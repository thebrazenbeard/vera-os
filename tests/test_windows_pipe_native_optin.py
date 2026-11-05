"""Opt-in, disposable Windows-native VeraOS named-pipe PING qualification.

Source tests, Linux CI, and normal Windows tests MUST skip this module's probe.
An operator must authorize a specific local Windows test and explicitly set
VERAOS_NATIVE_PIPE_TEST=1 for the one-off command. Never enable it in CI or
in a background service. This only verifies Windows token observation for a
same-logon PING; it confers no identity, consent, WSL admission, grant, or
protected-effect authority and does not establish adversarial server custody.

Run ONLY after fresh authorization, from the VeraOS checkout on Windows
PowerShell (the environment assignments last only in this shell). Both the
explicit command-line marker and environment variable are necessary; normal
unittest discovery cannot activate native pipe operations merely by inheriting
the environment variable:
    $env:VERAOS_NATIVE_PIPE_TEST = '1'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:PYTHONPATH = 'src'
    py -3 tests/test_windows_pipe_native_optin.py --native-once

This file is source-only until that operator-authorized native run occurs.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import unittest


_IS_NATIVE_HOST = sys.platform == "win32" and os.name == "nt"
_HAS_OPT_IN_ENV = os.environ.get("VERAOS_NATIVE_PIPE_TEST") == "1"
_DIRECT_NATIVE_ONCE = (Path(sys.argv[0]).name == "test_windows_pipe_native_optin.py"
                       and sys.argv[1:] == ["--native-once"])
_OPTED_IN = _IS_NATIVE_HOST and _HAS_OPT_IN_ENV and _DIRECT_NATIVE_ONCE
_BOOT_DEADLINE_SECONDS = 8
_IO_DEADLINE_SECONDS = 8
_EXIT_DEADLINE_SECONDS = 8


def _source_module():
    # This import has no Win32 effects. It is delayed until explicit opt-in.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from veraos import windows_pipe_host
    return windows_pipe_host


def _bind(dll, name, return_type, arg_types):
    function = getattr(dll, name)
    function.restype = return_type
    function.argtypes = arg_types
    return function


def _kernel_functions():
    # No DLL is loaded at import or unittest discovery time.
    kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
    H, D, B, P = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, ctypes.c_void_p
    return (
        _bind(kernel, "ConnectNamedPipe", B, [H, P]),
        _bind(kernel, "CreateFileW", H, [wintypes.LPCWSTR, D, D, P, D, D, H]),
        _bind(kernel, "ReadFile", B, [H, P, D, ctypes.POINTER(D), P]),
        _bind(kernel, "WriteFile", B, [H, P, D, ctypes.POINTER(D), P]),
        _bind(kernel, "CloseHandle", B, [H]),
    )


def _write(write_file, handle, payload):
    buffer = ctypes.create_string_buffer(payload)
    received = wintypes.DWORD(0)
    if not write_file(handle, buffer, len(payload), ctypes.byref(received), None):
        raise RuntimeError("native WriteFile failed")
    if received.value != len(payload):
        raise RuntimeError("partial PING/PONG message")


def _read(read_file, handle):
    buffer = ctypes.create_string_buffer(16)
    received = wintypes.DWORD(0)
    if not read_file(handle, buffer, len(buffer), ctypes.byref(received), None):
        raise RuntimeError("native ReadFile failed")
    return buffer.raw[:received.value]


def _serve_one_ping():
    host = _source_module()
    connect, _, read_file, write_file, _ = _kernel_functions()
    with host.ephemeral_pipe() as pipe:
        # A unique random name is passed only through a private parent pipe.
        print(json.dumps({"ready": pipe.name}), flush=True)
        if not connect(pipe.handle, None) and ctypes.get_last_error() != 535:
            raise RuntimeError("native ConnectNamedPipe failed")
        if _read(read_file, pipe.handle) != b"PING":
            raise RuntimeError("unexpected PING frame")
        observed = host.observe_after_read(pipe)
        native = host._Native()
        token = wintypes.HANDLE()
        if not native.OpenProcessToken(native.GetCurrentProcess(), host.TOKEN_QUERY,
                                       ctypes.byref(token)):
            raise RuntimeError("process token unavailable")
        try:
            expected_user = host._token_sid(native, token, host.TOKEN_USER)
            expected_luid = host._token_authentication_luid(native, token)
        finally:
            native.CloseHandle(token)
        if observed.user_sid != expected_user or observed.logon_luid != expected_luid:
            raise RuntimeError("observed client user or logon LUID mismatch")
        thread_token = wintypes.HANDLE()
        if native.OpenThreadToken(native.GetCurrentThread(), host.TOKEN_QUERY,
                                  True, ctypes.byref(thread_token)):
            native.CloseHandle(thread_token)
            raise RuntimeError("client impersonation was not reverted")
        if ctypes.get_last_error() != 1008:  # ERROR_NO_TOKEN
            raise RuntimeError("thread token cleanup ambiguous")
        _write(write_file, pipe.handle, b"PONG")
        # Never expose actual SID, logon LUID, token handles, or pipe payload.
        print(json.dumps({"token_observed": True, "user_match": True,
                          "luid_match": True, "reverted": True}), flush=True)


def _client_ping(pipe_name, result_queue):
    _, create_file, read_file, write_file, close_handle = _kernel_functions()
    # Exact narrow client rights from windows_pipe_host.CLIENT_PIPE_ACCESS.
    access = 0x00120083
    security_qos = 0x00100000 | 0x00020000  # PRESENT | IMPERSONATION
    handle = create_file(pipe_name, access, 0, None, 3, security_qos, None)
    invalid = ctypes.c_void_p(-1).value
    if not handle or int(handle) == invalid:
        result_queue.put((False, "native CreateFileW denied"))
        return
    try:
        _write(write_file, handle, b"PING")
        if _read(read_file, handle) != b"PONG":
            raise RuntimeError("unexpected PONG response")
        result_queue.put((True, "PONG"))
    except Exception as exc:
        result_queue.put((False, str(exc)))
    finally:
        close_handle(handle)


@unittest.skipUnless(_OPTED_IN, "native named-pipe probe requires Windows and fresh operator opt-in")
class WindowsNativePipeOptInTests(unittest.TestCase):
    def test_real_ping_token_and_endpoint_cleanup_only(self):
        # A child process makes even a blocked synchronous Connect/Read bounded:
        # the parent kills this exact disposable child on timeout or failure.
        process = subprocess.Popen(
            [sys.executable, "-u", str(Path(__file__).resolve()), "--server"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        lines = queue.Queue()

        def _read_server_lines():
            for line in process.stdout:
                lines.put(line)

        threading.Thread(target=_read_server_lines, daemon=True).start()
        try:
            ready = json.loads(lines.get(timeout=_BOOT_DEADLINE_SECONDS))
            name = ready.get("ready")
            prefix = "\\\\.\\pipe\\veraos-ping-"
            self.assertIsInstance(name, str)
            self.assertTrue(name.startswith(prefix) and len(name) == len(prefix) + 32)
            response_queue = queue.Queue()
            threading.Thread(target=_client_ping, args=(name, response_queue),
                             daemon=True).start()
            ok, response = response_queue.get(timeout=_IO_DEADLINE_SECONDS)
            self.assertTrue(ok, response)
            self.assertEqual("PONG", response)
            receipt = json.loads(lines.get(timeout=_IO_DEADLINE_SECONDS))
            self.assertEqual(receipt, {"token_observed": True, "user_match": True,
                                       "luid_match": True, "reverted": True})
            self.assertEqual(process.wait(timeout=_EXIT_DEADLINE_SECONDS), 0)
            _, create_file, _, _, close_handle = _kernel_functions()
            reopened = create_file(name, 0x00120083, 0, None, 3,
                                   0x00100000 | 0x00020000, None)
            open_error = ctypes.get_last_error()
            if reopened and int(reopened) != ctypes.c_void_p(-1).value:
                close_handle(reopened)
                self.fail("disposable Windows pipe remained after child exit")
            self.assertEqual(open_error, 2, "endpoint reopen failed for an unexpected reason")
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=_EXIT_DEADLINE_SECONDS)


if __name__ == "__main__":
    if sys.argv[-1] == "--server":
        # Server is an isolated child; only an opted-in parent should launch it.
        if not _IS_NATIVE_HOST or not _HAS_OPT_IN_ENV:
            raise SystemExit("native named-pipe child requires opted-in Windows host")
        _serve_one_ping()
    elif _OPTED_IN:
        sys.argv = [sys.argv[0]]  # remove the explicit one-shot marker
        unittest.main(verbosity=2)
    else:
        raise SystemExit("native named-pipe probe requires fresh opt-in and --native-once")
