"""Real-process, bounded startup/ready/exit/restart test for local WSL IPC.

This does not exercise Windows startup, logon, systemd service persistence,
identity admission, or an operating VeraOS. Every child belongs to this test.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos.wsl_ipc import SOCKET_NAME, query  # noqa: E402
from veraos.wsl_pilot import Pilot  # noqa: E402


@unittest.skipUnless(os.name == "posix" and hasattr(socket, "SO_PEERCRED"),
                     "Linux peer-credential AF_UNIX surface required")
@unittest.skipIf(os.name == "posix" and os.geteuid() == 0,
                 "requires actual unprivileged Linux UID")
class ForegroundLifecycleProcessTests(unittest.TestCase):
    def setUp(self) -> None:
        import pwd

        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.parent = Path(tempfile.mkdtemp(prefix="veraos-lifecycle-",
                                            dir=native_home))
        self.children: list[subprocess.Popen[str]] = []
        self.addCleanup(shutil.rmtree, self.parent)
        self.addCleanup(self._stop_children)
        self.root = self.parent / "pilot"
        with Pilot.init(self.root):
            pass

    def _stop_children(self) -> None:
        for process in self.children:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)

    def _start(self, budget: int) -> subprocess.Popen[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        process = subprocess.Popen(
            [sys.executable, "-m", "veraos.wsl_ipc", "--root", str(self.root),
             "serve", "--max-responses", str(budget)],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.children.append(process)
        return process

    def _ready_status(self, process: subprocess.Popen[str]) -> dict:
        deadline = time.monotonic() + 10
        path = self.root / SOCKET_NAME
        while time.monotonic() < deadline:
            if process.poll() is not None:
                out, err = process.communicate(timeout=1)
                self.fail(f"owned server exited before readiness: {process.returncode}: {out!r} {err!r}")
            if path.is_socket():
                try:
                    return query(self.root, {"action": "status"})
                except ConnectionRefusedError:
                    # bind() precedes listen(); this retry never consumes a
                    # server request and is bounded by the readiness deadline.
                    pass
            time.sleep(0.02)
        self.fail("bounded foreground readiness was not observed")

    def test_budget_exit_cleans_owned_socket_and_allows_new_foreground_process(self):
        first = self._start(2)
        ready = self._ready_status(first)
        self.assertEqual(ready, {"schema": "VERAOS_WSL_IPC_V1", "tasks": 0,
                                 "events": 0, "production_authority": False})
        self.assertEqual(query(self.root, {"action": "status"}), ready)
        out, err = first.communicate(timeout=10)
        self.assertEqual(first.returncode, 0, err)
        self.assertEqual(json.loads(out), {"handled": 2})
        self.assertFalse((self.root / SOCKET_NAME).exists(),
                         "normal budget exit must unlink ONLY its owned socket")

        second = self._start(1)
        self.assertEqual(self._ready_status(second), ready)
        out, err = second.communicate(timeout=10)
        self.assertEqual(second.returncode, 0, err)
        self.assertEqual(json.loads(out), {"handled": 1})
        self.assertFalse((self.root / SOCKET_NAME).exists())
        with Pilot(self.root) as pilot:
            self.assertEqual(pilot.db.execute("SELECT count(*) FROM tasks").fetchone(), (0,))
            self.assertEqual(pilot.db.execute("SELECT count(*) FROM events").fetchone(), (0,))


if __name__ == "__main__":
    unittest.main()
