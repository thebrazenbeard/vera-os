"""Local-task-correlated *denial* receipts: no Windows identity admission.

This exercises a SQLite fixture only. A caller-supplied task ID is not a
credential, and these receipts never authorize or perform the effect.
"""
from __future__ import annotations

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


@unittest.skipUnless(os.name == "posix", "POSIX SQLite fixture required")
class DenialTaskReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.geteuid() == 0:
            uid_patch = patch("veraos.wsl_pilot._uid", return_value=0)
            uid_patch.start()
            self.addCleanup(uid_patch.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.parent = Path(tempfile.mkdtemp(prefix="veraos-local-denial-", dir=native_home))
        self.addCleanup(shutil.rmtree, self.parent)
        self.root = self.parent / "pilot"
        with Pilot.init(self.root):
            pass

    def test_existing_local_task_assertion_stays_unbound_to_authoritative_event(self) -> None:
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("inspect", "fixture.txt")
            self.assertIs(pilot.protected_effect("protected.merge", task_id=task_id), False)
            row = pilot.db.execute(
                "SELECT task_id, detail FROM events "
                "WHERE code='PROTECTED_EFFECT_DENIED'"
            ).fetchone()
            self.assertIsNone(row[0], "caller assertion must never populate authoritative task_id")
            detail = json.loads(row[1])
            self.assertEqual(detail, {
                "schema": "VERAOS_LOCAL_TASK_DENIAL_V1",
                "effect": "protected.merge",
                "association": "CALLER_ASSERTED_EXISTING_LOCAL_TASK",
                "asserted_task_id": task_id,
                "authenticated_principal_id": None,
                "windows_ping_request_id": None,
            })

    def test_unknown_local_task_still_does_not_execute_and_receipt_is_unbound(self) -> None:
        with Pilot(self.root) as pilot:
            self.assertIs(pilot.protected_effect("protected.merge", task_id="f" * 32), False)
            row = pilot.db.execute(
                "SELECT task_id, detail FROM events WHERE code='PROTECTED_EFFECT_DENIED'"
            ).fetchone()
        self.assertIsNone(row[0])
        detail = json.loads(row[1])
        self.assertEqual(detail["association"], "UNBOUND_UNKNOWN_LOCAL_TASK")
        self.assertIsNone(detail["asserted_task_id"])
        self.assertIsNone(detail["authenticated_principal_id"])
        self.assertIsNone(detail["windows_ping_request_id"])

    def test_separate_cli_process_can_emit_untrusted_assertion_only(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("real subprocess requires non-root WSL account")
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("inspect", "fixture.txt")
        proc = subprocess.run(
            [sys.executable, "-m", "veraos.wsl_pilot", "--root", str(self.root),
             "deny-effect", "protected.merge", "--task-id", task_id],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
            capture_output=True, text=True, check=False, timeout=8,
        )
        self.assertEqual((proc.returncode, json.loads(proc.stdout)), (0, {"allowed": False}))
        with Pilot(self.root) as pilot:
            row = pilot.db.execute(
                "SELECT task_id, detail FROM events WHERE code='PROTECTED_EFFECT_DENIED'"
            ).fetchone()
            self.assertIsNone(row[0])
            self.assertEqual(json.loads(row[1])["asserted_task_id"], task_id)
            self.assertIsNone(json.loads(row[1])["authenticated_principal_id"])

    def test_malformed_task_reference_rejected_without_attribution(self) -> None:
        with Pilot(self.root) as pilot:
            for task_ref in ("", "../other", "X" * 32, 123, None):
                with self.subTest(task_ref=task_ref):
                    if task_ref is None:
                        continue  # None intentionally retains legacy unbound behavior.
                    with self.assertRaises(PilotError):
                        pilot.protected_effect("protected.merge", task_id=task_ref)
            self.assertEqual(pilot.db.execute("SELECT count(*) FROM events").fetchone(), (0,))

    def test_legacy_unbound_denial_receipt_contract_is_preserved(self) -> None:
        with Pilot(self.root) as pilot:
            self.assertFalse(pilot.protected_effect("protected.merge"))
            row = pilot.db.execute(
                "SELECT task_id, detail FROM events WHERE code='PROTECTED_EFFECT_DENIED'"
            ).fetchone()
        self.assertEqual(row, (None, "protected.merge"))


if __name__ == "__main__":
    unittest.main()
