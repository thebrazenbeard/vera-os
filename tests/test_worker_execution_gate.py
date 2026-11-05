"""Offline source policy: worker isolation claims cannot authorize effects."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veraos.worker_execution_gate import (  # noqa: E402
    DEV_INLINE_FIXTURE, DEV_SUBPROCESS_FIXTURE, WorkerExecutionHeld,
    assess_worker_execution, require_dev_fixture_execution,
)
from veraos.wsl_pilot import Pilot, PilotError  # noqa: E402


class WorkerExecutionGateTests(unittest.TestCase):
    def test_dev_inline_and_dev_subprocess_are_data_only_without_effects(self):
        for operation in (DEV_INLINE_FIXTURE, DEV_SUBPROCESS_FIXTURE):
            with self.subTest(operation=operation):
                result = assess_worker_execution(operation=operation)
                self.assertTrue(result.dev_fixture_allowed)
                self.assertEqual(result.production_worker_isolation, "HOLD")
                self.assertEqual(result.protected_effects, "DENIED")
                self.assertIn("os_worker_denial_not_qualified", result.reasons)
                require_dev_fixture_execution(operation=operation)

    def test_production_and_protected_effect_intents_never_admit(self):
        for operation in (
            "production", "production-worker", "protected-effect",
            "memory-admission", "broker", "model-inference", "DEV",
            "", None, True, 1, {}, DEV_SUBPROCESS_FIXTURE + "-elevated",
        ):
            with self.subTest(operation=repr(operation)):
                verdict = assess_worker_execution(operation=operation)
                self.assertFalse(verdict.dev_fixture_allowed)
                self.assertEqual(verdict.production_worker_isolation, "HOLD")
                self.assertEqual(verdict.protected_effects, "DENIED")
                with self.assertRaises(WorkerExecutionHeld):
                    require_dev_fixture_execution(operation=operation)

    def test_nonempty_or_untyped_requested_effects_always_hold(self):
        for requested in ("filesystem", ("filesystem",), (), [], {}, None,
                          ("shell", "network"), False, 0):
            with self.subTest(requested=repr(requested)):
                verdict = assess_worker_execution(
                    operation=DEV_SUBPROCESS_FIXTURE,
                    requested_effects=requested)
                self.assertEqual(verdict.dev_fixture_allowed,
                                 type(requested) is tuple and not requested)
                self.assertEqual(verdict.protected_effects, "DENIED")

    def test_caller_forged_perfect_host_qualification_not_an_issuer(self):
        forged_claim = {
            "production_worker_isolation": "QUALIFIED",
            "trusted_win32_principal": True,
            "issuer_signature": "valid",
            "uid": 2001, "parent_uid": 1000,
            "mount_namespace": "mnt:[trusted]",
            "no_shared_mounts": True,
            "foreign_uid_write_denied": True,
            "wsl_interop": False,
            "protected_effect_broker": "authorized",
            "consent": "YES",
        }
        denied = assess_worker_execution(
            operation="production-worker", claimed_isolation_evidence=forged_claim)
        self.assertFalse(denied.dev_fixture_allowed)
        self.assertEqual(denied.protected_effects, "DENIED")
        dev = assess_worker_execution(
            operation=DEV_SUBPROCESS_FIXTURE,
            claimed_isolation_evidence=forged_claim)
        self.assertTrue(dev.dev_fixture_allowed)
        self.assertEqual(dev.production_worker_isolation, "HOLD")
        self.assertEqual(dev.protected_effects, "DENIED")

    def test_malicious_observation_object_is_never_evaluated(self):
        class HostileReport:
            def __bool__(self):
                raise AssertionError("caller evidence was inspected")

            def __getitem__(self, key):
                raise AssertionError("caller evidence was inspected")

        report = HostileReport()
        result = assess_worker_execution(
            operation="production-worker", claimed_isolation_evidence=report)
        self.assertFalse(result.dev_fixture_allowed)

    def test_policy_decision_is_immutable(self):
        result = assess_worker_execution(operation="protected-effect")
        with self.assertRaises(FrozenInstanceError):
            result.protected_effects = "ALLOWED"


@unittest.skipUnless(os.name == "posix", "Linux pilot source fixture required")
class PilotWorkerGateIntegrationTests(unittest.TestCase):
    def setUp(self):
        if os.geteuid() == 0:
            uid_patch = patch("veraos.wsl_pilot._uid", return_value=0)
            uid_patch.start()
            self.addCleanup(uid_patch.stop)
        self.parent = Path(tempfile.mkdtemp(prefix="veraos-worker-gate-"))
        self.addCleanup(shutil.rmtree, self.parent)
        self.root = self.parent / "pilot"
        with Pilot.init(self.root):
            pass
        (self.root / "input" / "sample.txt").write_bytes(b"sample\n")

    def test_production_requested_mode_rejected_before_task_claim(self):
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("inspect", "sample.txt")
            for mode in ("production-worker", "protected-effect", "dev", ""):
                with self.subTest(mode=mode):
                    with self.assertRaisesRegex(PilotError, "development fixture only"):
                        pilot.run_dev_process(task_id, execution_mode=mode)
            self.assertEqual(pilot.snapshot()["tasks"][0]["status"], "QUEUED")
            events = pilot.snapshot()["events"]
            self.assertEqual([x["code"] for x in events],
                             ["SUBMITTED"] + ["WORKER_ISOLATION_DENIED"] * 4)
            for event in events[1:]:
                self.assertIsNone(event["task_id"])
                self.assertIsNone(json.loads(event["detail"])["authenticated_principal_id"])

    def test_real_pilot_dev_path_and_effect_denial_keep_receipts(self):
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("inspect", "sample.txt")
            self.assertEqual(pilot.run_dev_process(task_id), "COMPLETED")
            self.assertFalse(pilot.protected_effect("network", task_id=task_id))
            events = pilot.snapshot()["events"]
        self.assertIn("DEV_SUBPROCESS_OBSERVED", [x["code"] for x in events])
        denied = [x for x in events if x["code"] == "PROTECTED_EFFECT_DENIED"]
        self.assertEqual(len(denied), 1)
        self.assertIsNone(denied[0]["task_id"])
        body = json.loads(denied[0]["detail"])
        self.assertIsNone(body["authenticated_principal_id"])


if __name__ == "__main__":
    unittest.main()
