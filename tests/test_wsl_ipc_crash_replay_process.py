"""Cross-process crash/replay evidence for the opt-in Linux IPC pilot.

This is a disposable same-UID AF_UNIX fixture; it does NOT authenticate a
Windows logon, grant an effect, or prove host-owned monotonic state.
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


@unittest.skipUnless(os.name == "posix" and hasattr(socket, "AF_UNIX"),
                     "Linux/POSIX AF_UNIX transport required")
@unittest.skipIf(os.name == "posix" and os.geteuid() == 0,
                 "real unprivileged UID required; root-mocked tests are not host probes")
class CrashReplayProcessTests(unittest.TestCase):
    def setUp(self) -> None:
        # The WSL pilot is allowed only on the Linux-account native home FS.
        # Other Linux hosts can use their process-local temporary filesystem.
        import pwd
        native_home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                       if "microsoft" in os.uname().release.lower() else None)
        self.parent = Path(tempfile.mkdtemp(prefix="veraos-crash-replay-",
                                            dir=native_home))
        self.children: list[subprocess.Popen[str]] = []
        self.addCleanup(shutil.rmtree, self.parent)
        self.addCleanup(self._stop_children)
        self.root = self.parent / "pilot"
        with Pilot.init(self.root):
            pass
        (self.root / "input" / "fixture.txt").write_bytes(b"known-input\n")

    def _stop_children(self) -> None:
        for child in self.children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=10)

    def _serve(self) -> subprocess.Popen[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        server = subprocess.Popen(
            [sys.executable, "-m", "veraos.wsl_ipc", "--root", str(self.root),
             "serve", "--max-responses", "20"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.children.append(server)
        deadline = time.monotonic() + 10
        path = self.root / SOCKET_NAME
        while time.monotonic() < deadline:
            if server.poll() is not None:
                out, err = server.communicate(timeout=1)
                self.fail(f"server exited early: {server.returncode}: {out!r} {err!r}")
            if path.is_socket():
                return server
            time.sleep(0.02)
        self.fail("foreground server did not create socket within bounded startup")

    def test_response_loss_then_hard_crash_requires_socket_reconcile_but_no_replay(self) -> None:
        """Loss of a response after commit must not mint a second task.

        A crash leaves the server socket inode behind by design. This test
        deletes ONLY its own disposable fixture socket after confirming the
        original server is dead; it makes no claim of production recovery.
        """
        request_id = "e" * 32
        request = {"action": "submit", "worker": "digest",
                   "filename": "fixture.txt", "request_id": request_id}
        first = self._serve()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2.0)
            client.connect(str(self.root / SOCKET_NAME))
            client.sendall(json.dumps(request).encode("utf-8") + b"\n")
            # Intentionally forfeit the first response. We observe its durable
            # commit through independent SQLite readback before killing server.

        task_id = None
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with Pilot(self.root) as observed:
                row = observed.db.execute(
                    "SELECT task_id FROM ipc_submissions WHERE principal_uid=? "
                    "AND request_id=?", (os.geteuid(), request_id)
                ).fetchone() if observed.db.execute(
                    "SELECT name FROM sqlite_master WHERE name='ipc_submissions'"
                ).fetchone() else None
            if row:
                task_id = row[0]
                break
            time.sleep(0.02)
        self.assertIsNotNone(task_id, "initial request was not durably committed")

        first.kill()
        first.communicate(timeout=10)
        self.assertNotEqual(first.returncode, 0)
        stale = self.root / SOCKET_NAME
        self.assertTrue(stale.is_socket(), "unexpected automatic stale-socket removal")

        # The new server must fail closed before taking over an old socket.
        refused = subprocess.run(
            [sys.executable, "-m", "veraos.wsl_ipc", "--root", str(self.root),
             "serve", "--max-responses", "1"],
            env={**os.environ,
                 "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
            text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(refused.returncode, 2)
        self.assertIn('"error":"HELD"', refused.stderr)

        # A human/reconciler first validates its fixture ownership and exact
        # socket inode, then clears that stale endpoint. NEVER auto-unlink a
        # live socket or use this procedure on an uninspected host service.
        old_inode = stale.lstat().st_ino
        self.assertTrue(stale.is_socket())
        self.assertEqual(stale.lstat().st_ino, old_inode)
        stale.unlink()
        second = self._serve()
        self.assertEqual(query(self.root, request), {"task_id": task_id})
        conflicting = query(self.root, {**request, "filename": "other.txt"})
        self.assertEqual(conflicting.get("result"), "DENIED")
        with Pilot(self.root) as final:
            self.assertEqual(final.db.execute("SELECT count(*) FROM tasks").fetchone(), (1,))
            self.assertEqual(final.db.execute(
                "SELECT count(*) FROM events WHERE code='SUBMITTED'"
            ).fetchone(), (1,))
            self.assertEqual(final.db.execute(
                "SELECT count(*) FROM ipc_submissions"
            ).fetchone(), (1,))
        self.assertIsNone(second.poll(), "server should remain foreground/opt-in")


if __name__ == "__main__":
    unittest.main()
