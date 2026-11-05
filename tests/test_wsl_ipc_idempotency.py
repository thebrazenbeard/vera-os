"""Opt-in keyed submit retry semantics for the disposable WSL IPC fixture.

These tests do not certify owner authentication or operating-system worker
isolation. An unkeyed legacy submit intentionally retains V1 behavior.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import pwd
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos.wsl_ipc import _dispatch, query, serve
from veraos.wsl_pilot import Pilot, PilotError


KEY = "a" * 32


@unittest.skipUnless(os.name == "posix", "Linux/POSIX SQLite fixture")
class KeyedSubmitSQLiteTests(unittest.TestCase):
    def setUp(self):
        if os.geteuid() == 0:
            mock_uid = patch("veraos.wsl_pilot._uid", return_value=0)
            mock_ipc_uid = patch("veraos.wsl_ipc._uid", return_value=0)
            mock_uid.start()
            mock_ipc_uid.start()
            self.addCleanup(mock_uid.stop)
            self.addCleanup(mock_ipc_uid.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.top = Path(tempfile.mkdtemp(prefix="veraos-keyed-", dir=native_home))
        self.addCleanup(shutil.rmtree, self.top)
        self.root = self.top / "pilot"
        with Pilot.init(self.root):
            pass

    def request(self, **changes):
        request = {"action": "submit", "worker": "inspect",
                   "filename": "fixture.txt", "request_id": KEY}
        request.update(changes)
        return request

    def dispatch(self, request):
        with Pilot(self.root) as pilot:
            return _dispatch(pilot, request)

    def test_keyed_retry_returns_exact_original_task_without_second_event(self):
        first = self.dispatch(self.request())
        second = self.dispatch(self.request())
        self.assertEqual(first, second)
        with Pilot(self.root) as pilot:
            state = pilot.snapshot()
            self.assertEqual(len(state["tasks"]), 1)
            self.assertEqual([e["code"] for e in state["events"]], ["SUBMITTED"])
            self.assertEqual(pilot.db.execute(
                "SELECT count(*) FROM ipc_submissions").fetchone()[0], 1)

    def test_conflicting_request_id_is_denied_with_no_new_task_or_receipt(self):
        original = self.dispatch(self.request())
        for changed in ({"filename": "other.txt"}, {"worker": "digest"}):
            with self.subTest(changed=changed), self.assertRaises(PilotError):
                self.dispatch(self.request(**changed))
        self.assertEqual(self.dispatch(self.request()), original)
        with Pilot(self.root) as pilot:
            state = pilot.snapshot()
            self.assertEqual(len(state["tasks"]), 1)
            self.assertEqual(len(state["events"]), 1)

    def test_invalid_request_ids_are_rejected_before_mutation(self):
        for invalid in ("client-1", "A" * 32, "a" * 31, 12, None, [], "z" * 32):
            with self.subTest(invalid=invalid), self.assertRaises(PilotError):
                self.dispatch(self.request(request_id=invalid))
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.snapshot()["tasks"], [])
            self.assertEqual(pilot.snapshot()["events"], [])

    def test_two_independent_sqlite_clients_racing_one_key_create_one_task(self):
        request = self.request()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.dispatch, (request, request)))
        self.assertEqual(results[0], results[1])
        with Pilot(self.root) as pilot:
            self.assertEqual(len(pilot.snapshot()["tasks"]), 1)
            self.assertEqual(len(pilot.snapshot()["events"]), 1)

    def test_unkeyed_legacy_submit_is_explicitly_not_idempotent(self):
        request = {"action": "submit", "worker": "inspect", "filename": "fixture.txt"}
        self.assertNotEqual(self.dispatch(request), self.dispatch(request))


@unittest.skipUnless(os.name == "posix" and hasattr(socket, "SO_PEERCRED"),
                     "Linux AF_UNIX peer credential socket required")
class KeyedSubmitSocketTests(unittest.TestCase):
    request = KeyedSubmitSQLiteTests.request

    def setUp(self):
        KeyedSubmitSQLiteTests.setUp(self)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM):
                pass
        except PermissionError:
            self.skipTest("sandbox forbids AF_UNIX; rerun on actual WSL")
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.errors = []

        def run_server():
            try:
                serve(self.root, self.stop, self.ready)
            except Exception as exc:
                self.errors.append(exc)

        self.thread = threading.Thread(target=run_server, daemon=True)
        self.thread.start()
        self.assertTrue(self.ready.wait(3), f"socket listener failed: {self.errors!r}")
        self.addCleanup(self._stop)

    def _stop(self):
        self.stop.set()
        self.thread.join(3)
        self.assertFalse(self.thread.is_alive())
        self.assertFalse(self.errors)

    def test_socket_lost_response_replay_retains_one_task(self):
        request = self.request(worker="digest")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(str(self.root / "pilot.sock"))
            import json
            client.sendall(json.dumps(request).encode() + b"\n")
            # Closing before reading simulates a lost result, not a failed send.
        deadline = time.monotonic() + 3
        while True:
            with Pilot(self.root) as pilot:
                if len(pilot.snapshot()["tasks"]) == 1:
                    first_id = pilot.snapshot()["tasks"][0]["task_id"]
                    break
            if time.monotonic() > deadline:
                self.fail("first keyed submit was not committed")
            time.sleep(0.01)
        replay = query(self.root, request)
        self.assertEqual(replay, {"task_id": first_id})
        with Pilot(self.root) as pilot:
            self.assertEqual(len(pilot.snapshot()["tasks"]), 1)
            self.assertEqual(len(pilot.snapshot()["events"]), 1)
