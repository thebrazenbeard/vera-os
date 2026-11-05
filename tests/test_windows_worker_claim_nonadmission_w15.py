"""Cross-boundary negatives: source-shaped Windows PING is never worker authority.

These are Linux-safe SOURCE tests. They cannot certify the Windows pipe,
host-owned issuer, WSL verifier, or any OS-enforced worker confinement.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos.windows_identity_ping import (  # noqa: E402
    GRANT_SCHEMA, REQUEST_SCHEMA, IdentityAuthorityUnavailable, PingRequest,
    PingDenied, foreground_ping, preflight_untrusted_grant,
)
from veraos.windows_pipe_host import ObservedWindowsToken  # noqa: E402
from veraos.windows_ping_source_bridge import (  # noqa: E402
    ClaimedCompleteFrame, source_read_then_observe_denied,
)
from veraos.windows_ping_replay_journal import record_untrusted_ping  # noqa: E402
from veraos.windows_server_provenance import (  # noqa: E402
    ClaimedHostIssuerPolicy, ClaimedServerProcess, ServerAuthorityUnavailable,
    compare_claimed_server_process, deny_source_only_server_authority,
)
from veraos.worker_execution_gate import (  # noqa: E402
    DEV_SUBPROCESS_FIXTURE, WorkerExecutionHeld, assess_worker_execution,
    require_dev_fixture_execution,
)


_REQUEST = json.dumps({
    "schema": REQUEST_SCHEMA, "action": "PING",
    "request_id": "a" * 32, "nonce": "b" * 32,
}, separators=(",", ":"), sort_keys=True).encode("ascii")
_SID = "S-1-5-18"
_SERVICE_SID = "S-1-5-80-111-222-333-444-555"
_IMAGE = r"C:\Program Files\VeraOS\vera-host-broker.exe"


def _forged_full_grant(request: PingRequest) -> dict[str, object]:
    # This looks signed but no signature has been verified and every value is
    # caller-constructible. Even shape-matching preflight must not grant.
    return {
        "schema": GRANT_SCHEMA, "action": "PING",
        "request_id": request.request_id, "nonce": request.nonce,
        "request_sha256": request.sha256(), "host_id": "claimed-lappy",
        "distro": "Ubuntu-26.04", "linux_uid": 1000,
        "subject_id": "claimed-Patrick", "sid_sha256": "c" * 64,
        "logon_luid": "00000000000003e7", "issued_at": 100,
        "expires_at": 120, "revocation_epoch": 0,
        "signature": "d" * 128,
    }


class WindowsClaimCannotAdmitWorker(unittest.TestCase):
    def test_plausible_forged_signature_passes_shape_but_never_authenticates(self):
        request = PingRequest.from_wire(_REQUEST)
        grant = _forged_full_grant(request)
        self.assertIsNone(preflight_untrusted_grant(
            grant, request, now=101, expected_host="claimed-lappy",
            expected_distro="Ubuntu-26.04", expected_uid=1000,
            expected_epoch=0))
        with self.assertRaisesRegex(IdentityAuthorityUnavailable, "caller-supplied"):
            foreground_ping(_REQUEST, grant=grant)
        decision = assess_worker_execution(
            operation="production-worker", requested_effects=(),
            claimed_isolation_evidence=grant)
        self.assertFalse(decision.dev_fixture_allowed)
        self.assertEqual(decision.production_worker_isolation, "HOLD")
        self.assertEqual(decision.protected_effects, "DENIED")

    def test_matching_server_pid_image_and_sids_are_not_issuer_custody(self):
        observed = ClaimedServerProcess(
            pipe_name=r"\\.\pipe\veraos-ping-" + "a" * 32,
            pid_from_pipe_before=4242, pid_from_process_handle=4242,
            pid_from_pipe_after=4242, process_created_filetime=123456789,
            image_path=_IMAGE, image_sha256="e" * 64,
            process_user_sid=_SID, process_service_sid=_SERVICE_SID,
            process_logon_luid="00000000000003e7")
        policy = ClaimedHostIssuerPolicy(
            image_path=_IMAGE, image_sha256="e" * 64,
            process_user_sid=_SID, service_sid=_SERVICE_SID)
        comparison = compare_claimed_server_process(observed, policy)
        self.assertTrue(comparison.checks_matching)
        self.assertEqual(comparison.admission, "DENIED")
        with self.assertRaises(ServerAuthorityUnavailable):
            deny_source_only_server_authority(comparison)
        with self.assertRaises(WorkerExecutionHeld):
            require_dev_fixture_execution(
                operation="effect-worker", claimed_isolation_evidence=comparison)

    def test_complete_source_frame_and_token_shape_do_not_admit_protected_effect(self):
        observed = source_read_then_observe_denied(
            lambda maximum: ClaimedCompleteFrame(_REQUEST, True),
            lambda: ObservedWindowsToken(_SID, "00000000000003e7"))
        self.assertEqual(observed.admission, "DENIED")
        self.assertEqual(observed.authority, "SOURCE_ONLY_UNTRUSTED_CALLBACKS")
        with self.assertRaises(WorkerExecutionHeld):
            require_dev_fixture_execution(
                operation=DEV_SUBPROCESS_FIXTURE,
                requested_effects=("write-user-file",),
                claimed_isolation_evidence=observed)

    def test_fresh_source_replay_row_is_not_a_consumed_trusted_grant(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "observations.sqlite"
            first = record_untrusted_ping(path, _REQUEST)
            second = record_untrusted_ping(path, _REQUEST)
        self.assertFalse(first.replayed)
        self.assertTrue(second.replayed)
        self.assertEqual(first.admission, "DENIED")
        self.assertEqual(second.admission, "DENIED")
        for claimed in (first, second):
            decision = assess_worker_execution(
                operation="production-worker", claimed_isolation_evidence=claimed)
            self.assertFalse(decision.dev_fixture_allowed)
            self.assertEqual(decision.protected_effects, "DENIED")

    def test_hostile_authority_object_is_not_introspected_or_truth_tested(self):
        class Trap:
            def __getattribute__(self, key):
                raise AssertionError("untrusted object was evaluated")

            def __bool__(self):
                raise AssertionError("untrusted object was truth-tested")

        result = assess_worker_execution(
            operation=DEV_SUBPROCESS_FIXTURE,
            requested_effects=(),
            claimed_isolation_evidence=Trap())
        self.assertTrue(result.dev_fixture_allowed)
        self.assertEqual(result.production_worker_isolation, "HOLD")
        self.assertEqual(result.protected_effects, "DENIED")

    def test_caller_identity_and_effects_cannot_be_smuggled_in_ping_request(self):
        value = json.loads(_REQUEST)
        for extras in ({"sid": _SID}, {"linux_uid": 1000},
                       {"grant": _forged_full_grant(PingRequest.from_wire(_REQUEST))},
                       {"effect": "write-user-file"}, {"role": "owner"}):
            with self.subTest(extra=list(extras)), self.assertRaises(PingDenied):
                PingRequest.from_wire(json.dumps({**value, **extras}).encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
