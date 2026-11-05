"""Durable SOURCE-ONLY replay observations for untrusted Windows PING shapes.

This is NOT a Windows grant verifier or a trusted replay authority. All callers
and observations are untrusted; every return value denies admission. The
separate SQLite digest only catches partial corruption. A same-UID writer, a
complete database rollback, or a process replacing this code can forge state.

No protected operation may use this journal as proof of Windows identity,
consent, receipt custody, anti-rollback, or a consumed *trusted* grant.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .windows_identity_ping import PingRequest


_VERSION = "VERAOS_SOURCE_PING_REPLAY_V1"
_MAX_OBSERVATIONS = 1024  # bounded offline prototype; not a production retention policy
_HEX64 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_CREATE_SEEN = (
    "CREATE TABLE source_ping_seen ("
    "request_id_digest TEXT PRIMARY KEY NOT NULL, "
    "nonce_digest TEXT NOT NULL UNIQUE, "
    "request_sha256 TEXT NOT NULL) WITHOUT ROWID"
)
_CREATE_META = (
    "CREATE TABLE source_ping_meta ("
    "name TEXT PRIMARY KEY NOT NULL, "
    "value TEXT NOT NULL) WITHOUT ROWID"
)


class SourcePingReplayHeld(RuntimeError):
    """The local source-observation ledger cannot be used safely."""


@dataclass(frozen=True, slots=True)
class DeniedReplayObservation:
    """A non-authorizing result, even if `replayed` is false."""

    request_sha256: str
    replayed: bool

    @property
    def admission(self) -> str:
        return "DENIED"

    @property
    def authority(self) -> str:
        return "UNTRUSTED_SOURCE_ONLY"


def _domain_hash(domain: bytes, value: str) -> str:
    return hashlib.sha256(domain + b"\0" + value.encode("ascii")).hexdigest()


def _digest(db: sqlite3.Connection) -> str:
    rows = db.execute(
        "SELECT request_id_digest, nonce_digest, request_sha256 "
        "FROM main.source_ping_seen ORDER BY request_id_digest"
    ).fetchall()
    return hashlib.sha256(json.dumps(rows, separators=(",", ":"),
                                     ensure_ascii=True).encode("ascii")).hexdigest()


def _validate_schema(db: sqlite3.Connection) -> None:
    # ATTACH and TEMP objects can shadow an unqualified table. No arbitrary
    # attached/temp object should influence this dedicated source journal.
    databases = {row[1] for row in db.execute("PRAGMA database_list")}
    if databases not in ({"main"}, {"main", "temp"}):
        raise SourcePingReplayHeld("unexpected attached database; hold")
    if db.execute("SELECT 1 FROM sqlite_temp_master LIMIT 1").fetchone():
        raise SourcePingReplayHeld("unexpected temporary schema; hold")
    objects = dict(db.execute(
        "SELECT name, sql FROM main.sqlite_master "
        "WHERE type IN ('table','view','trigger')"
    ).fetchall())
    if objects != {"source_ping_seen": _CREATE_SEEN,
                   "source_ping_meta": _CREATE_META}:
        raise SourcePingReplayHeld("source replay schema differs; hold")
    # Check the marker and row digests even when the incoming request is a
    # duplicate. These are corruption alarms, not cryptographic custody.
    marker = dict(db.execute(
        "SELECT name,value FROM main.source_ping_meta").fetchall())
    if (set(marker) != {"version", "digest"} or marker["version"] != _VERSION
            or _HEX64.fullmatch(marker["digest"]) is None
            or marker["digest"] != _digest(db)):
        raise SourcePingReplayHeld("source replay marker mismatch; hold")
    rows = db.execute(
        "SELECT request_id_digest,nonce_digest,request_sha256 "
        "FROM main.source_ping_seen"
    ).fetchall()
    if len(rows) > _MAX_OBSERVATIONS:
        raise SourcePingReplayHeld("source replay capacity exceeded; hold")
    if any(type(value) is not str or _HEX64.fullmatch(value) is None
           for row in rows for value in row):
        raise SourcePingReplayHeld("source replay row malformed; hold")


def record_untrusted_ping(db_path: Path, raw_request: bytes) -> DeniedReplayObservation:
    """Atomically record a PING-shaped nonce, always denying authority.

    The first sighting becomes a *source observation*, not an admission.
    Reusing either the same request ID or nonce is reported as replayed. A
    distinct ID+nonce after a whole-db rollback can appear fresh: this source
    has no independent monotonic host custody.
    """
    request = PingRequest.from_wire(raw_request)
    if not isinstance(db_path, Path) or db_path.is_symlink():
        raise SourcePingReplayHeld("dedicated non-symlink SQLite path required")
    request_digest = _domain_hash(b"VERAOS_SOURCE_REQUEST_ID_V1", request.request_id)
    nonce_digest = _domain_hash(b"VERAOS_SOURCE_NONCE_V1", request.nonce)
    with closing(sqlite3.connect(db_path, timeout=2.0, isolation_level=None)) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            names = {r[0] for r in db.execute(
                "SELECT name FROM main.sqlite_master "
                "WHERE type IN ('table','view','trigger')"
            )}
            if not names:
                db.execute(_CREATE_SEEN)
                db.execute(_CREATE_META)
                db.executemany("INSERT INTO main.source_ping_meta VALUES (?,?)", [
                    ("version", _VERSION), ("digest", _digest(db))])
            _validate_schema(db)
            replayed = db.execute(
                "SELECT 1 FROM main.source_ping_seen WHERE "
                "request_id_digest=? OR nonce_digest=? LIMIT 1",
                (request_digest, nonce_digest)
            ).fetchone() is not None
            if not replayed:
                count = db.execute(
                    "SELECT count(*) FROM main.source_ping_seen").fetchone()[0]
                if count >= _MAX_OBSERVATIONS:
                    raise SourcePingReplayHeld("source replay capacity exhausted; hold")
                db.execute("INSERT INTO main.source_ping_seen VALUES (?,?,?)",
                           (request_digest, nonce_digest, request.sha256()))
                db.execute(
                    "UPDATE main.source_ping_meta SET value=? WHERE name='digest'",
                    (_digest(db),))
            db.commit()
        except Exception:
            db.rollback()
            raise
    return DeniedReplayObservation(request_sha256=request.sha256(), replayed=replayed)
