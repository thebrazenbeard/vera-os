"""Opt-in Linux AF_UNIX adapter for the disposable WSL pilot.

SO_PEERCRED identifies a Linux UID, *not* a Windows SID, application, person,
Vera identity, or independent worker sandbox. This is not a public service.
"""
from __future__ import annotations

import argparse
import hashlib
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
import uuid

from .wsl_pilot import Pilot, PilotError, _NAME, _uid


MAX_REQUEST = 1024
MAX_RESPONSES = 20
SOCKET_NAME = "pilot.sock"
_TASK_ID = re.compile(r"[0-9a-f]{32}\Z", re.ASCII)
_REQUEST_ID = re.compile(r"[0-9a-f]{32}\Z", re.ASCII)
_KEYED_LEDGER_VERSION = "1"


def _keyed_ledger_digest(db: sqlite3.Connection) -> str:
    """Detect partial ledger-row loss against a separately stored DB marker.

    Not authentication: a writer controlling this SQLite file can rewrite both.
    """
    rows = db.execute(
        "SELECT principal_uid, request_id, payload_sha256, task_id "
        "FROM ipc_submissions ORDER BY principal_uid, request_id").fetchall()
    return hashlib.sha256(json.dumps(
        rows, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _require_keyed_ledger_schema(db: sqlite3.Connection) -> None:
    """Reject restored/forged tables lacking the uniqueness and FK contract."""
    columns = db.execute("PRAGMA table_info('ipc_submissions')").fetchall()
    expected = [
        ("principal_uid", "INTEGER", 1, 1),
        ("request_id", "TEXT", 1, 2),
        ("payload_sha256", "TEXT", 1, 0),
        ("task_id", "TEXT", 1, 0),
    ]
    actual = [(row[1], row[2], row[3], row[5]) for row in columns]
    if actual != expected:
        raise PilotError("keyed submission table schema mismatch; recovery held")
    foreign_keys = db.execute("PRAGMA foreign_key_list('ipc_submissions')").fetchall()
    if (len(foreign_keys) != 1 or foreign_keys[0][2:5] !=
            ("tasks", "task_id", "task_id")):
        raise PilotError("keyed submission foreign key missing; recovery held")
    indexes = set()
    for info in db.execute("PRAGMA index_list('ipc_submissions')"):
        if info[2] != 1 or info[4] != 0:
            continue
        fields = tuple(r[2] for r in db.execute(
            'PRAGMA index_info("' + info[1].replace('"', '""') + '")'))
        indexes.add((info[3], fields))
    if not {("pk", ("principal_uid", "request_id")),
            ("u", ("task_id",))}.issubset(indexes):
        raise PilotError("keyed submission uniqueness missing; recovery held")


def _object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise PilotError("duplicate JSON key")
        value[key] = item
    return value


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
        value = json.loads(line.decode("utf-8"),
                           object_pairs_hook=_object_without_duplicate_keys)
    except (UnicodeError, ValueError) as exc:
        raise PilotError("invalid request JSON") from exc
    if type(value) is not dict:
        raise PilotError("request must be a JSON object")
    return value


def _submit_keyed(pilot: Pilot, request: dict) -> dict:
    """Atomically bind a same-UID request ID to one durable fixture task.

    This is only a Linux UID-scoped retry mechanism, NOT human identity or
    protected-effect authorization. Legacy unkeyed V1 submit remains distinct.
    """
    worker, filename, request_id = (request["worker"], request["filename"],
                                    request["request_id"])
    if type(request_id) is not str or not _REQUEST_ID.fullmatch(request_id):
        raise PilotError("invalid request ID")
    # Match the Pilot.submit fixture allowlist before opening the transaction.
    if type(worker) is not str or worker not in ("inspect", "digest"):
        raise PilotError("unrecognized worker")
    if (type(filename) is not str or not _NAME.fullmatch(filename)
            or filename in (".", "..")):
        raise PilotError("input must be a simple fixture filename")
    principal = _uid()
    payload = json.dumps({"action": "submit", "worker": worker, "filename": filename},
                         separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_sha = hashlib.sha256(payload).hexdigest()
    # Explicit BEGIN IMMEDIATE covers the schema-on-first-use migration,
    # request uniqueness, task insertion, and SUBMITTED receipt in ONE commit.
    # Pilot.submit() has its own commit and cannot be wrapped atomically here.
    pilot.db.execute("BEGIN IMMEDIATE")
    try:
        version = pilot.db.execute(
            "SELECT value FROM meta WHERE key='ipc_submissions_version'").fetchone()
        saved_digest = pilot.db.execute(
            "SELECT value FROM meta WHERE key='ipc_submissions_digest'").fetchone()
        exists = pilot.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='ipc_submissions'").fetchone() is not None
        if version is not None and version != (_KEYED_LEDGER_VERSION,):
            raise PilotError("unsupported keyed submission ledger version")
        if (version is None) != (saved_digest is None):
            raise PilotError("keyed submission metadata incomplete; recovery held")
        if not exists:
            if version is not None:
                raise PilotError("keyed submission ledger missing; recovery held")
            # Old V1 did not distinguish unkeyed tasks from a restored #73
            # database with its key table removed. Refuse that ambiguous
            # migration instead of potentially duplicating an earlier task.
            if pilot.db.execute("SELECT 1 FROM tasks LIMIT 1").fetchone():
                raise PilotError("ambiguous pre-keyed task history; recovery held")
            pilot.db.execute("""
                CREATE TABLE ipc_submissions (
                    principal_uid INTEGER NOT NULL,
                    request_id TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    task_id TEXT NOT NULL UNIQUE REFERENCES tasks(task_id),
                    PRIMARY KEY (principal_uid, request_id)
                )
            """)
        # The per-mapping receipt count below must not rescan the entire
        # append-only event journal for each entry. This index is transactional
        # with the keyed admission/migration and applies to legacy databases.
        pilot.db.execute("CREATE INDEX IF NOT EXISTS events_keyed_receipt_idx "
                         "ON events(task_id, code, detail)")
        _require_keyed_ledger_schema(pilot.db)
        # Validate ALL known mappings before admitting even a new request ID:
        # a partial restore must not turn an orphaned key into a fresh task.
        if pilot.db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise PilotError("broken task or event reference; recovery held")
        bindings = pilot.db.execute("""
            SELECT m.principal_uid, m.payload_sha256, m.task_id,
                   t.worker, t.filename, t.owner_uid,
                   (SELECT COUNT(*) FROM events e
                    WHERE e.task_id=m.task_id AND e.code='SUBMITTED'
                      AND e.detail=t.worker)
            FROM ipc_submissions m LEFT JOIN tasks t ON t.task_id=m.task_id
        """).fetchall()
        for uid, digest, task_id, prior_worker, prior_filename, owner, receipts in bindings:
            if (prior_worker is None or owner != uid or receipts != 1 or
                    digest != hashlib.sha256(json.dumps(
                        {"action": "submit", "worker": prior_worker,
                         "filename": prior_filename}, separators=(",", ":"),
                        sort_keys=True).encode("utf-8")).hexdigest()):
                raise PilotError("keyed submission integrity mismatch; recovery held")
        if version is None and pilot.db.execute("""
            SELECT 1 FROM tasks t LEFT JOIN ipc_submissions m
            ON m.task_id=t.task_id WHERE m.task_id IS NULL LIMIT 1
        """).fetchone():
            # A legacy #73 table can itself be partially restored before the
            # new digest marker is installed. No evidence distinguishes a
            # missing key from a legitimate unkeyed legacy task here.
            raise PilotError("unmapped pre-marker task history; recovery held")
        current_digest = _keyed_ledger_digest(pilot.db)
        if saved_digest is not None and saved_digest[0] != current_digest:
            raise PilotError("keyed submission ledger changed; recovery held")
        if version is None:
            # Both fresh construction and accepted legacy #73 ledgers receive
            # the marker in the SAME transaction as the next keyed operation.
            pilot.db.execute("INSERT INTO meta VALUES (?, ?)",
                             ("ipc_submissions_version", _KEYED_LEDGER_VERSION))
            pilot.db.execute("INSERT INTO meta VALUES (?, ?)",
                             ("ipc_submissions_digest", current_digest))
        previous = pilot.db.execute(
            "SELECT payload_sha256, task_id FROM ipc_submissions "
            "WHERE principal_uid=? AND request_id=?", (principal, request_id)).fetchone()
        if previous is not None:
            if previous[0] != payload_sha:
                raise PilotError("request ID reused for different payload")
            task_id = previous[1]
        else:
            task_id = uuid.uuid4().hex
            pilot.db.execute("INSERT INTO tasks VALUES (?,?,?,?,?)",
                             (task_id, worker, filename, "QUEUED", principal))
            pilot.db.execute("INSERT INTO events(task_id,code,detail) VALUES (?,?,?)",
                             (task_id, "SUBMITTED", worker))
            pilot.db.execute(
                "INSERT INTO ipc_submissions VALUES (?,?,?,?)",
                (principal, request_id, payload_sha, task_id))
            pilot.db.execute(
                "UPDATE meta SET value=? WHERE key='ipc_submissions_digest'",
                (_keyed_ledger_digest(pilot.db),))
        pilot.db.commit()
    except Exception:
        pilot.db.rollback()
        raise
    return {"task_id": task_id}


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
    keys = set(request)
    allowed_keys = schemas.get(action) if type(action) is str else None
    if (allowed_keys is None or
            (keys != allowed_keys and not (
                action == "submit" and keys == allowed_keys | {"request_id"}))):
        raise PilotError("unsupported action or unexpected fields")
    if action in ("run", "cancel") and (
            type(request["task_id"]) is not str or not _TASK_ID.fullmatch(request["task_id"])):
        raise PilotError("invalid task ID")
    if action == "submit":
        if "request_id" in request:
            return _submit_keyed(pilot, request)
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
        deadline = time.monotonic() + 2.0
        received = bytearray()
        while b"\n" not in received:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PilotError("response deadline expired; effect outcome unknown")
            client.settimeout(min(1.0, remaining))
            chunk = client.recv(min(512, 4097 - len(received)))
            if not chunk:
                raise PilotError("response truncated; effect outcome unknown")
            received.extend(chunk)
            if len(received) > 4096:
                raise PilotError("oversized response; effect outcome unknown")
        line, _, trailing = received.partition(b"\n")
        if trailing:
            raise PilotError("unexpected multiple responses")
        return json.loads(line.decode("utf-8"))


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
