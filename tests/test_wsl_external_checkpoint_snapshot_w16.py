"""Source-only regression for external checkpoint comparisons under WAL writes.

The fabricated checkpoint in these tests does not authenticate a host-owned
issuer or grant protected effects. A coherent SQLite snapshot is necessary but
not sufficient for a safe cross-host recovery protocol.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veraos import wsl_recovery_witness as witness  # noqa: E402
from veraos.wsl_ipc import _dispatch, _keyed_ledger_digest  # noqa: E402
from veraos.wsl_pilot import Pilot, PilotError, SCHEMA  # noqa: E402


@unittest.skipUnless(os.name == "posix", "POSIX SQLite fixture required")
class ExternalCheckpointSnapshotTests(unittest.TestCase):
    def setUp(self):
        if os.geteuid() == 0:
            for target in ("veraos.wsl_pilot._uid", "veraos.wsl_ipc._uid"):
                identity = patch(target, return_value=0)
                identity.start()
                self.addCleanup(identity.stop)
        self.temp = Path(tempfile.mkdtemp(prefix="veraos-checkpoint-w16-"))
        self.addCleanup(shutil.rmtree, self.temp)
        self.root = self.temp / "pilot"
        with Pilot.init(self.root):
            pass
        with Pilot(self.root) as pilot:
            _dispatch(pilot, {"action": "submit", "worker": "inspect",
                              "filename": "fixture.txt", "request_id": "a" * 32})

    def checkpoint(self) -> witness.ExternalCheckpoint:
        # This locally constructed value has NO authority as a real witness.
        with Pilot(self.root) as pilot:
            return witness.ExternalCheckpoint(
                owner_uid=os.geteuid(), schema=SCHEMA, keyed_version="1",
                keyed_count=pilot.db.execute("SELECT COUNT(*) FROM ipc_submissions").fetchone()[0],
                keyed_digest=_keyed_ledger_digest(pilot.db),
            )

    def test_matching_stable_snapshot_does_not_leave_transaction_open(self):
        claim = self.checkpoint()
        with Pilot(self.root) as pilot:
            self.assertFalse(pilot.db.in_transaction)
            witness.assert_matches_external_checkpoint(pilot.db, claim)
            self.assertFalse(pilot.db.in_transaction)

    def test_concurrent_wal_writer_after_digest_scan_fails_closed(self):
        claim = self.checkpoint()
        original_digest = witness._keyed_ledger_digest
        triggered = False

        with Pilot(self.root) as writer, Pilot(self.root) as reader:
            def concurrent_write(db):
                nonlocal triggered
                digest = original_digest(db)
                if not triggered:
                    triggered = True
                    _dispatch(writer, {"action": "submit", "worker": "inspect",
                                       "filename": "fixture.txt", "request_id": "b" * 32})
                return digest

            with patch.object(witness, "_keyed_ledger_digest", side_effect=concurrent_write):
                with self.assertRaisesRegex(PilotError, "concurrent database change; hold"):
                    witness.assert_matches_external_checkpoint(reader.db, claim)
            self.assertTrue(triggered)
            self.assertFalse(reader.db.in_transaction)
        # The committed new mapping is real, and an older claim must now fail.
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.db.execute("SELECT COUNT(*) FROM ipc_submissions").fetchone()[0], 2)
            with self.assertRaisesRegex(PilotError, "external recovery checkpoint mismatch"):
                witness.assert_matches_external_checkpoint(pilot.db, claim)

    def test_existing_caller_transaction_is_held_without_commit_or_rollback(self):
        claim = self.checkpoint()
        with Pilot(self.root) as pilot:
            pilot.db.execute("BEGIN")
            try:
                with self.assertRaisesRegex(PilotError, "preexisting transaction; hold"):
                    witness.assert_matches_external_checkpoint(pilot.db, claim)
                self.assertTrue(pilot.db.in_transaction)
            finally:
                pilot.db.rollback()

    def test_stale_caller_owned_read_snapshot_can_never_be_accepted(self):
        claim = self.checkpoint()
        with Pilot(self.root) as writer, Pilot(self.root) as reader:
            reader.db.execute("BEGIN")
            try:
                reader.db.execute("SELECT COUNT(*) FROM ipc_submissions").fetchone()
                _dispatch(writer, {"action": "submit", "worker": "inspect",
                                   "filename": "fixture.txt", "request_id": "c" * 32})
                with self.assertRaisesRegex(PilotError, "preexisting transaction; hold"):
                    witness.assert_matches_external_checkpoint(reader.db, claim)
                self.assertTrue(reader.db.in_transaction)
            finally:
                reader.db.rollback()

    def test_failed_comparison_releases_owned_snapshot(self):
        bad = witness.ExternalCheckpoint(os.geteuid(), SCHEMA, "1", 999, "0" * 64)
        with Pilot(self.root) as pilot:
            with self.assertRaises(PilotError):
                witness.assert_matches_external_checkpoint(pilot.db, bad)
            self.assertFalse(pilot.db.in_transaction)


if __name__ == "__main__":
    unittest.main()
