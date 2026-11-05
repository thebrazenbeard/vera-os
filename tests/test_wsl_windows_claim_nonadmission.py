"""Cross-boundary regression: untrusted Windows claims do not authorize WSL.

This uses the existing production entrypoints, not a synthetic receiver. A
Windows PING request, fake grant and matching 32-hex request ID cannot grant
additional Linux task, status, run, cancellation or effect authority.

The same-UID keyed submit path remains a development fixture, not a Windows
nonce/revocation ledger or a proof of owner identity.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import shutil
import tempfile
import unittest
from unittest.mock import patch

from veraos.windows_identity_ping import (
    GRANT_SCHEMA, REQUEST_SCHEMA, IdentityAuthorityUnavailable, PingDenied,
    PingRequest, foreground_ping, preflight_untrusted_grant,
)
from veraos.wsl_ipc import _dispatch
from veraos.wsl_pilot import Pilot, PilotError


REQUEST_ID = "a" * 32
NONCE = "b" * 32
NOW = 1_800_000_000


def ping_request(*, nonce: str = NONCE) -> bytes:
    return json.dumps({
        "schema": REQUEST_SCHEMA, "action": "PING",
        "request_id": REQUEST_ID, "nonce": nonce,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")


def synthetic_grant(*, nonce: str = NONCE) -> dict:
    request = PingRequest.from_wire(ping_request(nonce=nonce))
    return {
        "schema": GRANT_SCHEMA, "action": "PING",
        "request_id": REQUEST_ID, "nonce": nonce,
        "request_sha256": request.sha256(),
        "host_id": "synthetic-host", "distro": "Ubuntu-26.04",
        "linux_uid": 1000, "subject_id": "test-only",
        "sid_sha256": "c" * 64, "logon_luid": "test-only",
        "issued_at": NOW - 1, "expires_at": NOW + 15,
        "revocation_epoch": 7, "signature": "d" * 128,
    }


@unittest.skipUnless(os.name == "posix", "Linux/WSL task fixture required")
class WindowsClaimCannotPromoteWSLTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.geteuid() == 0:
            for module in ("veraos.wsl_pilot._uid", "veraos.wsl_ipc._uid"):
                mocked_uid = patch(module, return_value=0)
                mocked_uid.start()
                self.addCleanup(mocked_uid.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.parent = Path(tempfile.mkdtemp(prefix="veraos-win-claim-hold-",
                                            dir=native_home))
        self.addCleanup(shutil.rmtree, self.parent)
        self.root = self.parent / "pilot"
        with Pilot.init(self.root):
            pass

    def dispatch(self, request: dict) -> dict:
        with Pilot(self.root) as pilot:
            return _dispatch(pilot, request)

    def state(self) -> dict:
        with Pilot(self.root) as pilot:
            return pilot.snapshot()

    def test_matching_grant_shape_is_not_windows_or_wsl_authority(self) -> None:
        grant = synthetic_grant()
        # This is a non-authorizing syntactic check, not signature verification.
        self.assertIsNone(preflight_untrusted_grant(
            grant, PingRequest.from_wire(ping_request()), now=NOW,
            expected_host="synthetic-host", expected_distro="Ubuntu-26.04",
            expected_uid=1000, expected_epoch=7))
        with self.assertRaises(IdentityAuthorityUnavailable):
            foreground_ping(ping_request(), grant=grant)
        with self.assertRaises(PilotError):
            self.dispatch({"action": "PING", "request_id": REQUEST_ID,
                           "nonce": NONCE, "grant": grant})
        self.assertEqual(self.state()["tasks"], [])
        self.assertEqual(self.state()["events"], [])

    def test_forged_grant_and_nonce_fields_cannot_enter_linux_submit(self) -> None:
        base = {"action": "submit", "worker": "inspect",
                "filename": "fixture.txt", "request_id": REQUEST_ID}
        for injection in (
            {"nonce": NONCE},
            {"grant": synthetic_grant()},
            {"sid_sha256": "c" * 64},
            {"authenticated_principal_id": "forged-principal"},
            {"revocation_epoch": 7},
        ):
            with self.subTest(injection=injection), self.assertRaises(PilotError):
                self.dispatch({**base, **injection})
        self.assertEqual(self.state()["tasks"], [])
        self.assertEqual(self.state()["events"], [])

    def test_host_assertions_do_not_promote_status_cancel_run_or_effect(self) -> None:
        task_id = self.dispatch({
            "action": "submit", "worker": "inspect",
            "filename": "fixture.txt", "request_id": REQUEST_ID,
        })["task_id"]
        for request in (
            {"action": "status", "windows_sid": "S-1-5-18"},
            {"action": "run", "task_id": task_id, "grant": synthetic_grant()},
            {"action": "cancel", "task_id": task_id,
             "authenticated_principal_id": "forged-principal"},
            {"action": "deny-effect", "effect": "protected.merge",
             "host_id": "synthetic-host"},
        ):
            with self.subTest(request=request), self.assertRaises(PilotError):
                self.dispatch(request)
        state = self.state()
        self.assertFalse(state["production_authority"])
        self.assertEqual(len(state["tasks"]), 1)
        self.assertEqual(state["tasks"][0]["status"], "QUEUED")
        self.assertEqual([event["code"] for event in state["events"]], ["SUBMITTED"])

    def test_same_uid_retry_dedup_is_not_a_windows_nonce_ledger(self) -> None:
        base = {"action": "submit", "worker": "inspect",
                "filename": "fixture.txt", "request_id": REQUEST_ID}
        task_id = self.dispatch(base)["task_id"]
        self.assertEqual(self.dispatch(base), {"task_id": task_id})
        with self.assertRaises(PilotError):
            self.dispatch({**base, "filename": "different.txt"})
        with self.assertRaises(PilotError):
            self.dispatch({**base, "nonce": "e" * 32})
        self.assertEqual(len(self.state()["tasks"]), 1)
        self.assertEqual(len(self.state()["events"]), 1)
        # The same request ID with a new PING nonce cannot reuse the old
        # grant shape; an exactly matching forged grant is still unauthorized.
        with self.assertRaises(PingDenied):
            preflight_untrusted_grant(
                synthetic_grant(), PingRequest.from_wire(
                    ping_request(nonce="e" * 32)), now=NOW,
                expected_host="synthetic-host", expected_distro="Ubuntu-26.04",
                expected_uid=1000, expected_epoch=7)
        with self.assertRaises(IdentityAuthorityUnavailable):
            foreground_ping(ping_request(nonce="e" * 32),
                            grant=synthetic_grant(nonce="e" * 32))

    def test_stale_epoch_and_expiry_are_rejected_before_bridge(self) -> None:
        grant = synthetic_grant()
        for changes in ({"revocation_epoch": 6}, {"expires_at": NOW}):
            with self.subTest(changes=changes), self.assertRaises(PingDenied):
                preflight_untrusted_grant(
                    {**grant, **changes}, PingRequest.from_wire(ping_request()),
                    now=NOW, expected_host="synthetic-host",
                    expected_distro="Ubuntu-26.04", expected_uid=1000,
                    expected_epoch=7)
        self.assertEqual(self.state()["tasks"], [])
        self.assertEqual(self.state()["events"], [])


if __name__ == "__main__":
    unittest.main()
