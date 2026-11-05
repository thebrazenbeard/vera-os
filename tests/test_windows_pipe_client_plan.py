"""Pure source tests for an explicitly untrusted Win32 narrow-access PING plan.

No CreateFileW, ReadFile, WriteFile, named pipe, Windows impersonation, grant,
or host effect is performed by these tests.
"""
from __future__ import annotations

import inspect
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos import windows_pipe_client_plan as client  # noqa: E402
from veraos.windows_identity_ping import (  # noqa: E402
    IdentityAuthorityUnavailable, PingDenied, PingRequest,
)
from veraos import windows_pipe_host as host  # noqa: E402


NAME = r"\\.\pipe\veraos-ping-" + "a" * 32
PING = b'{"schema":"VERAOS_WINDOWS_IDENTITY_PING_REQUEST_V1","action":"PING","request_id":"' + (
    b"b" * 32) + b'","nonce":"' + (b"c" * 32) + b'"}'


class NarrowWin32ClientPlanTests(unittest.TestCase):
    def test_exact_narrow_client_rights_are_subset_of_server_dacl(self):
        self.assertEqual(client.NARROW_CLIENT_ACCESS, 0x00120083)
        self.assertEqual(client.NARROW_CLIENT_ACCESS, host.CLIENT_PIPE_ACCESS)
        self.assertEqual(client.NARROW_CLIENT_ACCESS & host.FILE_CREATE_PIPE_INSTANCE, 0)
        self.assertEqual(client.NARROW_CLIENT_ACCESS & client.FILE_READ_EA, 0)
        self.assertEqual(client.NARROW_CLIENT_ACCESS & client.FILE_WRITE_ATTRIBUTES, 0)
        self.assertEqual(client.NARROW_CLIENT_ACCESS & client.FILE_WRITE_EA, 0)
        self.assertNotEqual(client.NARROW_CLIENT_ACCESS, client.FILE_GENERIC_READ)
        self.assertNotEqual(client.NARROW_CLIENT_ACCESS, client.FILE_GENERIC_WRITE)
        self.assertNotEqual(client.NARROW_CLIENT_ACCESS,
                            client.FILE_GENERIC_READ | client.FILE_GENERIC_WRITE)

    def test_valid_ping_produces_canonical_one_message_plan_without_native_handle(self):
        plan = client.plan_untrusted_ping(NAME, PING)
        self.assertEqual(plan.pipe_name, NAME)
        self.assertEqual(plan.desired_access, 0x00120083)
        self.assertEqual(plan.share_mode, 0)
        self.assertEqual(plan.creation_disposition, 3)
        self.assertEqual(plan.flags_and_attributes, 0)
        self.assertNotIn("server_authenticated", plan.__dataclass_fields__)
        self.assertNotIn("authorizes_task", plan.__dataclass_fields__)
        self.assertEqual(PingRequest.from_wire(plan.message).request_id, "b" * 32)
        self.assertLessEqual(len(plan.message), host.MAX_PIPE_FRAME)
        self.assertNotIn(b"\n", plan.message)
        self.assertFalse(hasattr(plan, "handle"))

    def test_server_dacl_access_change_fails_closed(self):
        with patch.object(client, "CLIENT_PIPE_ACCESS", 0x00120087):
            with self.assertRaisesRegex(client.ClientPlanDenied, "DACL"):
                client.plan_untrusted_ping(NAME, PING)

    def test_payload_bytes_canonicalize_order_and_whitespace(self):
        wire = b'{ "nonce":"' + b"c" * 32 + b'", "request_id":"' + (
            b"b" * 32) + b'", "action":"PING", "schema":"VERAOS_WINDOWS_IDENTITY_PING_REQUEST_V1" }'
        self.assertEqual(client.plan_untrusted_ping(NAME, wire).message,
                         client.plan_untrusted_ping(NAME, PING).message)

    def test_arbitrary_pipe_name_or_network_name_is_rejected(self):
        wrong = [
            "", NAME.upper(), r"\\.\pipe\veraos-ping-test", NAME + "x",
            r"\\remote\pipe\veraos-ping-" + "a" * 32,
            r"\\.\pipe\other-" + "a" * 32,
            r"\\.\pipe\veraos-ping-" + "A" * 32,
            r"\\.\pipe\veraos-ping-" + "../" + "a" * 32,
            123, None,
        ]
        for name in wrong:
            with self.subTest(name=name), self.assertRaises(client.ClientPlanDenied):
                client.plan_untrusted_ping(name, PING)

    def test_user_supplied_sid_and_duplicate_json_are_denied(self):
        for raw in (
            PING[:-1] + b',"sid":"S-1-5-18"}',
            PING[:-1] + b',"nonce":"' + b"c" * 32 + b'"}',
            b'{"schema":"bad","action":"PING","request_id":"' + b"b" * 32 +
            b'","nonce":"' + b"c" * 32 + b'"}',
            "not bytes",
        ):
            with self.subTest(raw=raw), self.assertRaises((PingDenied, client.ClientPlanDenied)):
                client.plan_untrusted_ping(NAME, raw)

    def test_no_source_client_runtime_or_pipe_response_admission(self):
        source = inspect.getsource(client)
        for forbidden in ("ctypes.WinDLL(", "CreateFileW(", "ReadFile(", "WriteFile(",
                          "ImpersonateNamedPipeClient(", "serve_forever(", "launch_wsl("):
            self.assertNotIn(forbidden, source)
        self.assertFalse(hasattr(client, "open_pipe"))
        self.assertFalse(hasattr(client, "connect"))
        self.assertFalse(hasattr(client, "send"))
        for raw in (b"", b'{"signature":"' + b"f" * 128 + b'"}'):
            with self.assertRaises(IdentityAuthorityUnavailable):
                client.reject_untrusted_reply(raw)


if __name__ == "__main__":
    unittest.main()
