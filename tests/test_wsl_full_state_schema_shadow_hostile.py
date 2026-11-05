"""Hostile schema-shadow falsifiers for the SOURCE-only full-state witness.

The connection is an in-process fixture, not an external WSL principal or
production trust issuer. A caller with an existing SQLite connection can
create TEMP objects that alter unqualified name resolution. These tests
must hold even if the witness claim was independently provided.
"""

from __future__ import annotations

import os
from pathlib import Path
import pwd
import shutil
import tempfile
import unittest
from unittest.mock import patch

from veraos.wsl_ipc import _dispatch
from veraos.wsl_pilot import Pilot, PilotError, SCHEMA
from veraos.wsl_recovery_witness import (
    FullStateTransition, assert_full_state_transition_consistent,
    full_pilot_state_digest,
)


@unittest.skipUnless(os.name == "posix", "POSIX fixture required")
class FullStateSchemaShadowHostileTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.geteuid() == 0:
            for module in ("veraos.wsl_pilot._uid", "veraos.wsl_ipc._uid"):
                fixture_uid = patch(module, return_value=0)
                fixture_uid.start()
                self.addCleanup(fixture_uid.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.parent = Path(tempfile.mkdtemp(prefix="veraos-shadow-hostile-",
                                            dir=native_home))
        self.addCleanup(shutil.rmtree, self.parent)
        self.root = self.parent / "pilot"
        with Pilot.init(self.root):
            pass
        with Pilot(self.root) as pilot:
            _dispatch(pilot, {"action": "submit", "worker": "inspect",
                              "filename": "fixture.txt", "request_id": "a" * 32})

    @staticmethod
    def committed_claim(digest: str) -> FullStateTransition:
        return FullStateTransition(
            owner_uid=os.geteuid(), schema=SCHEMA, version="1", generation=1,
            phase="COMMITTED", before_digest=digest, after_digest=digest,
        )

    def test_unsupported_persistent_view_holds_instead_of_escaping_digest(self) -> None:
        with Pilot(self.root) as pilot:
            baseline = full_pilot_state_digest(pilot.db)
            # A VIEW is durable schema state but omitted by the prior
            # table/index/trigger-only schema scan.
            pilot.db.execute("CREATE VIEW untracked_view AS SELECT * FROM tasks")
            pilot.db.commit()
            with self.assertRaisesRegex(PilotError, "unsupported.*schema"):
                assert_full_state_transition_consistent(
                    pilot.db, self.committed_claim(baseline))

    def test_temp_table_cannot_shadow_modified_persistent_task_state(self) -> None:
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("inspect", "fixture.txt")
            baseline = full_pilot_state_digest(pilot.db)
            # TEMP objects take precedence over main for unqualified SELECT.
            pilot.db.execute("CREATE TEMP TABLE tasks AS SELECT * FROM main.tasks")
            pilot.db.execute("UPDATE main.tasks SET status='COMPLETED' "
                             "WHERE task_id=?", (task_id,))
            pilot.db.commit()
            self.assertEqual(pilot.db.execute(
                "SELECT status FROM main.tasks WHERE task_id=?",
                (task_id,)).fetchone(), ("COMPLETED",))
            with self.assertRaisesRegex(PilotError, "unsupported.*schema|full-state mismatch"):
                assert_full_state_transition_consistent(
                    pilot.db, self.committed_claim(baseline))


if __name__ == "__main__":
    unittest.main()
