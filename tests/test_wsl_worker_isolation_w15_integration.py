"""Wave 15 DEV-pilot integration regressions; never an OS isolation proof.

The subprocess workers retain the coordinator's UID. All assertions below
concern local source admission and SQLite receipts, not Linux/Windows security
boundaries, Windows SID admission, a trusted issuer, or protected effects.
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

from veraos.worker_execution_gate import (  # noqa: E402
    DEV_SUBPROCESS_FIXTURE, assess_worker_execution,
)
from veraos.wsl_pilot import Pilot, PilotError  # noqa: E402


@unittest.skipUnless(os.name == "posix", "Linux/POSIX DEV pilot only")
class IsolationGatePilotIntegration(unittest.TestCase):
    def setUp(self) -> None:
        if os.geteuid() == 0:
            # Root CI is not equivalent to a real unprivileged WSL probe.
            mocked = patch("veraos.wsl_pilot._uid", return_value=0)
            mocked.start()
            self.addCleanup(mocked.stop)
        home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                if "microsoft" in os.uname().release.lower() else None)
        top = Path(tempfile.mkdtemp(prefix="veraos-w15-gate-", dir=home))
        self.addCleanup(shutil.rmtree, top)
        self.root = top / "pilot"
        with Pilot.init(self.root):
            pass
        (self.root / "input" / "sample.txt").write_bytes(b"wave-15 fixture\n")

    @staticmethod
    def _forged_isolation() -> object:
        class ForgedReport:
            def __bool__(self):
                raise AssertionError("untrusted isolation report was evaluated")

            def __getitem__(self, key):
                raise AssertionError(f"untrusted evidence was accessed: {key}")

        return ForgedReport()

    def test_forged_isolation_never_promotes_source_admission(self) -> None:
        report = self._forged_isolation()
        for operation, effects in (
            ("production-worker", ()),
            ("protected-effect", ("merge",)),
            (DEV_SUBPROCESS_FIXTURE, ("network",)),
        ):
            with self.subTest(operation=operation):
                verdict = assess_worker_execution(
                    operation=operation, requested_effects=effects,
                    claimed_isolation_evidence=report)
                self.assertFalse(verdict.dev_fixture_allowed)
                self.assertEqual(verdict.production_worker_isolation, "HOLD")
                self.assertEqual(verdict.protected_effects, "DENIED")
        dev = assess_worker_execution(
            operation=DEV_SUBPROCESS_FIXTURE,
            claimed_isolation_evidence=report)
        self.assertTrue(dev.dev_fixture_allowed)
        self.assertEqual(dev.production_worker_isolation, "HOLD")
        self.assertEqual(dev.protected_effects, "DENIED")

    def test_dev_child_does_not_inherit_synthetic_host_environment(self) -> None:
        # This tests explicit env={} hygiene, not same-UID filesystem denial.
        with patch.dict(os.environ, {
            "VERAOS_W15_SYNTHETIC_SECRET": "must-not-reach-child",
            "WSL_INTEROP": "untrusted-fake-socket",
        }):
            with Pilot(self.root) as pilot:
                result = pilot._run_data_scoped_child("inspect", b"5")
        self.assertEqual(result["size"], 5)
        self.assertTrue(set(result["env_keys"]).issubset({"LC_CTYPE"}))
        self.assertNotIn("VERAOS_W15_SYNTHETIC_SECRET", result["env_keys"])
        self.assertNotIn("WSL_INTEROP", result["env_keys"])

    def test_disallowed_execution_does_not_claim_and_restart_keeps_queue(self) -> None:
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("inspect", "sample.txt")
            for intent in ("production-worker", "isolated", "protected-effect"):
                with self.subTest(intent=intent):
                    with self.assertRaisesRegex(PilotError, "development fixture only"):
                        pilot.run_dev_process(task_id, execution_mode=intent)
            self.assertFalse(pilot.protected_effect("merge", task_id=task_id))
        with Pilot(self.root) as restarted:
            self.assertEqual(restarted.recover(), 0)
            self.assertEqual(restarted.snapshot()["tasks"][0]["status"], "QUEUED")
            events = restarted.snapshot()["events"]
            self.assertEqual([entry["code"] for entry in events],
                             ["SUBMITTED", "WORKER_ISOLATION_DENIED",
                              "WORKER_ISOLATION_DENIED", "WORKER_ISOLATION_DENIED",
                              "PROTECTED_EFFECT_DENIED"])
            for event in events[1:]:
                self.assertIsNone(event["task_id"])
                self.assertIsNone(json.loads(event["detail"])["authenticated_principal_id"])
            self.assertIsNone(events[-1]["task_id"])
            self.assertIsNone(json.loads(events[-1]["detail"])["authenticated_principal_id"])

    def test_two_dev_workers_and_unbound_effect_denial_survive_restart(self) -> None:
        with Pilot(self.root) as pilot:
            inspect_id = pilot.submit("inspect", "sample.txt")
            digest_id = pilot.submit("digest", "sample.txt")
            self.assertEqual(pilot.run_dev_process(inspect_id), "COMPLETED")
            self.assertEqual(pilot.run_dev_process(digest_id), "COMPLETED")
            self.assertFalse(pilot.protected_effect("merge", task_id=digest_id))
        derived = self.root / "derived" / (digest_id + ".sha256")
        expected = hashlib.sha256(b"wave-15 fixture\n").hexdigest() + "\n"
        self.assertEqual(derived.read_text(encoding="ascii"), expected)
        with Pilot(self.root) as restarted:
            self.assertEqual(restarted.recover(), 0)
            self.assertEqual([task["status"] for task in restarted.snapshot()["tasks"]],
                             ["COMPLETED", "COMPLETED"])
            with self.assertRaises(PilotError):
                restarted.run_dev_process(digest_id)
            events = restarted.snapshot()["events"]
            denials = [entry for entry in events
                       if entry["code"] == "PROTECTED_EFFECT_DENIED"]
            self.assertEqual(len(denials), 1)
            self.assertIsNone(denials[0]["task_id"])
            denial = json.loads(denials[0]["detail"])
            self.assertEqual(denial["asserted_task_id"], digest_id)
            self.assertIsNone(denial["authenticated_principal_id"])
            self.assertIsNone(denial["windows_ping_request_id"])
        self.assertEqual(derived.read_text(encoding="ascii"), expected)

    def test_failed_dev_worker_is_held_on_restart_without_output(self) -> None:
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("digest", "sample.txt")
            with patch.object(Pilot, "_run_data_scoped_child",
                              side_effect=PilotError("synthetic worker failure")):
                with self.assertRaisesRegex(PilotError, "synthetic worker failure"):
                    pilot.run_dev_process(task_id)
        with Pilot(self.root) as restarted:
            self.assertEqual(restarted.recover(), 0)
            self.assertEqual(restarted.snapshot()["tasks"][0]["status"],
                             "RECOVERY_HELD")
            self.assertEqual([event["code"] for event in restarted.snapshot()["events"]],
                             ["SUBMITTED", "CLAIMED", "WORKER_HELD"])
            with self.assertRaises(PilotError):
                restarted.run_dev_process(task_id)
        self.assertFalse(list((self.root / "derived").iterdir()))


if __name__ == "__main__":
    unittest.main()
