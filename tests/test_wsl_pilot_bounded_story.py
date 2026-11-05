"""One bounded DEV pilot story across separate SQLite sessions.

This is a local TEST, not a Windows SID, independent-principal, or deployment
probe. It deliberately calls the Linux-UID test adapter directly instead of
pretending an AF_UNIX socket works in every test sandbox. The two worker
subprocesses also retain the parent Linux UID and mount privileges.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veraos.wsl_ipc import _dispatch
from veraos.wsl_pilot import Pilot, PilotError


@unittest.skipUnless(os.name == "posix", "disposable Linux/POSIX pilot only")
class BoundedStoryTests(unittest.TestCase):
    def setUp(self) -> None:
        # Container CI may run as uid 0. This only simulates the UID lookup
        # for fixture setup; it must not be reported as a real unprivileged
        # WSL host test or used as a production authorization bypass.
        if os.geteuid() == 0:
            for name in ("veraos.wsl_pilot._uid", "veraos.wsl_ipc._uid"):
                mocked = patch(name, return_value=0)
                mocked.start()
                self.addCleanup(mocked.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        top = Path(tempfile.mkdtemp(prefix="veraos-bounded-story-", dir=native_home))
        self.addCleanup(shutil.rmtree, top)
        self.root = top / "state"
        with Pilot.init(self.root):
            pass
        (self.root / "input" / "sample.txt").write_bytes(b"bounded story\n")

    @staticmethod
    def submit(pilot: Pilot, key: str, worker: str = "inspect") -> str:
        return _dispatch(pilot, {
            "action": "submit", "worker": worker,
            "filename": "sample.txt", "request_id": key * 32,
        })["task_id"]

    def test_two_scoped_workers_cancellation_denial_and_recovery_survive_restart(self) -> None:
        # Session 1: four durable task IDs, including retried duplicate submit.
        with Pilot(self.root) as pilot:
            inspect_id = self.submit(pilot, "a")
            digest_id = self.submit(pilot, "b", "digest")
            cancelled_id = self.submit(pilot, "c")
            interrupted_id = self.submit(pilot, "d", "digest")
            self.assertEqual(self.submit(pilot, "a"), inspect_id)
            self.assertEqual(len(pilot.snapshot()["tasks"]), 4)
            self.assertEqual(len(pilot.snapshot()["events"]), 4)

        # Session 2: two actual restricted-data child processes, not OS
        # security sandboxes. Cancellation must not prevent other work.
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.run_dev_process(inspect_id), "COMPLETED")
            self.assertEqual(pilot.run_dev_process(digest_id), "COMPLETED")
            self.assertEqual(pilot.cancel(cancelled_id), "CANCELLED")
            self.assertTrue(pilot.claim(interrupted_id))
            self.assertEqual(pilot.cancel(interrupted_id), "CANCEL_REQUESTED")
            self.assertIs(pilot.protected_effect("merge", task_id=inspect_id), False)

        # Session 3 represents coordinator restart. Recovery holds ambiguous
        # in-flight work and never regenerates its output after cancellation.
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.recover(), 1)
            self.assertEqual(pilot.recover(), 0)
            with self.assertRaises(PilotError):
                pilot.run(interrupted_id)
            for key, worker, expected in (
                ("a", "inspect", inspect_id),
                ("b", "digest", digest_id),
                ("c", "inspect", cancelled_id),
                ("d", "digest", interrupted_id),
            ):
                self.assertEqual(self.submit(pilot, key, worker), expected)
            before_conflict = pilot.snapshot()
            with self.assertRaises(PilotError):
                self.submit(pilot, "a", "digest")
            self.assertEqual(pilot.snapshot(), before_conflict)

            snapshot = pilot.snapshot()
            status = {task["task_id"]: task["status"] for task in snapshot["tasks"]}
            self.assertEqual(status, {
                inspect_id: "COMPLETED", digest_id: "COMPLETED",
                cancelled_id: "CANCELLED", interrupted_id: "RECOVERY_HELD",
            })
            self.assertFalse(snapshot["production_authority"])
            self.assertFalse(snapshot["model_inference"])
            self.assertEqual(len(snapshot["events"]), 16)

            def codes(task_id: str) -> list[str]:
                return [e["code"] for e in snapshot["events"] if e["task_id"] == task_id]

            self.assertEqual(codes(inspect_id), [
                "SUBMITTED", "CLAIMED", "DEV_SUBPROCESS_OBSERVED", "COMPLETED",
            ])
            self.assertEqual(codes(digest_id), [
                "SUBMITTED", "CLAIMED", "DEV_SUBPROCESS_OBSERVED",
                "OUTPUT_INTENT", "COMPLETED",
            ])
            self.assertEqual(codes(cancelled_id), ["SUBMITTED", "CANCELLED"])
            self.assertEqual(codes(interrupted_id), [
                "SUBMITTED", "CLAIMED", "CANCEL_REQUESTED", "RECOVERY_HELD",
            ])
            denials = [e for e in snapshot["events"]
                       if e["code"] == "PROTECTED_EFFECT_DENIED"]
            self.assertEqual(len(denials), 1)
            self.assertIsNone(denials[0]["task_id"])
            payload = json.loads(denials[0]["detail"])
            self.assertEqual(payload["asserted_task_id"], inspect_id)
            self.assertEqual(payload["effect"], "merge")
            self.assertIsNone(payload["authenticated_principal_id"])
            self.assertIsNone(payload["windows_ping_request_id"])

        digest_output = self.root / "derived" / (digest_id + ".sha256")
        self.assertEqual(digest_output.read_text(encoding="ascii"),
                         hashlib.sha256(b"bounded story\n").hexdigest() + "\n")
        self.assertEqual([p.name for p in (self.root / "derived").iterdir()],
                         [digest_output.name])


if __name__ == "__main__":
    unittest.main()
