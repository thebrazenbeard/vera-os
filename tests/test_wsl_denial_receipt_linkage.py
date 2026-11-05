"""Offline characterization of a missing Windows PING -> task -> denial link.

Pinned review input: vera-os Draft #74 db7243915c0089310bb4ea986677c105b9ba4c0a.
These tests operate on a disposable SQLite fixture. They do not launch a
Windows pipe, obtain a SID, authenticate a WSL principal, or qualify a host.
The expected failure is a *desired contract*, not an implemented capability.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veraos.windows_identity_ping import (  # noqa: E402
    REQUEST_SCHEMA, IdentityAuthorityUnavailable, foreground_ping,
)
from veraos.wsl_pilot import Pilot  # noqa: E402


PING_REQUEST_ID = "b" * 32
PING_NONCE = "c" * 32


@unittest.skipUnless(os.name == "posix", "Linux/POSIX SQLite fixture required")
class DenialReceiptLinkageSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        # Root-owned CI may be able to execute source fixtures, but it cannot
        # thereby qualify the unprivileged Linux UID boundary on Lappy.
        if os.geteuid() == 0:
            uid_patch = patch("veraos.wsl_pilot._uid", return_value=0)
            uid_patch.start()
            self.addCleanup(uid_patch.stop)
        self.parent = Path(tempfile.mkdtemp(prefix="veraos-denial-link-"))
        self.addCleanup(shutil.rmtree, self.parent)
        self.root = self.parent / "pilot"
        with Pilot.init(self.root):
            pass

    @staticmethod
    def ping_wire() -> bytes:
        return json.dumps({
            "schema": REQUEST_SCHEMA,
            "action": "PING",
            "request_id": PING_REQUEST_ID,
            "nonce": PING_NONCE,
        }).encode("utf-8")

    def test_current_denial_is_durable_but_unbound_to_task_or_principal(self) -> None:
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("inspect", "fixture.txt")
            self.assertFalse(pilot.protected_effect("protected.merge"))
            rows = pilot.db.execute(
                "SELECT task_id, code, detail FROM events ORDER BY seq"
            ).fetchall()
            columns = {row[1] for row in pilot.db.execute("PRAGMA table_info(events)")}

        self.assertEqual(rows[0], (task_id, "SUBMITTED", "inspect"))
        self.assertEqual(rows[1], (None, "PROTECTED_EFFECT_DENIED", "protected.merge"))
        self.assertNotIn("principal_id", columns)
        self.assertNotIn("ping_request_id", columns)
        self.assertNotIn("grant_sha256", columns)

    def test_untrusted_windows_ping_packet_grants_no_linux_task_or_receipt(self) -> None:
        # A syntactically valid packet is still not observed Windows token
        # identity, an authenticated grant, consent, or WSL admission.
        with self.assertRaises(IdentityAuthorityUnavailable):
            foreground_ping(self.ping_wire())
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.db.execute("SELECT count(*) FROM tasks").fetchone(), (0,))
            self.assertEqual(pilot.db.execute("SELECT count(*) FROM events").fetchone(), (0,))

    @unittest.expectedFailure
    def test_desired_denial_receipt_causally_links_ping_task_and_principal(self) -> None:
        """Desired future schema only: never treat an xfail as host auth proof.

        The fixture's PING ID is *untrusted*: even if this test someday passes,
        separate real Windows-token and cryptographic admission probes remain
        mandatory. The purpose here is to catch absent causal receipt fields.
        """
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("inspect", "fixture.txt")
            self.assertFalse(pilot.protected_effect("protected.merge"))
            denied = pilot.db.execute(
                "SELECT task_id, detail FROM events "
                "WHERE code='PROTECTED_EFFECT_DENIED' ORDER BY seq DESC LIMIT 1"
            ).fetchone()
        self.assertIsNotNone(denied)
        self.assertEqual(denied[0], task_id, "denial must reference the admitted task")
        detail = json.loads(denied[1])
        self.assertEqual(detail["ping_request_id"], PING_REQUEST_ID)
        self.assertTrue(detail["authenticated_principal_id"])
        self.assertEqual(detail["effect"], "protected.merge")


if __name__ == "__main__":
    unittest.main()
