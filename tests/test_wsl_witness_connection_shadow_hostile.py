"""Fail-closed witness checks for caller-controlled SQLite connection state.

These are in-process source fixtures; they do not prove that a remote caller
can reach the checker or that an external host-owned issuer exists.
"""

from __future__ import annotations

import os
from pathlib import Path
import pwd
import shutil
import tempfile
import unittest
from unittest.mock import patch

from veraos.wsl_ipc import _dispatch, _keyed_ledger_digest
from veraos.wsl_pilot import Pilot, PilotError, SCHEMA
from veraos.wsl_recovery_witness import (
    ExternalCheckpoint, FullStateTransition,
    assert_full_state_transition_consistent, assert_matches_external_checkpoint,
    full_pilot_state_digest,
)


@unittest.skipUnless(os.name == "posix", "POSIX SQLite fixture required")
class WitnessConnectionShadowHostileTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.geteuid() == 0:
            for name in ("veraos.wsl_pilot._uid", "veraos.wsl_ipc._uid"):
                mocked_uid = patch(name, return_value=0)
                mocked_uid.start()
                self.addCleanup(mocked_uid.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.temp = Path(tempfile.mkdtemp(prefix="veraos-witness-dbstate-",
                                          dir=native_home))
        self.addCleanup(shutil.rmtree, self.temp)
        self.root = self.temp / "pilot"
        with Pilot.init(self.root):
            pass
        with Pilot(self.root) as pilot:
            _dispatch(pilot, {"action": "submit", "worker": "inspect",
                              "filename": "fixture.txt", "request_id": "a" * 32})

    def test_legacy_keyed_checkpoint_rejects_temp_shadow_of_changed_main_ledger(self):
        with Pilot(self.root) as pilot:
            original_count = pilot.db.execute(
                "SELECT count(*) FROM ipc_submissions").fetchone()[0]
            original_digest = _keyed_ledger_digest(pilot.db)
            claim = ExternalCheckpoint(os.geteuid(), SCHEMA, "1",
                                       original_count, original_digest)

            # The TEMP copy has real PK, UNIQUE, and FK metadata. Legacy
            # schema checks must not accidentally authenticate this copy.
            pilot.db.executescript("""
                CREATE TEMP TABLE tasks (task_id TEXT PRIMARY KEY);
                INSERT INTO temp.tasks SELECT task_id FROM main.tasks;
                CREATE TEMP TABLE ipc_submissions (
                    principal_uid INTEGER NOT NULL,
                    request_id TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    task_id TEXT NOT NULL UNIQUE REFERENCES tasks(task_id),
                    PRIMARY KEY (principal_uid, request_id)
                );
                INSERT INTO temp.ipc_submissions
                    SELECT * FROM main.ipc_submissions;
            """)
            pilot.db.execute("UPDATE main.ipc_submissions SET payload_sha256=?",
                             ("f" * 64,))
            pilot.db.commit()
            self.assertEqual(pilot.db.execute(
                "SELECT payload_sha256 FROM main.ipc_submissions"
            ).fetchone(), ("f" * 64,))
            self.assertNotEqual(pilot.db.execute(
                "SELECT payload_sha256 FROM temp.ipc_submissions"
            ).fetchone(), ("f" * 64,))
            with self.assertRaisesRegex(PilotError, "temporary|shadow|attached"):
                assert_matches_external_checkpoint(pilot.db, claim)

    def test_full_state_witness_rejects_attached_db_outside_main_snapshot(self):
        with Pilot(self.root) as pilot:
            digest = full_pilot_state_digest(pilot.db)
            claim = FullStateTransition(os.geteuid(), SCHEMA, "1", 1,
                                        "COMMITTED", digest, digest)
            pilot.db.execute("ATTACH DATABASE ':memory:' AS outsider")
            pilot.db.execute("CREATE TABLE outsider.tasks (task_id TEXT)")
            with self.assertRaisesRegex(PilotError, "attached|connection schema"):
                assert_full_state_transition_consistent(pilot.db, claim)


if __name__ == "__main__":
    unittest.main()
