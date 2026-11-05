"""Local Linux socket transport tests; no Windows SID or app identity claim."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch

from veraos.wsl_pilot import Pilot, PilotError
from veraos import wsl_ipc


@unittest.skipUnless(os.name == "posix" and hasattr(socket, "SO_PEERCRED"),
                     "Linux AF_UNIX SO_PEERCRED required")
class WSLLocalIPCTests(unittest.TestCase):
    def setUp(self):
        # Scratch may run as UID0 without permission to switch users. The
        # actual unprivileged credential test must also execute in WSL.
        if os.geteuid() == 0:
            self._patch_uid = patch("veraos.wsl_pilot._uid", return_value=0)
            self._patch_peer = patch("veraos.wsl_ipc._uid", return_value=0)
            self._patch_uid.start()
            self._patch_peer.start()
            self.addCleanup(self._patch_uid.stop)
            self.addCleanup(self._patch_peer.stop)
        self.outer = Path(tempfile.mkdtemp(prefix="veraos-ipc-"))
        self.addCleanup(shutil.rmtree, self.outer)
        self.root = self.outer / "pilot"
        with Pilot.init(self.root):
            pass
        (self.root / "input" / "fixture.txt").write_bytes(b"VERAOS-IPC\n")
        self._threads = []

    def _start(self, *, max_responses=20):
        stop = threading.Event()
        ready = threading.Event()
        errors = []
        result = []

        def target():
            try:
                result.append(wsl_ipc.serve(self.root, stop, ready,
                                           max_responses=max_responses))
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        self.assertTrue(ready.wait(3), f"server never ready: {errors!r}")
        self._threads.append((stop, thread, errors, result))
        self.addCleanup(lambda: (stop.set(), thread.join(3)))
        return stop, thread, errors, result

    def test_unix_socket_is_private_and_kernel_peer_is_actual_user(self):
        self._start()
        path = self.root / wsl_ipc.SOCKET_NAME
        self.assertTrue(stat.S_ISSOCK(path.lstat().st_mode))
        self.assertEqual(stat.S_IMODE(path.lstat().st_mode), 0o600)
        response = wsl_ipc.query(self.root, {"action": "status"})
        self.assertEqual(response["schema"], "VERAOS_WSL_IPC_V1")
        self.assertFalse(response["production_authority"])
        self.assertEqual(response["tasks"], 0)

    def test_client_cannot_assert_or_spoof_its_own_uid(self):
        self._start()
        self.assertEqual(wsl_ipc.query(self.root, {"action": "status", "uid": os.geteuid()})
                         ["result"], "DENIED")
        self.assertEqual(wsl_ipc.query(self.root, {"action": "status", "actor": "vera"})
                         ["result"], "DENIED")
        self.assertEqual(wsl_ipc.query(self.root, {"action": "status"})["tasks"], 0)

    def test_separate_client_calls_produce_durable_task_and_effect_receipts(self):
        self._start()
        task_id = wsl_ipc.query(self.root, {"action": "submit", "worker": "digest",
                                            "filename": "fixture.txt"})["task_id"]
        self.assertEqual(wsl_ipc.query(self.root, {"action": "run", "task_id": task_id}),
                         {"status": "COMPLETED"})
        self.assertEqual(wsl_ipc.query(self.root, {"action": "deny-effect",
                                                   "effect": "protected.merge"}),
                         {"allowed": False})
        status = wsl_ipc.query(self.root, {"action": "status"})
        self.assertEqual(status["tasks"], 1)
        self.assertEqual(status["events"], 5)
        expected = hashlib.sha256(b"VERAOS-IPC\n").hexdigest() + "\n"
        self.assertEqual((self.root / "derived" / (task_id + ".sha256")).read_text(), expected)

    def test_malformed_and_oversized_requests_fail_closed(self):
        self._start()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(str(self.root / wsl_ipc.SOCKET_NAME))
            client.sendall(b"not-json\n")
            self.assertEqual(json.loads(client.recv(1024))["result"], "DENIED")
        with self.assertRaises(PilotError):
            wsl_ipc.query(self.root, {"action": "status", "junk": "x" * 1500})
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(str(self.root / wsl_ipc.SOCKET_NAME))
            client.sendall(b"{" + b"x" * (wsl_ipc.MAX_REQUEST + 50) + b"\n")
            self.assertEqual(json.loads(client.recv(1024))["result"], "DENIED")

    def test_foreign_kernel_uid_is_denied_even_with_valid_request(self):
        # Source-injection test only; not a real cross-UID OS probe.
        self._start()
        with patch("veraos.wsl_ipc._peer_linux_uid", return_value=os.geteuid() + 1):
            self.assertEqual(wsl_ipc.query(self.root, {"action": "status"})["result"], "DENIED")
        self.assertEqual(wsl_ipc.query(self.root, {"action": "status"})["tasks"], 0)

    def test_existing_socket_path_cannot_be_silently_replaced(self):
        (self.root / wsl_ipc.SOCKET_NAME).symlink_to(self.root / "pilot.sqlite3")
        with self.assertRaises(PilotError):
            wsl_ipc.serve(self.root, threading.Event(), max_responses=1)
        self.assertTrue((self.root / wsl_ipc.SOCKET_NAME).is_symlink())

    def test_bounded_server_stops_and_restarts_without_replacing_db(self):
        stop, thread, errors, result = self._start(max_responses=2)
        first = wsl_ipc.query(self.root, {"action": "submit", "worker": "inspect",
                                           "filename": "fixture.txt"})["task_id"]
        self.assertEqual(wsl_ipc.query(self.root, {"action": "run", "task_id": first}),
                         {"status": "COMPLETED"})
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertEqual(result, [2])
        self.assertFalse((self.root / wsl_ipc.SOCKET_NAME).exists())
        self._start()
        self.assertEqual(wsl_ipc.query(self.root, {"action": "status"})["events"], 3)

    def test_unsupported_remote_recovery_and_arbitrary_tool_requests_denied(self):
        self._start()
        for request in ({"action": "recover"}, {"action": "exec", "cmd": "whoami"},
                        {"action": "submit", "worker": "shell", "filename": "fixture.txt"},
                        {"action": "run", "task_id": []},
                        {"action": "cancel", "task_id": {"forged": True}}):
            with self.subTest(request=request):
                self.assertEqual(wsl_ipc.query(self.root, request)["result"], "DENIED")
        # Server remains live after invalid bindable/compound JSON types.
        self.assertEqual(wsl_ipc.query(self.root, {"action": "status"})["tasks"], 0)

    def test_dribbling_client_cannot_reset_total_request_deadline(self):
        class SlowClient:
            def settimeout(self, _value):
                return None

            def recv(self, _length):
                return b"x"

        tick = iter((0.0, 0.1, 0.9, 1.7, 2.1, 2.2))
        with patch("veraos.wsl_ipc.time.monotonic", side_effect=lambda: next(tick)):
            with self.assertRaises(PilotError):
                wsl_ipc._read_request(SlowClient())


if __name__ == "__main__":
    unittest.main()
