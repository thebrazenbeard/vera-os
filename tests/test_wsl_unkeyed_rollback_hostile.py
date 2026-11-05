"""Independent fail-closed characterization of WSL pilot admission gaps.

Pinned review input: VeraOS Draft #74 048da7c59d72dbbbe718b48d1bda91460e0fda8b.
These are disposable SQLite source fixtures, NOT Windows/WSL identity probes.
"""
from __future__ import annotations

import os
from pathlib import Path
import pwd
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veraos import wsl_ipc  # noqa: E402
from veraos.wsl_pilot import Pilot  # noqa: E402


@unittest.skipUnless(os.name == "posix", "POSIX fixture required")
class UnkeyedRollbackHostileTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.geteuid() == 0:
            for module in ("veraos.wsl_pilot._uid", "veraos.wsl_ipc._uid"):
                fixture_uid = patch(module, return_value=0)
                fixture_uid.start()
                self.addCleanup(fixture_uid.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.parent = Path(tempfile.mkdtemp(prefix="veraos-unkeyed-hostile-",
                                            dir=native_home))
        self.addCleanup(shutil.rmtree, self.parent)
        self.root = self.parent / "pilot"
        with Pilot.init(self.root):
            pass

    def test_same_linux_uid_is_not_an_independent_session_authority(self) -> None:
        with Pilot(self.root) as first:
            task_id = first.submit("inspect", "owned.txt")
        # A different Pilot object with the same UID can cancel the task
        # despite no Windows subject/session, consent, or admission grant.
        with Pilot(self.root) as second:
            self.assertEqual(second.cancel(task_id), "CANCELLED")
            self.assertEqual(second.db.execute(
                "SELECT status FROM tasks WHERE task_id=?", (task_id,)
            ).fetchone(), ("CANCELLED",))

    @unittest.expectedFailure
    def test_desired_whole_state_checkpoint_sees_legacy_unkeyed_submit(self) -> None:
        """Desired future contract: unkeyed task/state changes must be visible.

        Current keyed mapping-only checkpoint is unchanged by this operation;
        the failure is a known HOLD gate, not a qualifying PASS.
        """
        with Pilot(self.root) as pilot:
            first = wsl_ipc._dispatch(pilot, {
                "action": "submit", "worker": "inspect", "filename": "one.txt",
                "request_id": "a" * 32,
            })["task_id"]
            before = wsl_ipc._keyed_ledger_digest(pilot.db)
            second = wsl_ipc._dispatch(pilot, {
                "action": "submit", "worker": "inspect", "filename": "two.txt",
            })["task_id"]
            after = wsl_ipc._keyed_ledger_digest(pilot.db)
            self.assertNotEqual(first, second)
            self.assertEqual(pilot.db.execute("SELECT COUNT(*) FROM tasks").fetchone(), (2,))
            self.assertEqual(pilot.db.execute("SELECT COUNT(*) FROM ipc_submissions").fetchone(), (1,))
            # This intentionally fails today; a trusted all-event witness or
            # strict disabled-legacy path must close the gap.
            self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
