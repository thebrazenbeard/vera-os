"""Source-contract probes for WSL IPC duplicate delivery and reply loss.

These tests characterize the *unkeyed legacy* IPC submit contract. A newer
opt-in 32-hex `request_id` path has keyed retry deduplication in Draft #73,
but unkeyed submissions still duplicate work and assert no caller identity.
"""
from __future__ import annotations

import json
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
from veraos.wsl_ipc import SOCKET_NAME, _dispatch, query, serve
from veraos.wsl_pilot import Pilot, PilotError


@unittest.skipUnless(os.name == "posix" and hasattr(socket, "SO_PEERCRED"),
                     "requires Linux AF_UNIX SO_PEERCRED")
class IPCReplayGapTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM):
                pass
        except PermissionError:
            self.skipTest("scratch sandbox prohibits AF_UNIX sockets; run on real WSL")
        # Scratch may run UID 0 without ability to runuser. In-process UID
        # simulation does not prove genuine nonroot operating-system admission.
        if os.geteuid() == 0:
            for target in ("veraos.wsl_pilot._uid", "veraos.wsl_ipc._uid"):
                stub = patch(target, return_value=0)
                stub.start()
                self.addCleanup(stub.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        top = Path(tempfile.mkdtemp(prefix="veraos-ipc-replay-", dir=native_home))
        self.addCleanup(shutil.rmtree, top)
        self.root = top / "state"
        with Pilot.init(self.root):
            pass
        (self.root / "input" / "fixture.txt").write_bytes(b"exact fixture\n")
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.thread = threading.Thread(
            target=serve, args=(self.root, self.stop, self.ready),
            kwargs={"max_responses": 20}, daemon=True,
        )
        self.thread.start()
        self.assertTrue(self.ready.wait(3), "local IPC listener did not become ready")
        self.addCleanup(self._stop_server)

    def _stop_server(self) -> None:
        self.stop.set()
        self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive(), "test server failed to stop")

    def _state(self) -> dict:
        with Pilot(self.root) as pilot:
            return pilot.snapshot()

    def _send_without_receiving(self, request: dict) -> None:
        """Deliver complete packet then drop caller; no response is consumed."""
        raw = json.dumps(request, sort_keys=True).encode("utf-8") + b"\n"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2.0)
            client.connect(str(self.root / SOCKET_NAME))
            client.sendall(raw)

    def _await(self, predicate, *, seconds: float = 2.0) -> None:
        deadline = time.monotonic() + seconds
        while not predicate():
            if time.monotonic() >= deadline:
                self.fail("server did not commit expected operation before deadline")
            threading.Event().wait(0.01)

    def test_duplicate_identical_submit_creates_two_distinct_tasks(self) -> None:
        request = {"action": "submit", "worker": "inspect", "filename": "fixture.txt"}
        first = query(self.root, request)
        second = query(self.root, request)
        self.assertNotEqual(first["task_id"], second["task_id"])
        snapshot = self._state()
        self.assertEqual(len(snapshot["tasks"]), 2)
        self.assertEqual([e["code"] for e in snapshot["events"]],
                         ["SUBMITTED", "SUBMITTED"])
        self.assertEqual(query(self.root, {"action": "status"})["tasks"], 2)

    def test_malformed_request_id_and_caller_identity_fields_rejected_not_ignored(self) -> None:
        for unexpected in (
            {"request_id": "client-1"},
            {"request_id": "client-1", "uid": 0},
            {"uid": os.geteuid()},
            {"caller": "Vera"},
            {"session": "arbitrary"},
        ):
            with self.subTest(unexpected=unexpected):
                denied = query(self.root, {
                    "action": "submit", "worker": "inspect",
                    "filename": "fixture.txt", **unexpected,
                })
                self.assertEqual(denied["result"], "DENIED")
                self.assertEqual(denied["error"], "PilotError")
        self.assertEqual(self._state()["tasks"], [])
        self.assertEqual(self._state()["events"], [])

    def test_lost_unkeyed_submit_reply_commits_task_but_no_replay_key_available(self) -> None:
        request = {"action": "submit", "worker": "digest", "filename": "fixture.txt"}
        self._send_without_receiving(request)
        self._await(lambda: len(self._state()["tasks"]) == 1)
        # A status read tells the client only counts, not the task id issued
        # before its response was lost. Admin-side journal readback can recover
        # the id, but the legacy unkeyed request has no read-by-key.
        remote = query(self.root, {"action": "status"})
        self.assertEqual(remote["tasks"], 1)
        self.assertEqual(remote["events"], 1)
        self.assertNotIn("task_id", remote)
        before_retry = self._state()["tasks"][0]["task_id"]
        retried = query(self.root, request)
        self.assertNotEqual(retried["task_id"], before_retry)
        snapshot = self._state()
        self.assertEqual(len(snapshot["tasks"]), 2)
        self.assertEqual([e["code"] for e in snapshot["events"]],
                         ["SUBMITTED", "SUBMITTED"])

    def test_lost_run_reply_does_not_reexecute_same_known_task_id(self) -> None:
        submitted = query(self.root, {
            "action": "submit", "worker": "digest", "filename": "fixture.txt"})
        task_id = submitted["task_id"]
        self._send_without_receiving({"action": "run", "task_id": task_id})
        self._await(lambda: self._state()["tasks"][0]["status"] == "COMPLETED")
        path = self.root / "derived" / (task_id + ".sha256")
        first_bytes = path.read_bytes()
        again = query(self.root, {"action": "run", "task_id": task_id})
        self.assertEqual(again, {"result": "DENIED", "error": "PilotError"})
        self.assertEqual(path.read_bytes(), first_bytes)
        snapshot = self._state()
        self.assertEqual([e["code"] for e in snapshot["events"]],
                         ["SUBMITTED", "CLAIMED", "OUTPUT_INTENT", "COMPLETED"])


@unittest.skipUnless(os.name == "posix", "requires POSIX filesystem semantics")
class IPCDispatchContractTests(unittest.TestCase):
    """Real SQLite policy tests even when AF_UNIX is blocked by sandbox."""

    def setUp(self) -> None:
        if os.geteuid() == 0:
            stub = patch("veraos.wsl_pilot._uid", return_value=0)
            stub.start()
            self.addCleanup(stub.stop)
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        top = Path(tempfile.mkdtemp(prefix="veraos-ipc-dispatch-", dir=native_home))
        self.addCleanup(shutil.rmtree, top)
        self.root = top / "state"
        with Pilot.init(self.root):
            pass

    def test_same_unkeyed_submit_replay_is_not_idempotent(self) -> None:
        with Pilot(self.root) as pilot:
            request = {"action": "submit", "worker": "inspect", "filename": "fixture.txt"}
            first = _dispatch(pilot, request)
            second = _dispatch(pilot, request)
            self.assertNotEqual(first["task_id"], second["task_id"])
            self.assertEqual(len(pilot.snapshot()["tasks"]), 2)

    def test_malformed_request_id_fails_closed_without_receipt(self) -> None:
        with Pilot(self.root) as pilot:
            with self.assertRaises(PilotError):
                _dispatch(pilot, {"action": "submit", "worker": "inspect",
                                  "filename": "fixture.txt", "request_id": "fixed-key"})
            self.assertEqual(pilot.snapshot()["tasks"], [])
            self.assertEqual(pilot.snapshot()["events"], [])


if __name__ == "__main__":
    unittest.main()
