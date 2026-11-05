"""Offline checks for a *comparison*, not a trusted checkpoint issuer.

The test fabricates a simulated separate witness. It does not authenticate a
Windows identity, host-side monotonic store, or cross-resource commit.
"""
from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import pwd
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veraos.wsl_ipc import _dispatch, _keyed_ledger_digest  # noqa: E402
from veraos.wsl_pilot import Pilot, PilotError, SCHEMA  # noqa: E402
from veraos.wsl_recovery_witness import (  # noqa: E402
    ExternalCheckpoint, assert_matches_external_checkpoint,
)


@unittest.skipUnless(os.name == "posix", "POSIX SQLite fixture required")
class ExternalCheckpointComparisonTests(unittest.TestCase):
    def setUp(self):
        if os.geteuid() == 0:
            for name in ("veraos.wsl_pilot._uid", "veraos.wsl_ipc._uid"):
                identity = patch(name, return_value=0)
                identity.start()
                self.addCleanup(identity.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.temp = Path(tempfile.mkdtemp(prefix="veraos-witness-w8-", dir=native_home))
        self.addCleanup(shutil.rmtree, self.temp)
        self.root = self.temp / "pilot"
        with Pilot.init(self.root):
            pass

    def submit(self, request_id: str) -> str:
        with Pilot(self.root) as pilot:
            return _dispatch(pilot, {
                "action": "submit", "worker": "inspect", "filename": "fixture.txt",
                "request_id": request_id,
            })["task_id"]

    def fixture_claim(self) -> ExternalCheckpoint:
        # A test fixture only. Reading from the database is NOT an authority
        # source for a real external checkpoint and grants no authenticity.
        with Pilot(self.root) as pilot:
            return ExternalCheckpoint(
                owner_uid=os.geteuid(), schema=SCHEMA, keyed_version="1",
                keyed_count=pilot.db.execute(
                    "SELECT count(*) FROM ipc_submissions").fetchone()[0],
                keyed_digest=_keyed_ledger_digest(pilot.db),
            )

    def assert_claim(self, claim: ExternalCheckpoint | None):
        with Pilot(self.root) as pilot:
            assert_matches_external_checkpoint(pilot.db, claim)

    def backup(self, name: str) -> Path:
        dest = self.temp / name
        with closing(sqlite3.connect(self.root / "pilot.sqlite3")) as source:
            with closing(sqlite3.connect(dest)) as target:
                source.backup(target)
        return dest

    def restore(self, backup: Path) -> None:
        with closing(sqlite3.connect(backup)) as source:
            with closing(sqlite3.connect(self.root / "pilot.sqlite3")) as target:
                source.backup(target)

    def test_valid_matching_external_claim_passes_comparison_only(self):
        self.submit("a" * 32)
        self.assert_claim(self.fixture_claim())

    def test_legacy_database_without_keyed_table_is_held(self):
        claim = ExternalCheckpoint(os.geteuid(), SCHEMA, "1", 0, "0" * 64)
        with self.assertRaisesRegex(PilotError, "schema mismatch"):
            self.assert_claim(claim)

    def test_full_sqlite_rollback_rejected_against_newer_separate_claim(self):
        self.submit("a" * 32)
        older = self.backup("older.sqlite3")
        self.submit("b" * 32)
        newer_claim = self.fixture_claim()  # Simulated separate witness held out of DB.
        self.restore(older)
        with self.assertRaisesRegex(PilotError, "external recovery checkpoint mismatch"):
            self.assert_claim(newer_claim)

    def test_database_ahead_of_unpublished_witness_is_also_held(self):
        self.submit("a" * 32)
        older_claim = self.fixture_claim()
        self.submit("b" * 32)  # Model a crash before host witness publication.
        with self.assertRaisesRegex(PilotError, "external recovery checkpoint mismatch"):
            self.assert_claim(older_claim)

    def test_missing_invalid_and_foreign_claims_fail_closed(self):
        self.submit("a" * 32)
        valid = self.fixture_claim()
        for invalid in (
                None,
                ExternalCheckpoint(0, SCHEMA, "1", True, valid.keyed_digest),
                ExternalCheckpoint(os.geteuid(), SCHEMA, "1", 1, "nothex"),
                ExternalCheckpoint(os.geteuid() + 1, SCHEMA, "1", 1,
                                   valid.keyed_digest),
                ExternalCheckpoint(os.geteuid(), SCHEMA, "0", 1,
                                   valid.keyed_digest),
        ):
            with self.subTest(claim=invalid), self.assertRaises(PilotError):
                self.assert_claim(invalid)

    def test_self_forged_claim_can_match_rolled_back_db_without_authentication(self):
        """Deliberate falsifier: same-UID JSON is NOT trustworthy witness."""
        self.submit("a" * 32)
        older = self.backup("older.sqlite3")
        self.submit("b" * 32)
        self.restore(older)
        forged_claim = self.fixture_claim()
        self.assert_claim(forged_claim)  # Comparison alone cannot detect forgery.

    def test_unkeyed_task_rollback_is_invisible_to_mapping_only_claim(self):
        self.submit("a" * 32)
        old = self.backup("keyed-only.sqlite3")
        claim = self.fixture_claim()
        with Pilot(self.root) as pilot:
            pilot.submit("digest", "fixture.txt")  # Not included in keyed digest.
        self.restore(old)
        self.assert_claim(claim)  # Explicitly does NOT protect all tasks/events.

    def test_task_payload_mutation_does_not_change_keyed_ledger_anchor(self):
        task_id = self.submit("a" * 32)
        claim = self.fixture_claim()
        with Pilot(self.root) as pilot:
            pilot.db.execute("UPDATE tasks SET filename='other.txt' WHERE task_id=?",
                             (task_id,))
            pilot.db.commit()
        # Existing _submit_keyed checks must also run in any eventual gate;
        # this helper alone fingerprints mapping rows, not task bodies.
        self.assert_claim(claim)

    def test_corrupt_in_database_marker_fails_even_with_matching_claim(self):
        self.submit("a" * 32)
        claim = self.fixture_claim()
        with Pilot(self.root) as pilot:
            pilot.db.execute("UPDATE meta SET value=? WHERE key='ipc_submissions_digest'",
                             ("f" * 64,))
            pilot.db.commit()
        with self.assertRaisesRegex(PilotError, "external recovery checkpoint mismatch"):
            self.assert_claim(claim)


if __name__ == "__main__":
    unittest.main()
