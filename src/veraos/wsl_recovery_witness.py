"""Source-only checker for an externally authenticated recovery checkpoint.

There is deliberately NO checkpoint issuer, file-backed fallback, socket,
Windows bridge, or automatic admission hook here. A checkpoint from JSON,
the pilot directory, or another same-UID process is not trusted authority.
The caller must prove separately that the checkpoint came from a host-owned,
rollback-resistant issuer before using this comparison as a gate.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import sqlite3

from .wsl_ipc import _keyed_ledger_digest, _require_keyed_ledger_schema
from .wsl_pilot import PilotError, SCHEMA


_DIGEST = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_FULL_STATE_TABLES = frozenset(("meta", "tasks", "events",
                                "ipc_submissions", "sqlite_sequence"))
_MAX_SOURCE_ROWS = 10000


@dataclass(frozen=True, slots=True)
class ExternalCheckpoint:
    """Data contract only; construction does not authenticate its producer."""

    owner_uid: int
    schema: str
    keyed_version: str
    keyed_count: int
    keyed_digest: str


def assert_matches_external_checkpoint(
    db: sqlite3.Connection, checkpoint: ExternalCheckpoint | None
) -> None:
    """Fail closed if an independently trusted checkpoint disagrees with DB.

    Not an admission mechanism. The caller must verify the checkpoint's
    provenance and serialize this read with all DB writes and trusted witness
    publication. A successful result is *only* a consistency comparison.
    """
    if (type(checkpoint) is not ExternalCheckpoint or
            type(checkpoint.owner_uid) is not int or checkpoint.owner_uid < 0 or
            checkpoint.schema != SCHEMA or checkpoint.keyed_version != "1" or
            type(checkpoint.keyed_count) is not int or checkpoint.keyed_count < 0 or
            type(checkpoint.keyed_digest) is not str or
            not _DIGEST.fullmatch(checkpoint.keyed_digest)):
        raise PilotError("external recovery checkpoint unavailable or malformed; hold")

    # The schema, marker, count, and digest must come from one SQLite WAL
    # snapshot. A series of autocommit SELECTs can otherwise mix values from
    # different commits by a concurrent writer. This is consistency only;
    # the issuer and write serialization still require independent custody.
    # A caller-owned transaction may already hold a stale WAL read snapshot.
    # Without a protected writer lease, there is no safe way for this API to
    # certify that such a transaction represents the current ledger. Hold
    # instead of accepting a snapshot pinned before another writer committed.
    if db.in_transaction:
        raise PilotError("external checkpoint preexisting transaction; hold")
    version_before = db.execute("PRAGMA data_version").fetchone()[0]
    db.execute("BEGIN")
    try:
        _assert_keyed_checkpoint_in_snapshot(db, checkpoint)
    finally:
        db.rollback()
    if db.execute("PRAGMA data_version").fetchone()[0] != version_before:
        # A cooperating writer committed during the comparison. The snapshot
        # may have matched an older ledger, but cannot certify the current
        # state. This detection does not replace a real writer/issuer lease.
        raise PilotError("external checkpoint concurrent database change; hold")


def _assert_keyed_checkpoint_in_snapshot(
    db: sqlite3.Connection, checkpoint: ExternalCheckpoint
) -> None:
    # Do not permit caller-created TEMP copies to satisfy keyed schema/data
    # checks, or attached connection state outside the claimed database.
    _require_unshadowed_main_connection(db)

    # A DB with a lost keyed table, schema, marker, or owner must fail before
    # any comparison. The in-DB digest is not used as authentication.
    _require_keyed_ledger_schema(db)
    meta = dict(db.execute("SELECT key, value FROM meta WHERE key IN "
                           "('owner_uid','schema','ipc_submissions_version',"
                           "'ipc_submissions_digest')"))
    if (meta.get("owner_uid") != str(checkpoint.owner_uid) or
            meta.get("schema") != SCHEMA or
            meta.get("ipc_submissions_version") != "1"):
        raise PilotError("external checkpoint owner or version mismatch; hold")

    current_count = db.execute("SELECT count(*) FROM ipc_submissions").fetchone()[0]
    current_digest = _keyed_ledger_digest(db)
    if (meta.get("ipc_submissions_digest") != current_digest or
            current_count != checkpoint.keyed_count or
            current_digest != checkpoint.keyed_digest):
        raise PilotError("external recovery checkpoint mismatch; hold")


@dataclass(frozen=True, slots=True)
class FullStateTransition:
    """Untrusted value contract, never proof of a host-owned issuer.

    A real host issuer must durably and monotonically publish this record
    independently of the WSL guest. Constructing this Python type does NOT
    authenticate any of these fields or authorize task admission.
    """

    owner_uid: int
    schema: str
    version: str
    generation: int
    phase: str  # PREPARED or COMMITTED; only an exact COMMITTED match can compare.
    before_digest: str
    after_digest: str


def _source_rows(db: sqlite3.Connection, query: str) -> list:
    """Bound this development-only full-state scan; excess means HOLD."""
    rows = db.execute(query + " LIMIT ?", (_MAX_SOURCE_ROWS + 1,)).fetchall()
    if len(rows) > _MAX_SOURCE_ROWS:
        raise PilotError("pilot state exceeds bounded full-state witness scan; hold")
    return rows


def _require_unshadowed_main_connection(db: sqlite3.Connection) -> None:
    """Reject connection-local state omitted by either recovery comparison.

    The pilot expects one persistent database, `main`. Attached databases
    can carry unscanned state, and TEMP objects can shadow unqualified reads.
    This does not authenticate the caller or the witness's actual issuer.
    """
    databases = db.execute("PRAGMA database_list").fetchall()
    if not databases or any(row[1] not in ("main", "temp") for row in databases):
        raise PilotError("attached pilot database unsupported; hold")
    if db.execute("SELECT 1 FROM sqlite_temp_master LIMIT 1").fetchone():
        raise PilotError("unsupported temporary pilot schema can shadow main; hold")


def full_pilot_state_digest(db: sqlite3.Connection) -> str:
    """Fingerprint all known pilot tables and their schema, not just keyed IDs.

    SOURCE-only snapshot calculation; a same-UID caller may forge a matching
    checkpoint. Never expose this digest as a self-authenticating receipt.
    """
    # Multiple SELECTs must observe one SQLite snapshot, including under WAL
    # when another cooperating writer commits during the scan. Keep a caller's
    # pre-existing transaction intact; otherwise own only a read transaction.
    owns_snapshot = not db.in_transaction
    if owns_snapshot:
        db.execute("BEGIN")
    try:
        return _compute_full_pilot_state_digest(db)
    finally:
        if owns_snapshot:
            db.rollback()


def _compute_full_pilot_state_digest(db: sqlite3.Connection) -> str:
    # Unqualified SQLite lookups resolve TEMP objects before main. A caller
    # can otherwise clone a known-good main.tasks into TEMP.tasks, modify the
    # persistent task and still obtain the old digest on this connection.
    # The pilot never needs temporary objects: refuse their presence rather
    # than treating a caller-controlled shadow as durable state.
    _require_unshadowed_main_connection(db)
    # Views and future sqlite_master object kinds are durable schema state.
    # Previously omitted views could be inserted without changing the digest.
    if db.execute("SELECT 1 FROM sqlite_master WHERE "
                  "type NOT IN ('table','index','trigger') LIMIT 1").fetchone():
        raise PilotError("unsupported pilot schema object; hold")
    tables = {row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if tables != _FULL_STATE_TABLES:
        raise PilotError("unsupported pilot state table set; hold")
    _require_keyed_ledger_schema(db)
    if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise PilotError("pilot state foreign key mismatch; hold")
    triggers = {row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger'")}
    if triggers != {"events_no_update", "events_no_delete"}:
        raise PilotError("pilot event append-only trigger mismatch; hold")

    state = {
        "domain": "VERAOS_FULL_PILOT_SOURCE_STATE_V1",
        "schema": _source_rows(db,
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE type IN ('table','index','trigger') ORDER BY type,name"),
        "meta": _source_rows(db, "SELECT key,value FROM meta ORDER BY key"),
        "tasks": _source_rows(db,
            "SELECT task_id,worker,filename,status,owner_uid FROM tasks ORDER BY task_id"),
        "events": _source_rows(db,
            "SELECT seq,task_id,code,detail,recorded_utc FROM events ORDER BY seq"),
        "ipc_submissions": _source_rows(db,
            "SELECT principal_uid,request_id,payload_sha256,task_id "
            "FROM ipc_submissions ORDER BY principal_uid,request_id"),
        "sqlite_sequence": _source_rows(db,
            "SELECT name,seq FROM sqlite_sequence ORDER BY name"),
    }
    try:
        serialized = json.dumps(state, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=True).encode("utf-8")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise PilotError("pilot state is not canonically encodable; hold") from exc
    return hashlib.sha256(serialized).hexdigest()


def assert_full_state_transition_consistent(
    db: sqlite3.Connection, transition: FullStateTransition | None
) -> None:
    """Compare DB to a transition's declared committed result, never admit it.

    The caller must FIRST authenticate monotonic host-owned issuer custody
    and serialize guest writes with issuance. A PREPARED checkpoint always
    holds, whether DB is before or after the prospective commit; no automatic
    roll-forward or rewind is safe in an uncoordinated crash window.
    """
    if (type(transition) is not FullStateTransition or
            type(transition.owner_uid) is not int or transition.owner_uid < 0 or
            transition.schema != SCHEMA or transition.version != "1" or
            type(transition.generation) is not int or transition.generation < 0 or
            transition.phase not in ("PREPARED", "COMMITTED") or
            type(transition.before_digest) is not str or
            _DIGEST.fullmatch(transition.before_digest) is None or
            type(transition.after_digest) is not str or
            _DIGEST.fullmatch(transition.after_digest) is None):
        raise PilotError("full-state transition unavailable or malformed; hold")
    owns_snapshot = not db.in_transaction
    if owns_snapshot:
        db.execute("BEGIN")
    try:
        _assert_full_state_transition_in_snapshot(db, transition)
    finally:
        if owns_snapshot:
            db.rollback()


def _assert_full_state_transition_in_snapshot(
    db: sqlite3.Connection, transition: FullStateTransition
) -> None:
    meta = dict(db.execute("SELECT key,value FROM meta WHERE key IN ('owner_uid','schema')"))
    if (meta.get("owner_uid") != str(transition.owner_uid) or
            meta.get("schema") != transition.schema):
        raise PilotError("full-state owner/schema mismatch; hold")
    if transition.phase == "PREPARED":
        raise PilotError("external witness transition prepared; hold")
    if full_pilot_state_digest(db) != transition.after_digest:
        raise PilotError("external witness full-state mismatch; hold")
