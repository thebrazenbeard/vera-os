"""Real POSIX/SQLite contract tests for the opt-in WSL2 pilot.

Run as an unprivileged Linux user. These tests create only private temporary
directories and never start a daemon, load a model, or touch Windows mounts.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos.wsl_pilot import MAX_INPUT_BYTES, Pilot, PilotError, SCHEMA


@unittest.skipUnless(os.name == "posix", "WSL pilot requires POSIX Linux")
class WSLLocalPilotTests(unittest.TestCase):
    def setUp(self) -> None:
        # The isolated scratch runner can be uid 0 without privilege to use
        # runuser. In that environment simulate only the Pilot's UID lookup;
        # real subprocess/credential tests must run non-root on Lappy WSL.
        if os.geteuid() == 0:
            simulated = patch("veraos.wsl_pilot._uid", return_value=0)
            simulated.start()
            self.addCleanup(simulated.stop)
        # Real WSL uses a tmpfs at /tmp; put tests on Linux-native home ext4
        # to exercise actual process restart against disk-backed state.
        test_parent = Path.home() if "microsoft" in os.uname().release.lower() else None
        top = Path(tempfile.mkdtemp(prefix="veraos-wsl-test-", dir=test_parent))
        self.addCleanup(shutil.rmtree, top)
        self.root = top / "pilot"
        with Pilot.init(self.root):
            pass
        (self.root / "input" / "sample.txt").write_bytes(b"sample\n")

    def _status(self, task_id: str) -> str:
        with Pilot(self.root) as pilot:
            row = [r for r in pilot.snapshot()["tasks"] if r["task_id"] == task_id]
            self.assertEqual(len(row), 1)
            return row[0]["status"]

    def _cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        return subprocess.run(
            [sys.executable, "-m", "veraos.wsl_pilot", "--root", str(self.root), *args],
            env=env, capture_output=True, text=True, check=False, timeout=5,
        )

    def test_private_linux_state_and_os_user_binding(self) -> None:
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.root / "pilot.sqlite3").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.root / "pilot.lock").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.root / "derived").stat().st_mode), 0o700)
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.snapshot()["schema"], SCHEMA)
        with patch("veraos.wsl_pilot._uid", return_value=os.geteuid() + 1):
            with self.assertRaises(PilotError):
                Pilot(self.root)
        with self.assertRaises(FileExistsError):
            Pilot.init(self.root)

    def test_inspector_and_digest_are_real_different_scoped_workers(self) -> None:
        with Pilot(self.root) as pilot:
            inspect_id = pilot.submit("inspect", "sample.txt")
            digest_id = pilot.submit("digest", "sample.txt")
            self.assertEqual(pilot.run(inspect_id), "COMPLETED")
            self.assertEqual(pilot.run(digest_id), "COMPLETED")
            result = pilot.snapshot()
        expected_sha = hashlib.sha256(b"sample\n").hexdigest()
        output = self.root / "derived" / (digest_id + ".sha256")
        self.assertEqual(output.read_text(encoding="ascii"), expected_sha + "\n")
        self.assertFalse((self.root / "derived" / (inspect_id + ".sha256")).exists())
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        self.assertEqual([r["status"] for r in result["tasks"]],
                         ["COMPLETED", "COMPLETED"])
        inspect_receipts = [r for r in result["events"] if r["task_id"] == inspect_id]
        self.assertEqual([r["code"] for r in inspect_receipts],
                         ["SUBMITTED", "CLAIMED", "COMPLETED"])
        self.assertEqual(inspect_receipts[-1]["detail"], "bytes=7")
        digest_receipts = [r["code"] for r in result["events"] if r["task_id"] == digest_id]
        self.assertEqual(digest_receipts,
                         ["SUBMITTED", "CLAIMED", "OUTPUT_INTENT", "COMPLETED"])
        self.assertNotIn("sample\n", json.dumps(result))
        self.assertFalse(result["production_authority"])
        self.assertFalse(result["model_inference"])

    def test_cancellation_is_per_task_and_another_worker_continues(self) -> None:
        with Pilot(self.root) as pilot:
            canceled = pilot.submit("inspect", "sample.txt")
            continuing = pilot.submit("digest", "sample.txt")
            self.assertEqual(pilot.cancel(canceled), "CANCELLED")
            with self.assertRaises(PilotError):
                pilot.run(canceled)
            self.assertEqual(pilot.run(continuing), "COMPLETED")
            self.assertEqual(pilot.cancel(continuing), "COMPLETED")
        self.assertEqual(self._status(canceled), "CANCELLED")
        self.assertEqual(self._status(continuing), "COMPLETED")
        self.assertFalse((self.root / "derived" / (canceled + ".sha256")).exists())

    def test_cancel_claimed_work_and_recover_never_reexecutes_it(self) -> None:
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("digest", "sample.txt")
            self.assertTrue(pilot.claim(task_id))
            self.assertEqual(pilot.cancel(task_id), "CANCEL_REQUESTED")
            self.assertEqual(pilot.recover(), 1)
            self.assertEqual(pilot.recover(), 0)
            with self.assertRaises(PilotError):
                pilot.run(task_id)
        self.assertEqual(self._status(task_id), "RECOVERY_HELD")
        self.assertFalse((self.root / "derived" / (task_id + ".sha256")).exists())

    def test_windows_mount_is_not_an_allowed_state_root(self) -> None:
        # This is a validation test: no Windows drive is actually opened.
        with self.assertRaises(PilotError):
            Pilot(Path("/mnt/c/Users/anyone/veraos-pilot"))

    def test_state_root_rejects_symlinked_ancestor(self) -> None:
        # A /home-looking path must not silently resolve through a symlink.
        link = self.root.parent / "alias"
        link.symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(PilotError):
            Pilot.init(link / "new-pilot")
        self.assertFalse((self.root.parent / "new-pilot").exists())

    def test_spoofed_home_cannot_authorize_foreign_mount_device(self) -> None:
        foreign = Path("/dev/shm")
        if not foreign.exists() or foreign.stat().st_dev == Path.home().stat().st_dev:
            self.skipTest("no independent tmpfs device in this environment")
        # The previous baseline trusted HOME and would accept this mount.
        with patch.dict(os.environ, {"HOME": str(foreign)}), \
                patch("veraos.wsl_pilot.os.uname", return_value=SimpleNamespace(release="microsoft")):
            with self.assertRaises(PilotError):
                Pilot.init(foreign / "veraos-mount-check-never-create")

    def test_input_validation_rejects_traversal_and_ambient_files(self) -> None:
        with Pilot(self.root) as pilot:
            for name in ("../outside", "a/b", "..", "", " .", "x" * 100):
                with self.subTest(filename=name), self.assertRaises(PilotError):
                    pilot.submit("inspect", name)
            with self.assertRaises(PilotError):
                pilot.submit("shell", "sample.txt")
            with self.assertRaises(PilotError):
                pilot.protected_effect("../merge")
        target = self.root.parent / "outside.txt"
        target.write_text("private fixture", encoding="utf-8")
        (self.root / "input" / "linked.txt").symlink_to(target)
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("digest", "linked.txt")
            with self.assertRaises(OSError):
                pilot.run(task_id)
        self.assertEqual(self._status(task_id), "RECOVERY_HELD")
        self.assertFalse((self.root / "derived" / (task_id + ".sha256")).exists())

    def test_bounded_input_fails_closed_without_output(self) -> None:
        (self.root / "input" / "oversized.bin").write_bytes(b"X" * (MAX_INPUT_BYTES + 1))
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("digest", "oversized.bin")
            with self.assertRaises(PilotError):
                pilot.run(task_id)
        self.assertEqual(self._status(task_id), "RECOVERY_HELD")
        self.assertFalse((self.root / "derived" / (task_id + ".sha256")).exists())

    def test_default_denied_effect_has_durable_receipt_and_no_execution(self) -> None:
        with Pilot(self.root) as pilot:
            self.assertIs(pilot.protected_effect("merge"), False)
            self.assertIs(pilot.protected_effect("delete"), False)
            result = pilot.snapshot()
        denials = [e for e in result["events"] if e["code"] == "PROTECTED_EFFECT_DENIED"]
        self.assertEqual([e["detail"] for e in denials], ["merge", "delete"])
        self.assertEqual([e["task_id"] for e in denials], [None, None])
        self.assertEqual(list((self.root / "derived").iterdir()), [])

    def test_concurrent_atomic_claim_denies_second_runner(self) -> None:
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("digest", "sample.txt")
        gate = threading.Barrier(2)

        def attempt(_: int) -> bool:
            with Pilot(self.root) as other:
                gate.wait(timeout=5)
                return other.claim(task_id)

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(attempt, range(2)))
        self.assertEqual(sorted(results), [False, True])
        with Pilot(self.root) as pilot:
            events = [e["code"] for e in pilot.snapshot()["events"]]
        self.assertEqual(events.count("CLAIMED"), 1)
        self.assertEqual(self._status(task_id), "RUNNING")

    def test_cancel_during_output_held_and_recovery_refuses_live_worker(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("digest", "sample.txt")

        def worker() -> str:
            with Pilot(self.root) as pilot:
                actual = pilot._derive

                def held_derive(identifier: str, digest: str) -> None:
                    entered.set()
                    if not release.wait(5):
                        raise AssertionError("interleaving gate expired")
                    actual(identifier, digest)

                pilot._derive = held_derive
                return pilot.run(task_id)

        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(worker)
            self.assertTrue(entered.wait(5), "worker never reached output seam")
            try:
                with Pilot(self.root) as pilot:
                    self.assertEqual(pilot.cancel(task_id), "CANCEL_REQUESTED")
                    with self.assertRaises(PilotError):
                        pilot.recover()
            finally:
                release.set()
            self.assertEqual(result.result(timeout=5), "RECOVERY_HELD")

        self.assertEqual(self._status(task_id), "RECOVERY_HELD")
        self.assertTrue((self.root / "derived" / (task_id + ".sha256")).exists())
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.cancel(task_id), "RECOVERY_HELD")
            self.assertEqual(pilot.recover(), 0)
            self.assertEqual([e["code"] for e in pilot.snapshot()["events"]],
                             ["SUBMITTED", "CLAIMED", "CANCEL_REQUESTED", "OUTPUT_INTENT", "RECOVERY_HELD"])

    def test_completed_state_cannot_be_overwritten_by_cancel_or_recovery(self) -> None:
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("inspect", "sample.txt")
            self.assertEqual(pilot.run(task_id), "COMPLETED")
            self.assertEqual(pilot.cancel(task_id), "COMPLETED")
            self.assertEqual(pilot.recover(), 0)
            self.assertEqual([e["code"] for e in pilot.snapshot()["events"]],
                             ["SUBMITTED", "CLAIMED", "COMPLETED"])

    @unittest.skipIf(os.geteuid() == 0, "requires actual unprivileged OS identity")
    def test_real_subprocess_interruption_is_quarantined_on_restart(self) -> None:
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("digest", "sample.txt")
        code = (
            "import os,sys;from pathlib import Path;"
            "from veraos.wsl_pilot import Pilot;"
            "p=Pilot(Path(sys.argv[1]));"
            "assert p.claim(sys.argv[2]);"
            "p._derive(sys.argv[2],'0'*64);"
            "os._exit(17)"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        proc = subprocess.run([sys.executable, "-c", code, str(self.root), task_id],
                              env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(proc.returncode, 17, proc.stderr)
        file = self.root / "derived" / (task_id + ".sha256")
        self.assertEqual(file.read_text(encoding="ascii"), "0" * 64 + "\n")
        restarted = self._cli("recover")
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        self.assertEqual(json.loads(restarted.stdout), {"recovery_held": 1})
        self.assertEqual(self._status(task_id), "RECOVERY_HELD")
        self.assertEqual(self._cli("run", task_id).returncode, 2)
        with Pilot(self.root) as pilot:
            events = [e["code"] for e in pilot.snapshot()["events"]]
            self.assertEqual(events,
                             ["SUBMITTED", "CLAIMED", "OUTPUT_INTENT", "RECOVERY_HELD"])
        self.assertEqual(file.read_text(encoding="ascii"), "0" * 64 + "\n")
        self.assertEqual(json.loads(self._cli("recover").stdout), {"recovery_held": 0})

    def test_append_only_events_are_enforced_by_database_triggers(self) -> None:
        with Pilot(self.root) as pilot:
            task_id = pilot.submit("inspect", "sample.txt")
            with self.assertRaises(sqlite3.IntegrityError):
                with pilot.db:
                    pilot.db.execute("UPDATE events SET code='FALSIFIED' WHERE task_id=?", (task_id,))
            with self.assertRaises(sqlite3.IntegrityError):
                with pilot.db:
                    pilot.db.execute("DELETE FROM events WHERE task_id=?", (task_id,))
            events = pilot.snapshot()["events"]
        self.assertEqual(events[0]["code"], "SUBMITTED")

    @unittest.skipIf(os.geteuid() == 0, "requires actual unprivileged OS identity")
    def test_cli_status_and_error_contract(self) -> None:
        status = self._cli("status")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["schema"], SCHEMA)
        self.assertEqual(self._cli("run", "invalid-id").returncode, 2)
        self.assertEqual(json.loads(self._cli("deny-effect", "network").stdout),
                         {"allowed": False})


if __name__ == "__main__":
    unittest.main()
