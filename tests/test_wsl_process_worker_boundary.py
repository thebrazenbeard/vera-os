"""Opt-in same-UID subprocess data-boundary tests for the WSL pilot.

Real child processes are used, but no OS account/namespace/ACL boundary is
created. A passing test is NOT worker isolation or an effect authority grant.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos.wsl_pilot import Pilot, PilotError  # noqa: E402


@unittest.skipUnless(os.name == "posix", "POSIX subprocess fixture required")
class DataScopedProcessWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        # Root test runners can characterize source behavior with a mocked
        # Pilot UID, but that is never a qualified host-identity observation.
        if os.geteuid() == 0:
            uid_patch = patch("veraos.wsl_pilot._uid", return_value=0)
            uid_patch.start()
            self.addCleanup(uid_patch.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.parent = Path(tempfile.mkdtemp(prefix="veraos-process-data-", dir=native_home))
        self.addCleanup(shutil.rmtree, self.parent)
        self.root = self.parent / "pilot"
        with Pilot.init(self.root):
            pass
        (self.root / "input" / "sample.txt").write_bytes(b"sample\n")

    def test_two_real_children_process_different_bounded_inputs(self) -> None:
        with patch.dict(os.environ, {"VERAOS_TEST_ONLY_AMBIENT_SECRET": "never-inherit"}):
            with Pilot(self.root) as pilot:
                inspect_id = pilot.submit("inspect", "sample.txt")
                digest_id = pilot.submit("digest", "sample.txt")
                self.assertEqual(pilot.run_dev_process(inspect_id), "COMPLETED")
                self.assertEqual(pilot.run_dev_process(digest_id), "COMPLETED")
                receipts = pilot.snapshot()["events"]
        child_receipts = [x for x in receipts if x["code"] == "DEV_SUBPROCESS_OBSERVED"]
        self.assertEqual(len(child_receipts), 2)
        metadata = [json.loads(x["detail"]) for x in child_receipts]
        self.assertEqual([x["worker"] for x in metadata], ["inspect", "digest"])
        self.assertEqual([x["scope"] for x in metadata],
                         ["SAME_UID_DATA_ONLY", "SAME_UID_DATA_ONLY"])
        pids = [x["pid"] for x in metadata]
        self.assertNotEqual(pids[0], pids[1])
        self.assertNotIn(os.getpid(), pids)
        self.assertEqual(
            (self.root / "derived" / (digest_id + ".sha256")).read_text(encoding="ascii"),
            hashlib.sha256(b"sample\n").hexdigest() + "\n")
        self.assertFalse((self.root / "derived" / (inspect_id + ".sha256")).exists())
        self.assertEqual([x["detail"] for x in receipts if
                          x["task_id"] == inspect_id and x["code"] == "COMPLETED"],
                         ["bytes=7"])
        self.assertNotIn("VERAOS_TEST_ONLY_AMBIENT_SECRET", json.dumps(receipts))
        self.assertNotIn("never-inherit", json.dumps(receipts))

    def test_worker_child_receives_empty_ambient_env(self) -> None:
        with Pilot(self.root) as pilot:
            child = pilot._run_data_scoped_child("inspect", b"7")
            self.assertTrue(set(child["env_keys"]).issubset({"LC_CTYPE"}))
            self.assertEqual(child["size"], 7)
            self.assertNotEqual(child["pid"], os.getpid())
            with self.assertRaises(PilotError):
                pilot._run_data_scoped_child("digest", b"X" * 8193)
            with self.assertRaises(PilotError):
                pilot._run_data_scoped_child("unknown", b"7")

    def test_child_failure_holds_task_and_never_writes_output(self) -> None:
        with Pilot(self.root) as pilot:
            digest_id = pilot.submit("digest", "sample.txt")
            with patch.object(pilot, "_run_data_scoped_child",
                              side_effect=PilotError("fixture child unavailable")):
                with self.assertRaises(PilotError):
                    pilot.run_dev_process(digest_id)
            self.assertEqual(
                [x["status"] for x in pilot.snapshot()["tasks"] if
                 x["task_id"] == digest_id], ["RECOVERY_HELD"])
            self.assertEqual(
                [x["code"] for x in pilot.snapshot()["events"] if x["task_id"] == digest_id],
                ["SUBMITTED", "CLAIMED", "WORKER_HELD"])
        self.assertEqual(list((self.root / "derived").iterdir()), [])

    def test_spoofed_child_reported_pid_never_becomes_a_receipt(self) -> None:
        class SpoofedChild:
            pid = 51234  # Kernel-observed Popen value in this test double.
            returncode = 0

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def communicate(self, *, input, timeout):
                del input, timeout
                return (json.dumps({
                    "worker": "digest", "pid": 51235, "env_keys": ["LC_CTYPE"],
                    "sha256": hashlib.sha256(b"sample\n").hexdigest(),
                }).encode("utf-8"), b"")

        with Pilot(self.root) as pilot:
            task_id = pilot.submit("digest", "sample.txt")
            with patch("veraos.wsl_pilot.subprocess.Popen", return_value=SpoofedChild()):
                with self.assertRaisesRegex(PilotError, "provenance mismatch"):
                    pilot.run_dev_process(task_id)
            codes = [e["code"] for e in pilot.snapshot()["events"] if e["task_id"] == task_id]
            self.assertEqual(codes, ["SUBMITTED", "CLAIMED", "WORKER_HELD"])
            self.assertEqual(pilot.snapshot()["tasks"][0]["status"], "RECOVERY_HELD")
        self.assertEqual(list((self.root / "derived").iterdir()), [])

    @unittest.skipIf(os.geteuid() == 0,
                     "actual unprivileged CLI identity requires a real Linux UID")
    def test_separate_cli_process_runs_process_child_and_records_receipt(self) -> None:
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("inspect", "sample.txt")
        env = {**os.environ,
               "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        done = subprocess.run(
            [sys.executable, "-m", "veraos.wsl_pilot",
             "--root", str(self.root), "dev-run-process", task_id],
            env=env, capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {"status": "COMPLETED"})
        with Pilot(self.root) as pilot:
            events = [x for x in pilot.snapshot()["events"] if x["task_id"] == task_id]
        self.assertEqual([x["code"] for x in events],
                         ["SUBMITTED", "CLAIMED", "DEV_SUBPROCESS_OBSERVED", "COMPLETED"])


if __name__ == "__main__":
    unittest.main()
