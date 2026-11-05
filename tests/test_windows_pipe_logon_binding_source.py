"""SOURCE-only same-logon token binding; never opens a Windows named pipe.

These tests prove pure validation and inspect wiring only. They do not prove
native token impersonation, DACL enforcement, endpoint provenance, consent,
Windows principal mapping, a signed grant or WSL task admission.
"""
from __future__ import annotations

import inspect
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos import windows_pipe_host as host  # noqa: E402


class PipeLogonBindingSourceTests(unittest.TestCase):
    def test_matching_kernel_logon_sid_passes_non_authorizing_helper(self) -> None:
        # This is only a source-level shape/equality check; it creates no
        # observed token and cannot authorize a task.
        self.assertIsNone(host._require_same_logon_sid(
            "S-1-5-5-100-200", "S-1-5-5-100-200"))

    def test_other_logon_sid_is_denied_despite_valid_dacl_shape(self) -> None:
        # A Windows SYSTEM/admin client may have OS privilege to connect in
        # spite of the broker's allowlist, so check the observed logon SID too.
        for other in ("S-1-5-5-100-201", "S-1-5-5-101-200"):
            with self.subTest(client=other), self.assertRaisesRegex(
                    host.WindowsPipeUnavailable, "logon session mismatch"):
                host._require_same_logon_sid("S-1-5-5-100-200", other)

    def test_malformed_or_non_string_session_claims_fail_closed(self) -> None:
        invalid: tuple[object, ...] = (
            "S-1-5-18", "S-1-5-5-100-200)(A;;GA;;;WD", "", None, 1,
            "S-1-5-5-+100-200", "S-1-5-5-100-200\n",
        )
        for value in invalid:
            with self.subTest(client=value), self.assertRaises(
                    host.WindowsPipeUnavailable):
                host._require_same_logon_sid("S-1-5-5-100-200", value)  # type: ignore[arg-type]
            with self.subTest(owner=value), self.assertRaises(
                    host.WindowsPipeUnavailable):
                host._require_same_logon_sid(value, "S-1-5-5-100-200")  # type: ignore[arg-type]

    def test_pipe_ownership_custody_flows_to_post_read_observation(self) -> None:
        create = inspect.getsource(host.ephemeral_pipe)
        observe = inspect.getsource(host.observe_after_read)
        self.assertIn("owner_logon_sid=logon_sid", create)
        self.assertIn("_token_sid(native, token, TOKEN_LOGON_SID)", observe)
        self.assertIn("_require_same_logon_sid(pipe.owner_logon_sid, client_logon_sid)",
                      observe)
        # TokenUser/LUID still come only from the impersonated native token.
        self.assertIn("_token_sid(native, token, TOKEN_USER)", observe)
        self.assertIn("_token_authentication_luid(native, token)", observe)
        self.assertIn("RevertToSelf", observe)


if __name__ == "__main__":
    unittest.main()
