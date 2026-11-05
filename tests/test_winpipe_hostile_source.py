"""Independent security counterexamples against Draft #74 source-only pipe.

These tests intentionally do not invoke Windows APIs or grant authority. They
characterize compatibility and provenance gaps that native host tests must
resolve before the prototype may be called an identity broker.
"""
from __future__ import annotations

import inspect
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos import windows_pipe_host as host


# Microsoft FILE_GENERIC_READ / FILE_GENERIC_WRITE expanded access masks.
# https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights
FILE_GENERIC_READ = 0x00120089
FILE_GENERIC_WRITE = 0x00120116


class WindowsPipeHostileSourceTests(unittest.TestCase):
    def test_ordinary_generic_read_and_write_client_request_cannot_fit_dacl(self):
        # An ordinary CreateFileW(... GENERIC_READ|GENERIC_WRITE ...) client
        # will request rights excluded by the least-privilege logon-SID DACL.
        # The remedy is a deliberately narrow, tested client access mask,
        # NOT granting FILE_CREATE_PIPE_INSTANCE to that logon SID.
        client = host.CLIENT_PIPE_ACCESS
        for generic in (FILE_GENERIC_READ, FILE_GENERIC_WRITE,
                        FILE_GENERIC_READ | FILE_GENERIC_WRITE):
            with self.subTest(mask=hex(generic)):
                self.assertNotEqual(generic & ~client, 0)
        self.assertFalse(client & host.FILE_CREATE_PIPE_INSTANCE)

    def test_observation_does_not_prove_last_frame_or_pipe_provenance(self):
        source = inspect.getsource(host.observe_after_read)
        # An EphemeralPipe value is forgeable; neither origin nor most-recent
        # frame provenance is validated by this routine. It only reads token
        # information for an OS handle provided by a future caller.
        self.assertNotIn("ReadFile(", source)
        self.assertNotIn("ConnectNamedPipe(", source)
        self.assertIn("type(pipe) is not EphemeralPipe", source)
        self.assertIn("not by itself be treated as an authentication", source)

    def test_no_windows_to_linux_authentication_or_replay_authority(self):
        source = inspect.getsource(host)
        for banned in ("def authorize_ping(", "def issue_grant(",
                       "def verify_grant(", "def submit_wsl_task("):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
