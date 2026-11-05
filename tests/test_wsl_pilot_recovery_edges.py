"""Hostile state/recovery regressions for the source-only VeraOS WSL pilot.

Fresh tests use separate SQLite clients and private temporary fixtures. On a
root-only scratch runner the pilot's UID lookup is simulated as its actual
filesystem owner; this does not prove real cross-user isolation.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import pwd
import shutil
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos.wsl_pilot import Pilot, PilotError


@unittest.skipUnless(os.name == "posix", "requires Linux/POSIX filesystem semantics")
class StateRecoveryEdges(unittest.TestCase):
    def setUp(self) -> None:
        if os.geteuid() == 0:
            uid_stub = patch("veraos.wsl_pilot._uid", return_value=0)
            uid_stub.start()
            self.addCleanup(uid_stub.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        outer = Path(tempfile.mkdtemp(prefix="veraos-recovery-edge-", dir=native_home))
        self.addCleanup(shutil.rmtree, outer)
        self.root = outer / "state"
        with Pilot.init(self.root):
            pass
        (self.root / "input" / "known.txt").write_bytes(b"recovery-edge\n")

    def _events(self, task_id: str) -> list[str]:
        with Pilot(self.root) as pilot:
            return [event["code"] for event in pilot.snapshot()["events"]
                    if event["task_id"] == task_id]

    def _status(self, task_id: str) -> str:
        with Pilot(self.root) as pilot:
            return next(task["status"] for task in pilot.snapshot()["tasks"]
                        if task["task_id"] == task_id)

    def test_claim_event_failure_rolls_back_both_claim_and_receipt(self) -> None:
        with Pilot(self.root) as client:
            task = client.submit("digest", "known.txt")
            # Force the event insert to fail after the task's UPDATE.
            with patch.object(client, "_event", side_effect=sqlite3.IntegrityError("injected")):
                with self.assertRaises(sqlite3.IntegrityError):
                    client.claim(task)
        self.assertEqual(self._status(task), "QUEUED")
        self.assertEqual(self._events(task), ["SUBMITTED"])
        with Pilot(self.root) as later:
            self.assertTrue(later.claim(task))
        self.assertEqual(self._events(task), ["SUBMITTED", "CLAIMED"])

    def test_many_competing_sqlite_clients_claim_once_per_task(self) -> None:
        with Pilot(self.root) as owner:
            tasks = [owner.submit("inspect", "known.txt") for _ in range(24)]
        barrier = threading.Barrier(4)

        def contend(_: int) -> list[bool]:
            with Pilot(self.root) as other:
                barrier.wait(timeout=5)
                return [other.claim(task) for task in tasks]

        with ThreadPoolExecutor(max_workers=4) as workers:
            results = list(workers.map(contend, range(4)))
        for index, task in enumerate(tasks):
            self.assertEqual(sum(result[index] for result in results), 1, task)
            self.assertEqual(self._events(task).count("CLAIMED"), 1)
        with Pilot(self.root) as owner:
            self.assertEqual(owner.recover(), len(tasks))
            self.assertEqual(owner.recover(), 0)
        for task in tasks:
            self.assertEqual(self._status(task), "RECOVERY_HELD")
            self.assertEqual(self._events(task).count("RECOVERY_HELD"), 1)

    def test_recover_refuses_while_a_live_worker_holds_lease(self) -> None:
        with Pilot(self.root) as worker, Pilot(self.root) as recovery:
            task = worker.submit("inspect", "known.txt")
            with worker._worker_lease(exclusive=False):
                self.assertTrue(worker.claim(task))
                with self.assertRaises(PilotError):
                    recovery.recover()
                self.assertEqual(self._status(task), "RUNNING")
            self.assertEqual(recovery.recover(), 1)
            self.assertEqual(recovery.recover(), 0)
        self.assertEqual(self._events(task), ["SUBMITTED", "CLAIMED", "RECOVERY_HELD"])

    def test_cancel_between_input_and_output_writes_nothing(self) -> None:
        with Pilot(self.root) as runner, Pilot(self.root) as canceller:
            task = runner.submit("digest", "known.txt")
            original = runner._input

            def cancel_after_read(filename: str, *, read: bool) -> int | bytes:
                result = original(filename, read=read)
                self.assertEqual(canceller.cancel(task), "CANCEL_REQUESTED")
                return result

            with patch.object(runner, "_input", side_effect=cancel_after_read):
                self.assertEqual(runner.run(task), "CANCELLED")
        self.assertEqual(self._events(task),
                         ["SUBMITTED", "CLAIMED", "CANCEL_REQUESTED", "CANCELLED"])
        self.assertFalse((self.root / "derived" / (task + ".sha256")).exists())

    def test_cancel_after_output_requires_manual_reconciliation(self) -> None:
        with Pilot(self.root) as runner, Pilot(self.root) as canceller:
            task = runner.submit("digest", "known.txt")
            original = runner._derive

            def cancel_after_write(task_id: str, digest: str) -> None:
                original(task_id, digest)
                self.assertEqual(canceller.cancel(task), "CANCEL_REQUESTED")

            with patch.object(runner, "_derive", side_effect=cancel_after_write):
                self.assertEqual(runner.run(task), "RECOVERY_HELD")
        file = self.root / "derived" / (task + ".sha256")
        self.assertEqual(file.read_text(encoding="ascii"),
                         hashlib.sha256(b"recovery-edge\n").hexdigest() + "\n")
        self.assertEqual(self._events(task), [
            "SUBMITTED", "CLAIMED", "OUTPUT_INTENT", "CANCEL_REQUESTED", "RECOVERY_HELD"])
        with Pilot(self.root) as later:
            self.assertEqual(later.recover(), 0)
            with self.assertRaises(PilotError):
                later.run(task)
        self.assertEqual(self._status(task), "RECOVERY_HELD")

    def test_interrupted_intent_and_existing_file_never_replayed(self) -> None:
        with Pilot(self.root) as first:
            task = first.submit("digest", "known.txt")
            self.assertTrue(first.claim(task))
            first._derive(task, "7" * 64)
        file = self.root / "derived" / (task + ".sha256")
        self.assertEqual(file.read_text(encoding="ascii"), "7" * 64 + "\n")
        with Pilot(self.root) as restarted:
            self.assertEqual(restarted.recover(), 1)
            with self.assertRaises(PilotError):
                restarted.run(task)
            self.assertEqual(restarted.recover(), 0)
        self.assertEqual(self._events(task),
                         ["SUBMITTED", "CLAIMED", "OUTPUT_INTENT", "RECOVERY_HELD"])
        self.assertEqual(file.read_text(encoding="ascii"), "7" * 64 + "\n")

    def test_preexisting_output_causes_held_and_keeps_old_bytes(self) -> None:
        with Pilot(self.root) as first:
            task = first.submit("digest", "known.txt")
            path = self.root / "derived" / (task + ".sha256")
            path.write_text("DO-NOT-CLOBBER\n", encoding="ascii")
            with self.assertRaises(FileExistsError):
                first.run(task)
        self.assertEqual(path.read_text(encoding="ascii"), "DO-NOT-CLOBBER\n")
        self.assertEqual(self._status(task), "RECOVERY_HELD")
        self.assertEqual(self._events(task),
                         ["SUBMITTED", "CLAIMED", "OUTPUT_INTENT", "WORKER_HELD"])

    def test_recovery_is_targeted_and_does_not_claim_other_tasks(self) -> None:
        with Pilot(self.root) as first, Pilot(self.root) as second:
            active = first.submit("digest", "known.txt")
            waiting = first.submit("inspect", "known.txt")
            canceled = first.submit("digest", "known.txt")
            self.assertTrue(first.claim(active))
            self.assertEqual(second.cancel(canceled), "CANCELLED")
        with Pilot(self.root) as restarted:
            self.assertEqual(restarted.recover(), 1)
            self.assertEqual(restarted.run(waiting), "COMPLETED")
        self.assertEqual(self._status(active), "RECOVERY_HELD")
        self.assertEqual(self._status(waiting), "COMPLETED")
        self.assertEqual(self._status(canceled), "CANCELLED")
        self.assertEqual(self._events(canceled), ["SUBMITTED", "CANCELLED"])


if __name__ == "__main__":
    unittest.main()
