"""Negative source contract: legacy PCCC paths are not Windows->WSL authority.

Cross-repository observation at this implementation's review frontier:
vera-mono accepted main 2cf4c425 still declares C:/VERA in the legacy
pc_connection/path_policy.py, while Patrick's current root is D:/VERA.
This test does NOT import or verify that external repository at runtime.

These tests cannot establish native Windows pipe custody, signer identity,
consent, revocation, Windows SID binding, or a deployed WSL verifier.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veraos.windows_identity_ping import (  # noqa: E402
    GRANT_SCHEMA, REQUEST_SCHEMA, IdentityAuthorityUnavailable, PingDenied,
    PingRequest, foreground_ping, preflight_untrusted_grant,
)
from veraos.worker_execution_gate import (  # noqa: E402
    DEV_SUBPROCESS_FIXTURE, WorkerExecutionHeld, require_dev_fixture_execution,
)


def _request() -> bytes:
    return json.dumps({
        "schema": REQUEST_SCHEMA, "action": "PING",
        "request_id": "a" * 32, "nonce": "b" * 32,
    }, sort_keys=True, separators=(",", ":")).encode("ascii")


def _claim() -> dict[str, object]:
    request = PingRequest.from_wire(_request())
    return {
        "schema": GRANT_SCHEMA, "action": "PING",
        "request_id": request.request_id, "nonce": request.nonce,
        "request_sha256": request.sha256(), "host_id": "claimed-Lappy",
        "distro": "Ubuntu-26.04", "linux_uid": 1000,
        "subject_id": "claimed-owner", "sid_sha256": "c" * 64,
        "logon_luid": "00000000000003e7", "issued_at": 100,
        "expires_at": 120, "revocation_epoch": 0,
        "signature": "d" * 128,
    }


class LegacyPcccCannotCrossWindowsWslBoundary(unittest.TestCase):
    def test_old_or_new_windows_root_fields_are_never_ping_identity(self):
        valid = json.loads(_request())
        for stale in ("C:\\VERA", "C:/VERA/PCCC", "D:\\VERA"):
            for field in ("read_root", "write_root", "root_path"):
                with self.subTest(path=stale, field=field), self.assertRaises(PingDenied):
                    PingRequest.from_wire(json.dumps({**valid, field: stale}).encode())

    def test_legacy_pccc_write_root_id_does_not_upgrade_synthetic_grant(self):
        request = PingRequest.from_wire(_request())
        base = _claim()
        for root_id in ("PCCC_WRITE_ROOT_V1", "VERA_ROOT", "NONE"):
            with self.subTest(root_id=root_id), self.assertRaises(PingDenied):
                preflight_untrusted_grant(
                    {**base, "write_root_id": root_id}, request,
                    now=101, expected_host="claimed-Lappy",
                    expected_distro="Ubuntu-26.04", expected_uid=1000,
                    expected_epoch=0,
                )

    def test_shape_matching_claim_remains_denied_without_host_issuer(self):
        request = PingRequest.from_wire(_request())
        preflight_untrusted_grant(
            _claim(), request, now=101, expected_host="claimed-Lappy",
            expected_distro="Ubuntu-26.04", expected_uid=1000,
            expected_epoch=0,
        )
        with self.assertRaises(IdentityAuthorityUnavailable):
            foreground_ping(_request(), grant=_claim())
        with self.assertRaises(WorkerExecutionHeld):
            require_dev_fixture_execution(
                operation=DEV_SUBPROCESS_FIXTURE,
                requested_effects=("legacy-pccc-write",),
                claimed_isolation_evidence={
                    "write_root_id": "PCCC_WRITE_ROOT_V1",
                    "write_root": "C:/VERA/PCCC",
                    "authorization": _claim(),
                },
            )


if __name__ == "__main__":
    unittest.main()
