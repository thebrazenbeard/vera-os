"""No native API calls: hostile source-only server-identity preflight checks."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import inspect
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos import windows_server_provenance as provenance  # noqa: E402


PIPE = r"\\.\pipe\veraos-ping-" + "a" * 32
IMAGE = r"C:\Program Files\VeraOS\vera-host-broker.exe"
DIGEST = "b" * 64
USER_SID = "S-1-5-18"
SERVICE_SID = "S-1-5-80-111-222-333-444-555"


def _claimed(**changes):
    claimed = provenance.ClaimedServerProcess(
        pipe_name=PIPE,
        pid_from_pipe_before=4242,
        pid_from_process_handle=4242,
        pid_from_pipe_after=4242,
        process_created_filetime=123456789012,
        image_path=IMAGE,
        image_sha256=DIGEST,
        process_user_sid=USER_SID,
        process_service_sid=SERVICE_SID,
        process_logon_luid="00000000000003e7",
    )
    return replace(claimed, **changes)


def _policy(**changes):
    policy = provenance.ClaimedHostIssuerPolicy(
        image_path=IMAGE,
        image_sha256=DIGEST,
        process_user_sid=USER_SID,
        service_sid=SERVICE_SID,
    )
    return replace(policy, **changes)


class WindowsServerProvenanceSourceTests(unittest.TestCase):
    def test_all_synthetic_claims_match_but_no_windows_server_is_authenticated(self):
        result = provenance.compare_claimed_server_process(_claimed(), _policy())
        self.assertTrue(result.checks_matching)
        self.assertEqual(result.evidence_class, "SOURCE_ONLY_UNTRUSTED_PROCESS_CLAIMS")
        self.assertEqual(result.admission, "DENIED")
        self.assertNotIn("admission", result.__dataclass_fields__)
        with self.assertRaises(provenance.ServerAuthorityUnavailable):
            provenance.deny_source_only_server_authority(result)

    def test_constructed_matching_fakes_are_explicitly_denied(self):
        # A same-logon attacker can claim a matching pid/manifest/hash/SID.
        # The complete synthetic data still does not establish key custody.
        fake = provenance.SourceServerComparison(checks_matching=True)
        self.assertEqual(fake.admission, "DENIED")
        with self.assertRaisesRegex(provenance.ServerAuthorityUnavailable, "signer"):
            provenance.deny_source_only_server_authority(fake)
        with self.assertRaises(FrozenInstanceError):
            fake.checks_matching = False

    def test_witnessed_pipe_pid_race_or_incorrect_process_handle_is_rejected(self):
        for field, wrong in (
            ("pid_from_pipe_before", 4241),
            ("pid_from_process_handle", 4243),
            ("pid_from_pipe_after", 4244),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(
                    provenance.ServerProvenanceDenied, "PID inconsistency"):
                provenance.compare_claimed_server_process(_claimed(**{field: wrong}), _policy())

    def test_pid_and_process_creation_shape_must_be_exact(self):
        for field, invalid in (
            ("pid_from_pipe_before", True), ("pid_from_process_handle", 0),
            ("pid_from_pipe_after", -1), ("pid_from_pipe_before", 2**32),
            ("process_created_filetime", False),
            ("process_created_filetime", -1),
        ):
            with self.subTest(field=field, invalid=invalid), self.assertRaises(
                    provenance.ServerProvenanceDenied):
                provenance.compare_claimed_server_process(_claimed(**{field: invalid}), _policy())

    def test_path_and_digest_mismatch_cannot_be_mistaken_for_trust(self):
        for field, wrong in (
            ("image_path", r"C:\Users\Public\vera-host-broker.exe"),
            ("image_sha256", "d" * 64),
            ("process_user_sid", "S-1-5-19"),
            ("process_service_sid", "S-1-5-80-999-888"),
        ):
            with self.subTest(field=field):
                result = provenance.compare_claimed_server_process(
                    _claimed(**{field: wrong}), _policy())
                self.assertFalse(result.checks_matching)
                self.assertEqual(result.admission, "DENIED")

    def test_pipe_name_requires_exact_local_form(self):
        for name in (
            "", PIPE.upper(), PIPE + "-extra", r"\\evilhost\pipe\veraos-ping-" + "a" * 32,
            r"\\.\pipe\not-vera-" + "a" * 32,
            r"\\.\pipe\veraos-ping-" + "A" * 32, 123, None,
        ):
            with self.subTest(name=name), self.assertRaises(provenance.ServerProvenanceDenied):
                provenance.compare_claimed_server_process(_claimed(pipe_name=name), _policy())

    def test_reject_untrustworthy_path_or_digest_shapes(self):
        for field, invalid in (
            ("image_path", "relative\\vera.exe"),
            ("image_path", r"\\server\share\vera.exe"),
            ("image_path", "C:\\bad\\nul\x00evil.exe"),
            ("image_path", "C:/Windows/vera.exe"),
            ("image_sha256", "A" * 64),
            ("image_sha256", "b" * 63),
        ):
            with self.subTest(field=field, invalid=invalid), self.assertRaises(
                    provenance.ServerProvenanceDenied):
                provenance.compare_claimed_server_process(_claimed(**{field: invalid}), _policy())
        with self.assertRaises(provenance.ServerProvenanceDenied):
            provenance.compare_claimed_server_process(_claimed(), _policy(image_path="relative.exe"))
        with self.assertRaises(provenance.ServerProvenanceDenied):
            provenance.compare_claimed_server_process(_claimed(image_path="é:\\vera.exe"), _policy())

    def test_token_group_claims_cannot_be_interchanged_with_user_sid(self):
        for changes in (
            {"process_service_sid": USER_SID},
            {"process_user_sid": SERVICE_SID},
            {"process_service_sid": "service:name"},
            {"process_logon_luid": "00000000000003eX"},
            {"process_logon_luid": True},
        ):
            with self.subTest(changes=changes), self.assertRaises(provenance.ServerProvenanceDenied):
                provenance.compare_claimed_server_process(_claimed(**changes), _policy())
        with self.assertRaises(provenance.ServerProvenanceDenied):
            provenance.compare_claimed_server_process(_claimed(), _policy(service_sid=USER_SID))

    def test_policy_is_not_a_verified_manifest_and_cannot_grant(self):
        forged_policy = _policy(image_sha256="d" * 64)
        forged_process = _claimed(image_sha256="d" * 64)
        result = provenance.compare_claimed_server_process(forged_process, forged_policy)
        self.assertTrue(result.checks_matching)
        self.assertEqual(result.admission, "DENIED")
        with self.assertRaises(provenance.ServerAuthorityUnavailable):
            provenance.deny_source_only_server_authority(result)

    def test_reject_subclasses_and_noncomparison_promotions(self):
        class FakeResult(provenance.SourceServerComparison):
            @property
            def admission(self):
                return "GRANTED"

        with self.assertRaises(provenance.ServerProvenanceDenied):
            provenance.deny_source_only_server_authority(FakeResult(True))
        with self.assertRaises(provenance.ServerProvenanceDenied):
            provenance.compare_claimed_server_process(_claimed(), object())

    def test_source_has_no_native_probe_or_grant_issuer_entrypoint(self):
        source = inspect.getsource(provenance)
        for forbidden in ("ctypes.WinDLL(", "CreateFileW(", "OpenProcess(",
                          "GetNamedPipeServerProcessId(", "issue_grant(",
                          "verify_signature(", "launch_wsl("):
            self.assertNotIn(forbidden, source)
        self.assertFalse(hasattr(provenance, "open_pipe"))
        self.assertFalse(hasattr(provenance, "authorize_server"))
        self.assertFalse(hasattr(provenance, "issue_grant"))


if __name__ == "__main__":
    unittest.main()
