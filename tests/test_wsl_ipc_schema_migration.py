"""Fail-closed recovery probes for V1's opt-in keyed IPC submit.

Disposable real SQLite fixtures; not an installed Lappy/WSL service and not
proof against same-UID tampering, journal-level rollback, or lost backups.
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

from veraos.wsl_ipc import _dispatch
from veraos.wsl_pilot import Pilot, PilotError, SCHEMA


REQUEST_ID = "0123456789abcdef" * 2


@unittest.skipUnless(os.name == "posix", "Linux/POSIX fixture required")
class IdempotencyMigrationRecoveryTests(unittest.TestCase):
    def setUp(self):
        # Source-level verification in root-owned CI sandboxes only. A real
        # Lappy qualification MUST use an actual non-root Linux principal.
        if os.geteuid() == 0:
            uid_pilot = patch("veraos.wsl_pilot._uid", return_value=0)
            uid_ipc = patch("veraos.wsl_ipc._uid", return_value=0)
            uid_pilot.start()
            uid_ipc.start()
            self.addCleanup(uid_pilot.stop)
            self.addCleanup(uid_ipc.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.top = Path(tempfile.mkdtemp(prefix="veraos-ipc-migrate-", dir=native_home))
        self.addCleanup(shutil.rmtree, self.top)
        self.root = self.top / "pilot"
        with Pilot.init(self.root):
            pass

    @staticmethod
    def request() -> dict:
        return {"action": "submit", "worker": "inspect", "filename": "fixture.txt",
                "request_id": REQUEST_ID}

    @staticmethod
    def dispatch(root: Path, request: dict) -> dict:
        with Pilot(root) as pilot:
            return _dispatch(pilot, request)

    def _counts(self, root: Path | None = None) -> tuple[int, int, int]:
        with Pilot(root or self.root) as pilot:
            tasks = pilot.db.execute("SELECT count(*) FROM tasks").fetchone()[0]
            events = pilot.db.execute("SELECT count(*) FROM events").fetchone()[0]
            keys = pilot.db.execute("SELECT count(*) FROM ipc_submissions").fetchone()[0]
        return tasks, events, keys

    def test_initial_v1_database_has_no_keyed_table(self):
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.db.execute(
                "SELECT value FROM meta WHERE key='schema'").fetchone(), (SCHEMA,))
            self.assertIsNone(pilot.db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='ipc_submissions'").fetchone())
            self.assertIsNone(pilot.db.execute(
                "SELECT value FROM meta WHERE key='ipc_submissions_version'").fetchone())
            self.assertIsNone(pilot.db.execute(
                "SELECT value FROM meta WHERE key='ipc_submissions_digest'").fetchone())

    def test_first_keyed_submit_creates_table_but_does_not_upgrade_schema_marker(self):
        self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.db.execute(
                "SELECT value FROM meta WHERE key='schema'").fetchone(), (SCHEMA,))
            self.assertEqual(pilot.db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='ipc_submissions'").fetchone(), (1,))
            self.assertEqual(pilot.db.execute(
                "SELECT value FROM meta WHERE key='ipc_submissions_version'").fetchone(), ("1",))
            self.assertRegex(pilot.db.execute(
                "SELECT value FROM meta WHERE key='ipc_submissions_digest'").fetchone()[0],
                r"^[0-9a-f]{64}$")
        self.assertEqual(self._counts(), (1, 1, 1))

    def test_post_commit_pre_response_loss_is_recoverable_from_durable_key(self):
        # The first _dispatch commits before returning; deliberately discard
        # its returned value to model a missing/truncated IPC response.
        self.dispatch(self.root, self.request())
        with closing(sqlite3.connect(self.root / "pilot.sqlite3")) as db:
            committed = db.execute("SELECT task_id FROM ipc_submissions").fetchone()[0]
        result = self.dispatch(self.root, self.request())  # New SQLite client
        self.assertEqual(result, {"task_id": committed})
        self.assertEqual(self._counts(), (1, 1, 1))

    def test_complete_sqlite_backup_restore_preserves_request_key(self):
        original = self.dispatch(self.root, self.request())
        restored = self.top / "fully_restored"
        with Pilot.init(restored):
            pass
        with closing(sqlite3.connect(self.root / "pilot.sqlite3")) as source:
            with closing(sqlite3.connect(restored / "pilot.sqlite3")) as target:
                source.backup(target)
        self.assertEqual(self.dispatch(restored, self.request()), original)
        self.assertEqual(self._counts(restored), (1, 1, 1))

    def test_failed_first_keyed_migration_rolls_back_table_task_and_event(self):
        with Pilot(self.root) as pilot:
            pilot.db.executescript("""
                CREATE TRIGGER refuse_submitted BEFORE INSERT ON events
                WHEN NEW.code='SUBMITTED'
                BEGIN SELECT RAISE(ABORT, 'forced precommit failure'); END;
            """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.db.execute("SELECT count(*) FROM tasks").fetchone(), (0,))
            self.assertEqual(pilot.db.execute("SELECT count(*) FROM events").fetchone(), (0,))
            # DDL and DML are in one explicit transaction.
            self.assertIsNone(pilot.db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='ipc_submissions'").fetchone())
            pilot.db.execute("DROP TRIGGER refuse_submitted")
            pilot.db.commit()
        self.dispatch(self.root, self.request())
        self.assertEqual(self._counts(), (1, 1, 1))

    def test_partial_restore_without_mapping_holds_instead_of_duplicate(self):
        """Missing keyed table with retained marker must fail closed."""
        self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            pilot.db.execute("DROP TABLE ipc_submissions")
            pilot.db.commit()
        with self.assertRaisesRegex(PilotError, "ledger missing"):
            self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.db.execute("SELECT count(*) FROM tasks").fetchone(), (1,))
            self.assertEqual(pilot.db.execute("SELECT count(*) FROM events").fetchone(), (1,))
            self.assertEqual(pilot.db.execute(
                "SELECT value FROM meta WHERE key='ipc_submissions_version'").fetchone(), ("1",))

    def test_orphaned_mapping_holds_instead_of_returning_stale_task(self):
        """A restored request mapping must reference a real task."""
        original = self.dispatch(self.root, self.request())
        with closing(sqlite3.connect(self.root / "pilot.sqlite3")) as db:
            db.execute("PRAGMA foreign_keys=OFF")
            db.execute("DELETE FROM tasks WHERE task_id=?", (original["task_id"],))
            db.commit()
        with self.assertRaisesRegex(PilotError, "broken task"):
            self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            self.assertIsNone(pilot.db.execute(
                "SELECT 1 FROM tasks WHERE task_id=?", (original["task_id"],)).fetchone())
            self.assertEqual(pilot.db.execute(
                "SELECT count(*) FROM ipc_submissions").fetchone(), (1,))

    def test_pre_marker_legacy_table_with_valid_mapping_gets_marker(self):
        """Upgrade a #73-style table/receipt in place, without rewriting keys."""
        original = self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            pilot.db.execute("DELETE FROM meta WHERE key='ipc_submissions_version'")
            pilot.db.execute("DELETE FROM meta WHERE key='ipc_submissions_digest'")
            pilot.db.commit()
        self.assertEqual(self.dispatch(self.root, self.request()), original)
        self.assertEqual(self._counts(), (1, 1, 1))
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.db.execute(
                "SELECT value FROM meta WHERE key='ipc_submissions_version'").fetchone(), ("1",))

    def test_absent_marker_and_table_with_prior_unkeyed_task_is_ambiguous(self):
        """Refuse V1 history that cannot distinguish lost keys from unkeyed work."""
        with Pilot(self.root) as pilot:
            pilot.submit("inspect", "fixture.txt")
        with self.assertRaisesRegex(PilotError, "ambiguous pre-keyed"):
            self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            self.assertIsNone(pilot.db.execute(
                "SELECT value FROM meta WHERE key='ipc_submissions_version'").fetchone())
            self.assertIsNone(pilot.db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='ipc_submissions'").fetchone())

    def test_existing_mapping_with_modified_task_payload_holds(self):
        self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            pilot.db.execute("UPDATE tasks SET filename='altered.txt'")
            pilot.db.commit()
        with self.assertRaisesRegex(PilotError, "integrity mismatch"):
            self.dispatch(self.root, self.request())

    def test_missing_mapping_row_with_surviving_marker_holds(self):
        """The table itself can survive a partial restore that drops one row."""
        original = self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            pilot.db.execute("DELETE FROM ipc_submissions WHERE task_id=?",
                             (original["task_id"],))
            pilot.db.commit()
        with self.assertRaisesRegex(PilotError, "ledger changed"):
            self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.db.execute("SELECT count(*) FROM tasks").fetchone(), (1,))
            self.assertEqual(pilot.db.execute("SELECT count(*) FROM events").fetchone(), (1,))
            self.assertEqual(pilot.db.execute("SELECT count(*) FROM ipc_submissions").fetchone(), (0,))

    def test_missing_mapping_row_in_pre_marker_legacy_table_holds(self):
        """Old #73 file without either marker cannot silently lose a keyed row."""
        self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            pilot.db.execute("DELETE FROM meta WHERE key='ipc_submissions_version'")
            pilot.db.execute("DELETE FROM meta WHERE key='ipc_submissions_digest'")
            pilot.db.execute("DELETE FROM ipc_submissions")
            pilot.db.commit()
        with self.assertRaisesRegex(PilotError, "unmapped pre-marker"):
            self.dispatch(self.root, self.request())

    def test_missing_digest_with_version_holds(self):
        self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            pilot.db.execute("DELETE FROM meta WHERE key='ipc_submissions_digest'")
            pilot.db.commit()
        with self.assertRaisesRegex(PilotError, "metadata incomplete"):
            self.dispatch(self.root, self.request())

    def test_precreated_weak_table_without_constraints_is_rejected(self):
        """No legacy table without composite PK, task uniqueness, FK is admitted."""
        with Pilot(self.root) as pilot:
            pilot.db.execute("""
                CREATE TABLE ipc_submissions (
                    principal_uid INTEGER, request_id TEXT,
                    payload_sha256 TEXT, task_id TEXT)
            """)
            pilot.db.commit()
        with self.assertRaisesRegex(PilotError, "schema mismatch"):
            self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.db.execute("SELECT count(*) FROM tasks").fetchone(), (0,))
            self.assertIsNone(pilot.db.execute(
                "SELECT value FROM meta WHERE key='ipc_submissions_version'").fetchone())

    def test_table_with_primary_key_but_no_task_uniqueness_or_fk_rejected(self):
        with Pilot(self.root) as pilot:
            pilot.db.execute("""
                CREATE TABLE ipc_submissions (
                    principal_uid INTEGER NOT NULL,
                    request_id TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    PRIMARY KEY (principal_uid, request_id))
            """)
            pilot.db.commit()
        with self.assertRaisesRegex(PilotError, "foreign key missing"):
            self.dispatch(self.root, self.request())

    def test_keyed_migration_adds_event_lookup_index(self):
        self.dispatch(self.root, self.request())
        with Pilot(self.root) as pilot:
            names = [r[1] for r in pilot.db.execute("PRAGMA index_list('events')")]
            self.assertIn("events_keyed_receipt_idx", names)


if __name__ == "__main__":
    unittest.main()
