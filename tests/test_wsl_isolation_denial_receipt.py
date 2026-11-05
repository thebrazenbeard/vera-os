"""Persistence of DEV worker admission denials, not production authority proof.

These receipts are written by a same-UID SQLite caller. They must remain
unbound to an authoritative task/principal even when a valid local task ID is
asserted. Actual WSL/Windows isolation needs separate OS-level denial tests.
"""
from __future__ import annotations

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
from veraos.wsl_pilot import Pilot, PilotError  # noqa: E402


@unittest.skipUnless(os.name == "posix", "Linux/POSIX fixture only")
class IsolationDenialReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.geteuid() == 0:
            mock_uid = patch("veraos.wsl_pilot._uid", return_value=0)
            mock_uid.start()
            self.addCleanup(mock_uid.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.parent = Path(tempfile.mkdtemp(prefix="veraos-isolation-denial-",
                                            dir=native_home))
        self.addCleanup(shutil.rmtree, self.parent)
        self.root = self.parent / "pilot"
        with Pilot.init(self.root):
            pass

    def test_rejected_production_intent_receipt_survives_restart(self) -> None:
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("inspect", "sample.txt")
            with self.assertRaisesRegex(PilotError, "development fixture only"):
                pilot.run_dev_process(task_id, execution_mode="production-worker")
            self.assertEqual(pilot.snapshot()["tasks"][0]["status"], "QUEUED")
        # A new connection after coordinator restart observes the event; the
        # task is still QUEUED and no protected operation was performed.
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.recover(), 0)
            snapshot = pilot.snapshot()
        self.assertFalse(snapshot["production_authority"])
        self.assertEqual([e["code"] for e in snapshot["events"]],
                         ["SUBMITTED", "WORKER_ISOLATION_DENIED"])
        event = snapshot["events"][-1]
        self.assertIsNone(event["task_id"])
        detail = json.loads(event["detail"])
        self.assertEqual(detail["schema"], "VERAOS_LOCAL_ISOLATION_DENIAL_V1")
        self.assertEqual(detail["requested_execution_mode"], "production-worker")
        self.assertEqual(detail["association"], "CALLER_ASSERTED_EXISTING_LOCAL_TASK")
        self.assertEqual(detail["asserted_task_id"], task_id)
        self.assertEqual(detail["receipt_authority"], "SAME_UID_SQLITE_ONLY")
        self.assertEqual(detail["production_worker_isolation"], "HOLD")
        self.assertEqual(detail["protected_effects"], "DENIED")
        self.assertIsNone(detail["trusted_windows_issuer"])
        self.assertIsNone(detail["authenticated_principal_id"])

    def test_unknown_task_never_populates_foreign_key_or_identity(self) -> None:
        with Pilot(self.root) as pilot:
            with self.assertRaises(PilotError):
                pilot.run_dev_process("f" * 32, execution_mode="production-worker")
            event = pilot.snapshot()["events"][-1]
        self.assertIsNone(event["task_id"])
        detail = json.loads(event["detail"])
        self.assertEqual(detail["association"], "UNBOUND_UNKNOWN_LOCAL_TASK")
        self.assertIsNone(detail["asserted_task_id"])
        self.assertIsNone(detail["authenticated_principal_id"])

    def test_hostile_python_objects_not_evaluated_for_denial_logging(self) -> None:
        class Hostile:
            def __str__(self) -> str:
                raise AssertionError("untrusted __str__ evaluated")

            def __bool__(self) -> bool:
                raise AssertionError("untrusted __bool__ evaluated")

        with Pilot(self.root) as pilot:
            with self.assertRaises(PilotError):
                pilot.run_dev_process(Hostile(), execution_mode=Hostile())
            event = pilot.snapshot()["events"][-1]
        self.assertIsNone(event["task_id"])
        detail = json.loads(event["detail"])
        self.assertIsNone(detail["asserted_task_id"])
        self.assertIsNone(detail["requested_execution_mode"])


if __name__ == "__main__":
    unittest.main()
