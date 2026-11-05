"""Source-only checker for an externally authenticated recovery checkpoint.

There is deliberately NO checkpoint issuer, file-backed fallback, socket,
Windows bridge, or automatic admission hook here. A checkpoint from JSON,
the pilot directory, or another same-UID process is not trusted authority.
The caller must prove separately that the checkpoint came from a host-owned,
rollback-resistant issuer before using this comparison as a gate.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import sqlite3

from .wsl_ipc import _keyed_ledger_digest, _require_keyed_ledger_schema
from .wsl_pilot import PilotError, SCHEMA


_DIGEST = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


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
