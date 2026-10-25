"""Independent POSIX socketpair boundary matrix for VirtIO reply framing.

These cases exercise actual VirtioRPC.call() via a Unix socket pair, without
QEMU, model admission, a network listener, or an editor-startup task.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from veraos.virtio_model import MAX_FRAME, VirtioRPC


def response_exactly(size: int, *, request_id: str = "m1") -> bytes:
    body = json.dumps({"id": request_id, "ok": True, "padding": ""}, separators=(",", ":"))
    padding = size - len(body.encode("utf-8")) - 1  # The delimiter counts.
    if padding < 0:
        raise ValueError("requested frame is too small")
    payload = json.dumps({"id": request_id, "ok": True, "padding": "x" * padding},
                         separators=(",", ":")).encode() + b"\n"
    assert len(payload) == size
    return payload


def exchange(reply: bytes, *, chunk_size: int | None = None):
    host, guest = socket.socketpair()
    rpc = VirtioRPC(guest.fileno())
    def relay():
        try:
            request = b""
            while b"\n" not in request:
                received = host.recv(2048)
                if not received:
                    return
                request += received
            if reply:
                step = chunk_size or len(reply)
                for i in range(0, len(reply), step):
                    try:
                        host.sendall(reply[i:i + step])
                    except (BrokenPipeError, ConnectionResetError):
                        return
            host.shutdown(socket.SHUT_WR)
        finally:
            host.close()
    t = threading.Thread(target=relay, name="synthetic-virtio-relay", daemon=True)
    t.start()
    try:
        return rpc.call({"op": "models", "id": "m1"}, timeout=4)
    finally:
        guest.close()
        t.join(timeout=4)
        if t.is_alive():
            raise AssertionError("synthetic relay thread did not exit")


def assert_case(test: unittest.TestCase, *, reply=None, expected="ok", chunk_size=None):
    if expected == "request_oversize":
        left, right = socket.socketpair()
        try:
            rpc = VirtioRPC(left.fileno())
            with test.assertRaisesRegex(ValueError, "Request too large"):
                rpc.call({"op": "chat", "id": "m1", "messages": ["x" * 9000]}, timeout=1)
        finally:
            left.close()
            right.close()
        return
    errors = {
        "too_long": (RuntimeError, "VirtIO response too long"),
        "disconnected": (ConnectionError, "VirtIO relay disconnected"),
        "malformed": (json.JSONDecodeError, ""),
        "wrong_identity": (RuntimeError, "Unexpected VirtIO reply identity"),
        "relay_refusal": (RuntimeError, "denied"),
    }
    if expected == "ok":
        result = exchange(reply, chunk_size=chunk_size)
        test.assertEqual(result["id"], "m1")
        test.assertIs(result["ok"], True)
    else:
        error, phrase = errors[expected]
        with test.assertRaises(error) as caught:
            exchange(reply, chunk_size=chunk_size)
        test.assertIn(phrase, str(caught.exception))


def cases():
    return [
        ("valid_short", response_exactly(45), "ok", None),
        ("valid_8191", response_exactly(MAX_FRAME - 1), "ok", None),
        ("valid_8192_including_delimiter", response_exactly(MAX_FRAME), "ok", None),
        ("valid_8192_fragmented", response_exactly(MAX_FRAME), "ok", 37),
        ("reject_8193_contiguous", response_exactly(MAX_FRAME + 1), "too_long", None),
        ("reject_8237_contiguous", response_exactly(MAX_FRAME + 45), "too_long", None),
        ("reject_8193_fragmented", response_exactly(MAX_FRAME + 1), "too_long", 37),
        ("reject_8237_fragmented", response_exactly(MAX_FRAME + 45), "too_long", 37),
        ("reject_8192_undelimited_then_eof", b"x" * MAX_FRAME, "too_long", None),
        ("reject_8193_undelimited_then_eof", b"x" * (MAX_FRAME + 1), "too_long", None),
        ("reject_short_eof", b"", "disconnected", None),
        ("reject_malformed_json", b"{bad json}\n", "malformed", None),
        ("reject_wrong_identity", b'{"id":"other","ok":true}\n', "wrong_identity", None),
        ("reject_relay_refusal", b'{"id":"m1","ok":false,"error":"denied"}\n', "relay_refusal", None),
        ("reject_oversized_request_before_write", None, "request_oversize", None),
    ]


@unittest.skipIf(os.name == "nt", "socket file descriptors are POSIX-only")
class VirtioFramingMatrix(unittest.TestCase):
    pass


for _case_name, _reply, _expected, _chunk in cases():
    def _make_test(reply=_reply, expected=_expected, chunk_size=_chunk):
        def _test(self):
            assert_case(self, reply=reply, expected=expected, chunk_size=chunk_size)
        return _test
    setattr(VirtioFramingMatrix, "test_" + _case_name, _make_test())


if __name__ == "__main__":
    unittest.main()
