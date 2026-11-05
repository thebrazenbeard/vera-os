"""Development-only proof of two real worker children and conservative restart.

This uses disposable SQLite state and fixed inspect/digest fixtures. Passing does
not mean the same-UID workers are OS-sandboxed or authorized to use effects.
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
from veraos.wsl_pilot import Pilot  # noqa: E402


@unittest.skipUnless(os.name == "posix", "Linux/WSL pilot only")
class TwoWorkerRestartReceiptsTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.geteuid() == 0:
            # Local-root Python is never an unprivileged host verification.
            uid_patch = patch("veraos.wsl_pilot._uid", return_value=0)
            uid_patch.start()
            self.addCleanup(uid_patch.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.parent = Path(tempfile.mkdtemp(prefix="veraos-two-worker-", dir=native_home))
        self.addCleanup(shutil.rmtree, self.parent)
        self.root = self.parent / "pilot"
        with Pilot.init(self.root):
            pass
        (self.root / "input" / "sample.txt").write_bytes(b"bounded sample\n")

    def _cli(self, command: str, *args: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ,
               "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
               "VERAOS_TEST_ONLY_SECRET": "should-never-reach-a-worker"}
        return subprocess.run(
            [sys.executable, "-m", "veraos.wsl_pilot", "--root", str(self.root),
             command, *args], env=env, capture_output=True, text=True,
            check=False, timeout=20,
        )

    def test_in_process_two_fixed_children_receipts_survive_reopen(self) -> None:
        with patch.dict(os.environ, {"VERAOS_TEST_ONLY_SECRET": "never-inherit"}):
            with Pilot(self.root) as pilot:
                inspect_id = pilot.submit("inspect", "sample.txt")
                digest_id = pilot.submit("digest", "sample.txt")
                cancelled_id = pilot.submit("digest", "sample.txt")
                self.assertEqual(pilot.run_dev_process(inspect_id), "COMPLETED")
                self.assertEqual(pilot.run_dev_process(digest_id), "COMPLETED")
                self.assertEqual(pilot.cancel(cancelled_id), "CANCELLED")

        # Fresh SQLite connection is the restart boundary; no state in memory
        # supplies these assertions.
        with Pilot(self.root) as fresh:
            self.assertEqual(fresh.recover(), 0)
            snapshot = fresh.snapshot()
        statuses = {t["task_id"]: t["status"] for t in snapshot["tasks"]}
        self.assertEqual(statuses, {
            inspect_id: "COMPLETED", digest_id: "COMPLETED",
            cancelled_id: "CANCELLED"})
        observed = [e for e in snapshot["events"]
                    if e["code"] == "DEV_SUBPROCESS_OBSERVED"]
        self.assertEqual({e["task_id"] for e in observed}, {inspect_id, digest_id})
        child_pids = [json.loads(e["detail"])["pid"] for e in observed]
        self.assertEqual(len(set(child_pids)), 2)
        self.assertNotIn(os.getpid(), child_pids)
        self.assertEqual({json.loads(e["detail"])["scope"] for e in observed},
                         {"SAME_UID_DATA_ONLY"})
        self.assertEqual(
            (self.root / "derived" / (digest_id + ".sha256")).read_text("ascii"),
            hashlib.sha256(b"bounded sample\n").hexdigest() + "\n")
        self.assertEqual([p.name for p in (self.root / "derived").iterdir()],
                         [digest_id + ".sha256"])
        self.assertNotIn("VERAOS_TEST_ONLY_SECRET", json.dumps(snapshot))
        self.assertNotIn("never-inherit", json.dumps(snapshot))

    @unittest.skipIf(os.geteuid() == 0,
                     "actual CLI/restart owner identity requires non-root Linux UID")
    def test_two_distinct_cli_invocations_persist_through_fresh_cli_status(self) -> None:
        with Pilot(self.root) as pilot:
            inspect_id = pilot.submit("inspect", "sample.txt")
            digest_id = pilot.submit("digest", "sample.txt")
            cancelled_id = pilot.submit("inspect", "sample.txt")
        for task_id in (inspect_id, digest_id):
            done = self._cli("dev-run-process", task_id)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(json.loads(done.stdout), {"status": "COMPLETED"})
        cancelled = self._cli("cancel", cancelled_id)
        self.assertEqual(cancelled.returncode, 0, cancelled.stderr)
        self.assertEqual(json.loads(cancelled.stdout), {"status": "CANCELLED"})
        reopened = self._cli("status")
        self.assertEqual(reopened.returncode, 0, reopened.stderr)
        snapshot = json.loads(reopened.stdout)
        self.assertFalse(snapshot["production_authority"])
        self.assertFalse(snapshot["model_inference"])
        self.assertEqual({t["task_id"]: t["status"] for t in snapshot["tasks"]}, {
            inspect_id: "COMPLETED", digest_id: "COMPLETED",
            cancelled_id: "CANCELLED"})
        evidence = [json.loads(e["detail"]) for e in snapshot["events"]
                    if e["code"] == "DEV_SUBPROCESS_OBSERVED"]
        self.assertEqual([e["worker"] for e in evidence], ["inspect", "digest"])
        self.assertEqual(len({e["pid"] for e in evidence}), 2)
        self.assertEqual({e["scope"] for e in evidence}, {"SAME_UID_DATA_ONLY"})
        self.assertNotIn("should-never-reach-a-worker", json.dumps(snapshot))

    @unittest.skipIf(os.geteuid() == 0,
                     "abrupt process death/recovery requires real non-root Linux UID")
    def test_crashed_claim_is_held_across_restarted_coordinator(self) -> None:
        with Pilot(self.root) as pilot:
            interrupted_id = pilot.submit("digest", "sample.txt")
            cancelled_id = pilot.submit("digest", "sample.txt")
        # A distinct coordinator PID claims and exits abruptly before effects;
        # no mocked database state or synthetic recovery marker is involved.
        code = (
            "import os,sys; from pathlib import Path; "
            "from veraos.wsl_pilot import Pilot; "
            "p=Pilot(Path(sys.argv[1])); "
            "assert p.claim(sys.argv[2]); os._exit(41)"
        )
        process = subprocess.run(
            [sys.executable, "-c", code, str(self.root), interrupted_id],
            env={**os.environ,
                 "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
            capture_output=True, text=True, check=False, timeout=10,
        )
        self.assertEqual(process.returncode, 41, process.stderr)
        before = self._cli("status")
        self.assertEqual(before.returncode, 0, before.stderr)
        before_tasks = {t["task_id"]: t["status"]
                        for t in json.loads(before.stdout)["tasks"]}
        self.assertEqual(before_tasks[interrupted_id], "RUNNING")
        self.assertEqual(self._cli("cancel", cancelled_id).returncode, 0)

        recovered = self._cli("recover")
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual(json.loads(recovered.stdout), {"recovery_held": 1})
        refused = self._cli("dev-run-process", interrupted_id)
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(json.loads(refused.stderr)["result"], "HELD")
        after = self._cli("status")
        self.assertEqual(after.returncode, 0, after.stderr)
        snapshot = json.loads(after.stdout)
        statuses = {t["task_id"]: t["status"] for t in snapshot["tasks"]}
        self.assertEqual(statuses[interrupted_id], "RECOVERY_HELD")
        self.assertEqual(statuses[cancelled_id], "CANCELLED")
        interrupted_codes = [e["code"] for e in snapshot["events"]
                             if e["task_id"] == interrupted_id]
        self.assertEqual(interrupted_codes,
                         ["SUBMITTED", "CLAIMED", "RECOVERY_HELD"])
        self.assertFalse(list((self.root / "derived").iterdir()))


if __name__ == "__main__":
    unittest.main()
