"""Opt-in Linux AF_UNIX adapter for the disposable WSL pilot.

SO_PEERCRED identifies a Linux UID, *not* a Windows SID, application, person,
Vera identity, or independent worker sandbox. This is not a public service.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import sqlite3
import struct
import sys
import threading
import re
import time

from .wsl_pilot import Pilot, PilotError, _uid


MAX_REQUEST = 1024
MAX_RESPONSES = 20
SOCKET_NAME = "pilot.sock"
_TASK_ID = re.compile(r"[0-9a-f]{32}\Z", re.ASCII)


def _peer_linux_uid(client: socket.socket) -> int:
    """Obtain kernel-provided credentials, never trust a JSON-supplied UID."""
    if not hasattr(socket, "SO_PEERCRED") or client.family != socket.AF_UNIX:
        raise PilotError("Linux AF_UNIX peer credentials required")
    raw = client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    _pid, peer_uid, _gid = struct.unpack("3i", raw)
    return peer_uid


def _read_request(client: socket.socket) -> dict:
    deadline = time.monotonic() + 2.0
    received = bytearray()
    while b"\n" not in received:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PilotError("request deadline expired")
        client.settimeout(min(1.0, remaining))
        chunk = client.recv(min(256, MAX_REQUEST + 1 - len(received)))
        if not chunk:
            raise PilotError("incomplete request")
        received.extend(chunk)
        if len(received) > MAX_REQUEST:
            raise PilotError("oversized request")
    line, _, trailing = received.partition(b"\n")
    if trailing:
        raise PilotError("one JSON request per connection")
    try:
        value = json.loads(line.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise PilotError("invalid request JSON") from exc
    if type(value) is not dict:
        raise PilotError("request must be a JSON object")
    return value


def _dispatch(pilot: Pilot, request: dict) -> dict:
    # A strict key allowlist prevents a caller-supplied role, uid, path, or
    # arbitrary Python/tool payload from gaining any meaning.
    action = request.get("action")
    schemas = {
        "status": {"action"},
        "submit": {"action", "worker", "filename"},
        "run": {"action", "task_id"},
        "cancel": {"action", "task_id"},
        "deny-effect": {"action", "effect"},
    }
    if type(action) is not str or action not in schemas or set(request) != schemas[action]:
        raise PilotError("unsupported action or unexpected fields")
    if action in ("run", "cancel") and (
            type(request["task_id"]) is not str or not _TASK_ID.fullmatch(request["task_id"])):
        raise PilotError("invalid task ID")
    if action == "submit":
        return {"task_id": pilot.submit(request["worker"], request["filename"])}
    if action == "run":
        return {"status": pilot.run(request["task_id"])}
    if action == "cancel":
        return {"status": pilot.cancel(request["task_id"])}
    if action == "deny-effect":
        return {"allowed": pilot.protected_effect(request["effect"])}
    # Status has bounded result shape; never include private fixture content.
    row = pilot.db.execute("SELECT count(*) FROM tasks").fetchone()
    event_count = pilot.db.execute("SELECT count(*) FROM events").fetchone()[0]
    return {"schema": "VERAOS_WSL_IPC_V1", "tasks": row[0],
            "events": event_count, "production_authority": False}


def serve(root: Path, stop: threading.Event, ready: threading.Event | None = None,
          *, max_responses: int = MAX_RESPONSES) -> int:
    """Serve a bounded number of local requests; no autostart or TCP socket."""
    if type(max_responses) is not int or not 1 <= max_responses <= MAX_RESPONSES:
        raise PilotError("invalid request budget")
    with Pilot(root):
        pass  # Verify the owner-owned state root before creating the socket.
    path = Path(root).absolute() / SOCKET_NAME
    if path.exists() or path.is_symlink():
        raise PilotError("socket path is already owned or stale; never displace it")
    if not hasattr(socket, "SO_PEERCRED"):
        raise PilotError("kernel peer credentials are unavailable")
    handled = 0
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(path))
        own_inode = path.lstat().st_ino
        os.chmod(path, 0o600)
        server.listen(4)
        server.settimeout(0.2)
        if ready is not None:
            ready.set()
        try:
            while handled < max_responses and not stop.is_set():
                try:
                    client, _ = server.accept()
                except socket.timeout:
                    continue
                with client:
                    handled += 1
                    try:
                        if _peer_linux_uid(client) != _uid():
                            raise PilotError("peer Linux UID rejected")
                        request = _read_request(client)
                        with Pilot(root) as pilot:
                            response = _dispatch(pilot, request)
                    except (PilotError, OSError, ValueError, TypeError, sqlite3.Error) as exc:
                        response = {"result": "DENIED", "error": type(exc).__name__}
                    try:
                        client.sendall(json.dumps(response, sort_keys=True).encode("utf-8") + b"\n")
                    except (BrokenPipeError, ConnectionResetError):
                        # A disconnect cannot terminate the bounded server.
                        continue
        finally:
            # Only unlink the exact socket inode created by this server.
            if path.is_socket() and path.lstat().st_ino == own_inode:
                path.unlink()
    return handled


def query(root: Path, request: dict) -> dict:
    """One local request; the caller cannot assert its own peer credentials."""
    path = Path(root).absolute() / SOCKET_NAME
    raw = json.dumps(request, allow_nan=False).encode("utf-8") + b"\n"
    if len(raw) > MAX_REQUEST:
        raise PilotError("oversized request")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2.0)
        client.connect(str(path))
        client.sendall(raw)
        line = client.recv(4096)
        if b"\n" not in line:
            raise PilotError("invalid or truncated response")
        return json.loads(line.split(b"\n", 1)[0].decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    serve_args = commands.add_parser("serve")
    serve_args.add_argument("--max-responses", type=int, default=MAX_RESPONSES)
    request_args = commands.add_parser("request")
    request_args.add_argument("json_object")
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            result = {"handled": serve(args.root, threading.Event(),
                                       max_responses=args.max_responses)}
        else:
            result = query(args.root, json.loads(args.json_object))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PilotError, OSError, ValueError, TypeError):
        print('{"error":"HELD"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
