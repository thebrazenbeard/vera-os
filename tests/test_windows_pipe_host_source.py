"""Linux-safe Win32 SOURCE assertions, NOT real Windows pipe/token tests.

These tests never call CreateNamedPipeW, impersonate a client, change ACLs,
launch WSL, or provision a grant. Windows native verification remains BLOCKED.
"""
from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos import windows_pipe_host as host


class WindowsPipeSourceContractTests(unittest.TestCase):
    def test_native_abi_fail_closed_before_dll_load(self):
        source = inspect.getsource(host._Native.__init__)
        self.assertIn("_require_native_abi()", source)
        verify = inspect.getsource(host._require_native_abi)
        for required in ("_TOKEN_STATISTICS", "_SECURITY_ATTRIBUTES",
                         "_LUID", "_SID_AND_ATTRIBUTES", "_TOKEN_USER",
                         "_TOKEN_GROUPS_ONE", "Groups.offset",
                         "AuthenticationId.offset", "ModifiedId.offset"):
            self.assertIn(required, verify)
        # No Win32 API calls: if these tests ever run on a Windows test host,
        # fail before token parsing if its ctypes ABI is not the expected one.
        if sys.platform == "win32":
            host._require_native_abi()

    def test_token_groups_abi_drift_is_rejected_before_token_dereference(self):
        class PoisonedGroups(host.ctypes.Structure):
            _fields_ = [("GroupCount", host.wintypes.DWORD),
                        ("Unexpected", host.wintypes.DWORD * 4),
                        ("Groups", host._SID_AND_ATTRIBUTES * 1)]

        with patch.object(host, "_TOKEN_GROUPS_ONE", PoisonedGroups):
            with self.assertRaisesRegex(host.WindowsPipeUnavailable,
                                        "native Windows security ABI mismatch"):
                host._require_native_abi()

    def test_explicit_logon_sid_dacl_and_no_pipe_instance_creation_grant(self):
        self.assertEqual(host.CLIENT_PIPE_ACCESS & host.FILE_CREATE_PIPE_INSTANCE, 0)
        sddl = host._client_dacl_sddl("S-1-5-5-100-200")
        self.assertTrue(sddl.startswith("D:P(A;;0x00120083;;;S-1-5-5-100-200)"))
        self.assertIn("(A;;GA;;;SY)", sddl)
        self.assertNotIn(";;;WD)", sddl)
        self.assertNotIn(";;;AN)", sddl)
        self.assertNotIn(";;;AU)", sddl)
        for invalid in ("S-1-5-18", "S-1-1-0", "Everyone", "S-1-5-5-1-2)(A;;GA;;;WD", ""):
            with self.subTest(sid=invalid), self.assertRaises(host.WindowsPipeUnavailable):
                host._client_dacl_sddl(invalid)

    def test_single_first_instance_and_remote_rejection_flags_exist(self):
        self.assertEqual(host.FILE_FLAG_FIRST_PIPE_INSTANCE, 0x00080000)
        self.assertEqual(host.PIPE_REJECT_REMOTE_CLIENTS, 0x00000008)
        self.assertEqual(host.PIPE_TYPE_MESSAGE, 0x00000004)
        source = inspect.getsource(host.ephemeral_pipe)
        self.assertIn("FILE_FLAG_FIRST_PIPE_INSTANCE", source)
        self.assertIn("PIPE_REJECT_REMOTE_CLIENTS", source)
        self.assertIn("CreateNamedPipeW", source)
        self.assertIn("_token_sid(native, token, TOKEN_LOGON_SID)", source)

    def test_native_observation_is_last_read_only_and_cleanup_is_finally(self):
        source = inspect.getsource(host.observe_after_read)
        tree = ast.parse(source)
        self.assertTrue(any(isinstance(node, ast.Try) and node.finalbody
                            for node in ast.walk(tree)))
        for name in ("ImpersonateNamedPipeClient", "OpenThreadToken", "TOKEN_USER",
                     "TOKEN_STATISTICS", "RevertToSelf", "_exit"):
            with self.subTest(name=name):
                self.assertIn(name, source if name != "TOKEN_STATISTICS" else
                              source + inspect.getsource(host._token_authentication_luid))
        # This is structural coverage only. Neither mocked impersonation nor
        # shape assertions establish a Windows SID boundary.

    @unittest.skipIf(sys.platform == "win32", "no host API calls in source-only tests")
    def test_non_windows_fails_before_dll_load_or_pipe_creation(self):
        self.assertNotEqual(os.name, "nt")
        with self.assertRaises(host.WindowsPipeUnavailable):
            host._Native()
        with self.assertRaises(host.WindowsPipeUnavailable):
            with host.ephemeral_pipe():
                self.fail("non-Windows must never create a pipe")
        with self.assertRaises(host.WindowsPipeUnavailable):
            host.observe_after_read(host.EphemeralPipe("untrusted", 1))

    def test_no_public_auth_grant_or_external_effect_entrypoint(self):
        self.assertFalse(hasattr(host, "issue_grant"))
        self.assertFalse(hasattr(host, "authorize_ping"))
        self.assertFalse(hasattr(host, "serve_forever"))
        self.assertFalse(hasattr(host, "launch_wsl"))
        self.assertFalse(hasattr(host, "run_command"))
        source = inspect.getsource(host)
        self.assertNotIn("if __name__ == \"__main__\"", source)
        self.assertIn("not Vera identity/authorization", source)


if __name__ == "__main__":
    unittest.main()
