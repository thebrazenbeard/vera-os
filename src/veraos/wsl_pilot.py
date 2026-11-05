"""Unprivileged, opt-in WSL2 coordinator pilot. Not a VeraOS service.

Two fixed workers exercise local state and a narrow capability broker without
model loading, shell execution, network listeners, or production effects.
The OS UID is the *only* caller identity in this experiment: processes running
as the same Linux user are not isolated from each other.
"""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import sqlite3
import stat
import sys
import uuid


SCHEMA = "VERAOS_WSL_PILOT_V1"
MAX_INPUT_BYTES = 8192
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z", re.ASCII)


class PilotError(RuntimeError):
    """Expected local pilot rejection; never implies broader host security."""


def _uid() -> int:
    if os.name != "posix" or not hasattr(os, "geteuid"):
        raise PilotError("Linux POSIX user identity required")
    uid = os.geteuid()
    if uid == 0:
        raise PilotError("run as an unprivileged Linux user, not root")
    return uid


def _validate_root(root: Path, *, exists: bool) -> None:
    if not root.is_absolute() or root == Path("/") or root == Path("/mnt"):
        raise PilotError("absolute dedicated Linux state path required")
    if root.parts[:2] == ("/", "mnt"):
        raise PilotError("Windows and other /mnt mounts are not pilot state roots")
    # Resolve every ancestor: a lexical /home/... spelling may actually lead
    # through a symlink into a Windows mount.
    if root.resolve(strict=False) != root:
        raise PilotError("state path may not traverse symlinks")
    if os.name == "posix" and "microsoft" in os.uname().release.lower():
        # This first WSL experiment uses the native home filesystem only.
        # st_dev also rejects a Windows 9p mount bind-mounted beneath /home.
        backing = root if exists else root.parent
        # $HOME can be altered by the caller; only the OS account database
        # supplies the intended Linux home device for this first WSL pilot.
        try:
            owner_home = Path(pwd.getpwuid(_uid()).pw_dir).resolve(strict=True)
        except (KeyError, OSError) as exc:
            raise PilotError("Linux owner account home is unavailable") from exc
        if backing.stat().st_dev != owner_home.stat().st_dev:
            raise PilotError("WSL state must use the native Linux home filesystem")
    if exists:
        if root.is_symlink() or not root.is_dir():
            raise PilotError("state root must be an actual directory")
        info = root.stat()
        if info.st_uid != _uid() or (stat.S_IMODE(info.st_mode) & 0o077):
            raise PilotError("state root must be owned by caller and private (0700)")


