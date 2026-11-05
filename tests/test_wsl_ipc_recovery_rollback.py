"""Hostile recovery probes for the #74 WSL keyed-ledger pilot.

Every database is a disposable SQLite fixture. A changed, complete database
snapshot can look internally valid; these tests explicitly distinguish that
known inability from integrity checks that DO fail closed.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veraos.wsl_ipc import _dispatch
from veraos.wsl_pilot import Pilot, PilotError


KEY_A = "a" * 32
KEY_B = "b" * 32
KEY_C = "c" * 32


@unittest.skipUnless(os.name == "posix", "Linux/POSIX pilot fixture required")
class FullRollbackAndDowngradeTests(unittest.TestCase):
    def setUp(self):
        # CI scratch can be root. Patching only source fixture identity is NOT
        # evidence that the real non-root WSL owner gate works on Lappy.
        if os.geteuid() == 0:
            p1 = patch("veraos.wsl_pilot._uid", return_value=0)
            p2 = patch("veraos.wsl_ipc._uid", return_value=0)
            p1.start()
            p2.start()
            self.addCleanup(p1.stop)
            self.addCleanup(p2.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.temp = Path(tempfile.mkdtemp(prefix="veraos-rollback-w7-", dir=native_home))
        self.addCleanup(shutil.rmtree, self.temp)
        self.root = self.temp / "pilot"
        with Pilot.init(self.root):
            pass

    @staticmethod
    def request(key=KEY_A, *, filename="fixture.txt"):
        return {"action": "submit", "worker": "inspect", "filename": filename,
                "request_id": key}

    def submit(self, key=KEY_A, *, filename="fixture.txt"):
        with Pilot(self.root) as pilot:
            return _dispatch(pilot, self.request(key, filename=filename))["task_id"]

    def counts(self):
        with Pilot(self.root) as pilot:
            return tuple(pilot.db.execute("SELECT count(*) FROM " + table).fetchone()[0]
                         for table in ("tasks", "events", "ipc_submissions"))

    def db_backup(self, path: Path) -> None:
        with closing(sqlite3.connect(self.root / "pilot.sqlite3")) as src:
            with closing(sqlite3.connect(path)) as dst:
                src.backup(dst)

    def db_restore(self, path: Path) -> None:
        with closing(sqlite3.connect(path)) as src:
            with closing(sqlite3.connect(self.root / "pilot.sqlite3")) as dst:
                src.backup(dst)

    def test_full_database_rollback_to_valid_older_digest_replays_lost_key(self):
        """Current behavior, NOT success: same DB digest authenticates no time.

        Earlier A survives; B was committed and externally acknowledged before
        restoring the complete, internally consistent A-only snapshot. B's
        exact retry gets a new ID, despite both snapshots being valid SQLite.
        """
        first_a = self.submit(KEY_A)
        before_b = self.temp / "older-complete.sqlite3"
        self.db_backup(before_b)
        original_b = self.submit(KEY_B)
        self.assertEqual(self.counts(), (2, 2, 2))
        self.db_restore(before_b)
        self.assertEqual(self.submit(KEY_A), first_a)
        replayed_b = self.submit(KEY_B)
        self.assertNotEqual(replayed_b, original_b)
        self.assertEqual(self.counts(), (2, 2, 2))

    @unittest.expectedFailure
    def test_future_external_checkpoint_must_hold_full_database_rollback(self):
        """Desired future property requires an anchor OUTSIDE pilot.sqlite3."""
        self.submit(KEY_A)
        snapshot = self.temp / "trusted-old.sqlite3"
        self.db_backup(snapshot)
        self.submit(KEY_B)
        self.db_restore(snapshot)
        with self.assertRaises(PilotError):
            self.submit(KEY_B)

    def test_legacy_73_writer_after_marker_poisoning_is_detected_on_upgrade(self):
        """Model the exact #73 SQL commit shape, omitting #74 digest refresh.

        This is a synthetic downgrade-writer transaction, not execution of the
        old binary; it proves current validation catches the stale digest.
        """
        self.submit(KEY_A)
        legacy_task = uuid.uuid4().hex
        payload = json.dumps({"action": "submit", "worker": "inspect",
                              "filename": "fixture.txt"}, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        with Pilot(self.root) as pilot:
            pilot.db.execute("BEGIN IMMEDIATE")
            pilot.db.execute("INSERT INTO tasks VALUES (?,?,?,?,?)",
                             (legacy_task, "inspect", "fixture.txt", "QUEUED", os.geteuid()))
            pilot.db.execute("INSERT INTO events(task_id,code,detail) VALUES (?,?,?)",
                             (legacy_task, "SUBMITTED", "inspect"))
            pilot.db.execute("INSERT INTO ipc_submissions VALUES (?,?,?,?)",
                             (os.geteuid(), KEY_B, digest, legacy_task))
            pilot.db.commit()  # #73 did not update meta.ipc_submissions_digest.
        with self.assertRaisesRegex(PilotError, "ledger changed"):
            self.submit(KEY_B)
        self.assertEqual(self.counts(), (2, 2, 2))

    def test_stale_or_missing_submitted_receipt_is_held(self):
        task_id = self.submit(KEY_A)
        with Pilot(self.root) as pilot:
            # Emulates a corrupt restore by disabling an append-only trigger
            # ONLY inside this disposable test DB; production forbids deletion.
            pilot.db.execute("DROP TRIGGER events_no_delete")
            pilot.db.execute("DELETE FROM events WHERE task_id=? AND code='SUBMITTED'",
                             (task_id,))
            pilot.db.executescript("""
                CREATE TRIGGER events_no_delete BEFORE DELETE ON events
                BEGIN SELECT RAISE(ABORT, 'events are append only'); END;
            """)
            pilot.db.commit()
        with self.assertRaisesRegex(PilotError, "integrity mismatch"):
            self.submit(KEY_A)
        self.assertEqual(self.counts(), (1, 0, 1))

    def test_corrupted_version_marker_and_digest_both_hold(self):
        self.submit(KEY_A)
        with Pilot(self.root) as pilot:
            version = pilot.db.execute(
                "SELECT value FROM meta WHERE key='ipc_submissions_version'").fetchone()[0]
            pilot.db.execute("UPDATE meta SET value='unrecognized' "
                             "WHERE key='ipc_submissions_version'")
            pilot.db.commit()
        with self.assertRaisesRegex(PilotError, "unsupported keyed"):
            self.submit(KEY_A)
        with Pilot(self.root) as pilot:
            pilot.db.execute("UPDATE meta SET value=? "
                             "WHERE key='ipc_submissions_version'", (version,))
            pilot.db.execute("UPDATE meta SET value=? "
                             "WHERE key='ipc_submissions_digest'", ("0" * 64,))
            pilot.db.commit()
        with self.assertRaisesRegex(PilotError, "ledger changed"):
            self.submit(KEY_A)
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_unkeyed_legacy_task_is_not_reconciled_under_existing_marker(self):
        """Current permitted opt-in semantics, not a keyed-integrity defect.

        A new unkeyed Pilot.submit writes an unmapped task and event. The
        mapping ledger digest stays valid, so a later keyed request proceeds.
        This becomes a migration ambiguity if the markers are later lost.
        """
        original = self.submit(KEY_A)
        with Pilot(self.root) as pilot:
            unkeyed = pilot.submit("inspect", "fixture.txt")
        self.assertEqual(self.submit(KEY_A), original)
        keyed_b = self.submit(KEY_B)
        self.assertNotEqual(keyed_b, unkeyed)
        self.assertEqual(self.counts(), (3, 3, 2))

    def test_unkeyed_extra_task_forces_hold_if_markers_are_later_missing(self):
        self.submit(KEY_A)
        with Pilot(self.root) as pilot:
            pilot.submit("inspect", "fixture.txt")
            pilot.db.execute("DELETE FROM meta WHERE key IN "
                             "('ipc_submissions_version','ipc_submissions_digest')")
            pilot.db.commit()
        with self.assertRaisesRegex(PilotError, "unmapped pre-marker"):
            self.submit(KEY_B)
        self.assertEqual(self.counts(), (2, 2, 1))


if __name__ == "__main__":
    unittest.main()