class Pilot:
    def __init__(self, root: Path):
        self.root = Path(root).absolute()
        _validate_root(self.root, exists=True)
        db = self.root / "pilot.sqlite3"
        if db.is_symlink() or not db.is_file():
            raise PilotError("initialized database required")
        info = db.stat()
        if info.st_uid != _uid() or (stat.S_IMODE(info.st_mode) & 0o077):
            raise PilotError("database owner/permissions mismatch")
        self.db = sqlite3.connect(db, timeout=5)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        row = self.db.execute("SELECT value FROM meta WHERE key='owner_uid'").fetchone()
        schema = self.db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
        if row != (str(_uid()),) or schema != (SCHEMA,):
            self.db.close()
            raise PilotError("owner or schema mismatch")
        lease = self.root / "pilot.lock"
        if lease.is_symlink() or not lease.is_file() or lease.stat().st_uid != _uid() or (
                stat.S_IMODE(lease.stat().st_mode) & 0o077):
            self.db.close()
            raise PilotError("private worker lease required")

    @classmethod
    def init(cls, root: Path) -> "Pilot":
        _uid()
        root = Path(root).absolute()
        _validate_root(root, exists=False)
        root.mkdir(mode=0o700)  # No silent reuse of an existing state root.
        for child in ("input", "derived"):
            (root / child).mkdir(mode=0o700)
        db_path = root / "pilot.sqlite3"
        fd = os.open(db_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        fd = os.open(root / "pilot.lock", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        # sqlite3's context manager commits but does *not* close; explicitly
        # close the initializer connection (Python 3.14 warns on leaked DBs).
        with closing(sqlite3.connect(db_path)) as db, db:
            db.executescript("""
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE tasks (
                    task_id TEXT PRIMARY KEY,
                    worker TEXT NOT NULL CHECK (worker IN ('inspect', 'digest')),
                    filename TEXT NOT NULL,
                    status TEXT NOT NULL,
                    owner_uid INTEGER NOT NULL
                );
                CREATE TABLE events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT REFERENCES tasks(task_id),
                    code TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    recorded_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                );
                CREATE TRIGGER events_no_update BEFORE UPDATE ON events
                    BEGIN SELECT RAISE(ABORT, 'events are append only'); END;
                CREATE TRIGGER events_no_delete BEFORE DELETE ON events
                    BEGIN SELECT RAISE(ABORT, 'events are append only'); END;
            """)
            db.executemany("INSERT INTO meta VALUES (?, ?)",
                           (("schema", SCHEMA), ("owner_uid", str(_uid()))))
        return cls(root)

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "Pilot":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _event(self, task_id: str | None, code: str, detail: str = "") -> None:
        self.db.execute("INSERT INTO events(task_id,code,detail) VALUES (?,?,?)",
                        (task_id, code, detail))

    @contextmanager
    def _worker_lease(self, *, exclusive: bool):
        """Prevent recovery from racing any live cooperating worker process."""
        import fcntl  # POSIX/WSL only; this is not a hostile same-UID boundary.

        fd = os.open(self.root / "pilot.lock", os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            kind = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            try:
                fcntl.flock(fd, kind | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise PilotError("active worker lease; retry after workers stop") from exc
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def submit(self, worker: str, filename: str) -> str:
        if worker not in ("inspect", "digest"):
            raise PilotError("unrecognized worker")
        if type(filename) is not str or not _NAME.fullmatch(filename) or filename in (".", ".."):
            raise PilotError("input must be a simple fixture filename")
        task_id = uuid.uuid4().hex
        with self.db:
            self.db.execute("INSERT INTO tasks VALUES (?,?,?,?,?)",
                            (task_id, worker, filename, "QUEUED", _uid()))
            self._event(task_id, "SUBMITTED", worker)
        return task_id

    def claim(self, task_id: str) -> bool:
        """Atomic across separate SQLite clients; claim does not execute an effect."""
        with self.db:
            update = self.db.execute(
                "UPDATE tasks SET status='RUNNING' WHERE task_id=? AND status='QUEUED'",
                (task_id,))
            if update.rowcount != 1:
                return False
            self._event(task_id, "CLAIMED")
        return True

    def cancel(self, task_id: str) -> str:
        with self.db:
            # UPDATE itself takes SQLite's writer lock. No stale SELECT may
            # authorize a later overwrite of COMPLETED or RECOVERY_HELD.
            if self.db.execute("UPDATE tasks SET status='CANCELLED' "
                               "WHERE task_id=? AND status='QUEUED'", (task_id,)).rowcount:
                self._event(task_id, "CANCELLED")
                return "CANCELLED"
            if self.db.execute("UPDATE tasks SET status='CANCEL_REQUESTED' "
                               "WHERE task_id=? AND status='RUNNING'", (task_id,)).rowcount:
                self._event(task_id, "CANCEL_REQUESTED")
                return "CANCEL_REQUESTED"
            row = self.db.execute("SELECT status FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                raise PilotError("unknown task")
            return row[0]

    def recover(self) -> int:
        """Never auto-retry interrupted work, especially after output intent."""
        with self._worker_lease(exclusive=True):
            with self.db:
                ids = [r[0] for r in self.db.execute(
                    "SELECT task_id FROM tasks WHERE status IN ('RUNNING','CANCEL_REQUESTED')")]
                count = 0
                for task_id in ids:
                    update = self.db.execute(
                        "UPDATE tasks SET status='RECOVERY_HELD' WHERE task_id=? "
                        "AND status IN ('RUNNING','CANCEL_REQUESTED')", (task_id,))
                    if update.rowcount:
                        self._event(task_id, "RECOVERY_HELD", "manual reconciliation required")
                        count += 1
            return count

    def protected_effect(self, kind: str) -> bool:
        """Fixed default-deny broker; never forwards external effects."""
        if type(kind) is not str or not 1 <= len(kind) <= 48 or not _NAME.fullmatch(kind):
            raise PilotError("invalid effect label")
        with self.db:
            self._event(None, "PROTECTED_EFFECT_DENIED", kind)
        return False

    def _input(self, filename: str, *, read: bool) -> int | bytes:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        directory = os.open(self.root / "input", flags | os.O_DIRECTORY)
        try:
            fd = os.open(filename, flags, dir_fd=directory)
            try:
                first = os.fstat(fd)
                if not stat.S_ISREG(first.st_mode) or first.st_size > MAX_INPUT_BYTES:
                    raise PilotError("only bounded regular fixture files allowed")
                content = os.read(fd, MAX_INPUT_BYTES + 1) if read else b""
                last = os.fstat(fd)
                if (first.st_ino, first.st_size, first.st_mtime_ns) != (
                        last.st_ino, last.st_size, last.st_mtime_ns):
                    raise PilotError("fixture changed during read")
                if len(content) > MAX_INPUT_BYTES or (read and len(content) != first.st_size):
                    raise PilotError("fixture read was incomplete")
                return content if read else first.st_size
            finally:
                os.close(fd)
        finally:
            os.close(directory)

    def _derive(self, task_id: str, digest: str) -> None:
        name = task_id + ".sha256"
        # An intent receipt predates any filesystem write. An interrupted
        # operation is held for reconciliation, never automatically replayed.
        with self.db:
            self._event(task_id, "OUTPUT_INTENT", name)
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        directory = os.open(self.root / "derived", flags)
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=directory)
            try:
                payload = (digest + "\n").encode("ascii")
                if os.write(fd, payload) != len(payload):
                    raise PilotError("short derived output write")
                os.fsync(fd)
            finally:
                os.close(fd)
            os.fsync(directory)
        finally:
            os.close(directory)

    def run(self, task_id: str) -> str:
        with self._worker_lease(exclusive=False):
            return self._run_with_lease(task_id)

    def _run_with_lease(self, task_id: str) -> str:
        if not self.claim(task_id):
            raise PilotError("task is not queued or is already owned")
        worker, filename = self.db.execute(
            "SELECT worker,filename FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        try:
            if worker == "inspect":
                result = self._input(filename, read=False)
                detail = f"bytes={result}"
            else:
                data = self._input(filename, read=True)
                detail = hashlib.sha256(data).hexdigest()
            with self.db:
                state = self.db.execute("SELECT status FROM tasks WHERE task_id=?", (task_id,)).fetchone()[0]
                if state == "CANCEL_REQUESTED":
                    update = self.db.execute("UPDATE tasks SET status='CANCELLED' "
                                             "WHERE task_id=? AND status='CANCEL_REQUESTED'", (task_id,))
                    if update.rowcount:
                        self._event(task_id, "CANCELLED")
                        return "CANCELLED"
                if state != "RUNNING":
                    raise PilotError("unexpected task state; no effect admitted")
            if worker == "digest":
                self._derive(task_id, detail)
            with self.db:
                if self.db.execute("UPDATE tasks SET status='COMPLETED' "
                                   "WHERE task_id=? AND status='RUNNING'", (task_id,)).rowcount:
                    self._event(task_id, "COMPLETED", "output_written" if worker == "digest" else detail)
                    return "COMPLETED"
                if self.db.execute("UPDATE tasks SET status='RECOVERY_HELD' "
                                   "WHERE task_id=? AND status='CANCEL_REQUESTED'", (task_id,)).rowcount:
                    self._event(task_id, "RECOVERY_HELD", "cancel raced output; inspect before restart")
                    return "RECOVERY_HELD"
                raise PilotError("task changed after work; no terminal overwrite")
        except Exception:
            with self.db:
                update = self.db.execute(
                    "UPDATE tasks SET status='RECOVERY_HELD' WHERE task_id=? "
                    "AND status IN ('RUNNING','CANCEL_REQUESTED')", (task_id,))
                if update.rowcount:
                    self._event(task_id, "WORKER_HELD", "inspect failure or ambiguous output")
            raise

    def snapshot(self) -> dict:
        tasks = [dict(zip(("task_id", "worker", "filename", "status"), row)) for row in
                 self.db.execute("SELECT task_id,worker,filename,status FROM tasks ORDER BY rowid")]
        events = [dict(zip(("seq", "task_id", "code", "detail"), row)) for row in
                  self.db.execute("SELECT seq,task_id,code,detail FROM events ORDER BY seq")]
        return {"schema": SCHEMA, "tasks": tasks, "events": events,
                "production_authority": False, "model_inference": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    cmds = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "recover", "status"):
        cmds.add_parser(name)
    submit = cmds.add_parser("submit")
    submit.add_argument("worker", choices=("inspect", "digest"))
    submit.add_argument("filename")
    for name in ("run", "cancel"):
        cmds.add_parser(name).add_argument("task_id")
    cmds.add_parser("deny-effect").add_argument("effect")
    args = parser.parse_args(argv)
    try:
        with (Pilot.init(args.root) if args.command == "init" else Pilot(args.root)) as pilot:
            if args.command == "init":
                result = {"schema": SCHEMA, "initialized": True}
            elif args.command == "submit":
                result = {"task_id": pilot.submit(args.worker, args.filename)}
            elif args.command == "run":
                result = {"status": pilot.run(args.task_id)}
            elif args.command == "cancel":
                result = {"status": pilot.cancel(args.task_id)}
            elif args.command == "recover":
                result = {"recovery_held": pilot.recover()}
            elif args.command == "deny-effect":
                result = {"allowed": pilot.protected_effect(args.effect)}
            else:
                result = pilot.snapshot()
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PilotError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"error": type(exc).__name__, "result": "HELD"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
