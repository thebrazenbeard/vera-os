"""Federated cognition V1: local individuality + governed shared orientation.

Single-process reference implementation with separate durable SQLite stores.
It is NOT a cross-host consensus protocol, identity proof, or neural inference
service. External transport must authenticate the actual sender, and an external
authority broker must implement the injected admission functions.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Callable, Mapping, Any


class FederationError(ValueError):
    pass


class AuthorityError(FederationError):
    pass


class StaleState(FederationError):
    pass


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_KINDS = frozenset({"OBSERVATION", "HYPOTHESIS", "PROPOSAL", "OBJECTION"})
_MAX_JSON = 32_768


def _identity(raw: str) -> str:
    if not isinstance(raw, str) or not _ID.fullmatch(raw):
        raise FederationError("Invalid bounded identity")
    return raw


def _canonical(value: Any) -> str:
    def check(v: Any, depth: int = 0) -> None:
        if depth > 16:
            raise FederationError("Structured value too deep")
        if v is None or isinstance(v, (str, bool)):
            return
        if type(v) is int and abs(v) <= 2**53 - 1:
            return
        if isinstance(v, list):
            if len(v) > 256:
                raise FederationError("Structured list too large")
            for i in v:
                check(i, depth + 1)
            return
        if isinstance(v, dict):
            if len(v) > 256 or any(not isinstance(k, str) or
                                   not k.isascii() or not k.isprintable()
                                   for k in v):
                raise FederationError("Structured object keys invalid")
            for i in v.values():
                check(i, depth + 1)
            return
        raise FederationError("Unsupported structured value type")
    check(value)
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False)
    if len(raw.encode("utf8")) > _MAX_JSON:
        raise FederationError("Structured value exceeds size limit")
    return raw


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@dataclass(frozen=True, slots=True)
class Participant:
    """An agent is not a node or model; 'Vera' is the shared referent."""

    identity: str
    node_id: str
    agent_id: str
    model_ref: str | None = None

    def __post_init__(self) -> None:
        for value in (self.identity, self.node_id, self.agent_id):
            _identity(value)
        if self.model_ref is not None:
            _identity(self.model_ref)


@dataclass(frozen=True, slots=True)
class LocalEvent:
    identity: str
    node_id: str
    agent_id: str
    model_ref: str | None
    event_id: str
    kind: str
    entity: str
    predicate: str
    value_json: str
    confidence_ppm: int
    digest: str

    def canonical_content(self) -> str:
        return _canonical({
            "identity": self.identity, "node_id": self.node_id, "agent_id": self.agent_id,
            "model_ref": self.model_ref, "event_id": self.event_id,
            "kind": self.kind, "entity": self.entity, "predicate": self.predicate,
            "value": json.loads(self.value_json), "confidence_ppm": self.confidence_ppm,
        })

    def verify(self) -> None:
        for val in (self.identity, self.node_id, self.agent_id, self.event_id, self.entity,
                    self.predicate):
            _identity(val)
        if self.model_ref is not None:
            _identity(self.model_ref)
        if self.kind not in _KINDS:
            raise FederationError("Invalid event kind")
        if type(self.confidence_ppm) is not int or not 0 <= self.confidence_ppm <= 1_000_000:
            raise FederationError("Invalid confidence")
        if _canonical(json.loads(self.value_json)) != self.value_json:
            raise FederationError("Noncanonical event value")
        if sha256(self.canonical_content().encode("utf8")).hexdigest() != self.digest:
            raise FederationError("Event digest mismatch")

    @property
    def value(self) -> Any:
        return json.loads(self.value_json)


class NodeJournal:
    """Single-node, durable, append-only perspective; no global fact promotion."""

    def __init__(self, db_path: str | Path, *, node_id: str, identity: str = "Vera"):
        self.path = str(db_path)
        self.node_id = _identity(node_id)
        self.identity = _identity(identity)
        with closing(_connect(self.path)) as conn, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS node (id INTEGER PRIMARY KEY CHECK(id=1), node_id TEXT NOT NULL, identity TEXT NOT NULL)")
            conn.execute("""CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE, agent_id TEXT NOT NULL,
                model_ref TEXT, kind TEXT NOT NULL, entity TEXT NOT NULL,
                predicate TEXT NOT NULL, value_json TEXT NOT NULL,
                confidence_ppm INTEGER NOT NULL, digest TEXT NOT NULL)""")
            current = conn.execute("SELECT node_id,identity FROM node WHERE id=1").fetchone()
            if current is None:
                conn.execute("INSERT INTO node VALUES(1,?,?)",(self.node_id,self.identity))
            elif current != (self.node_id,self.identity):
                raise FederationError("Node storage identity mismatch")

    def record(self, participant: Participant, *, event_id: str, kind: str,
               entity: str, predicate: str, value: Any,
               confidence_ppm: int) -> LocalEvent:
        if participant.node_id != self.node_id or participant.identity != self.identity:
            raise FederationError("Participant belongs to another identity or node")
        value_json = _canonical(value)
        event = LocalEvent(self.identity, self.node_id, participant.agent_id, participant.model_ref,
                           event_id, kind, entity, predicate, value_json,
                           confidence_ppm, "")
        # Construction is provisional; semantic validation happens before persistence.
        data = event.canonical_content()
        event = LocalEvent(self.identity,self.node_id,participant.agent_id,participant.model_ref,
                           event_id,kind,entity,predicate,value_json,confidence_ppm,
                           sha256(data.encode("utf8")).hexdigest())
        event.verify()
        with closing(_connect(self.path)) as conn, conn:
            # Serialize the idempotency read and insert across concurrent writers.
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute("SELECT digest FROM events WHERE event_id=?",
                                   (event_id,)).fetchone()
            if current:
                if current[0] != event.digest:
                    raise FederationError("Event ID collision with changed semantics")
                return event
            conn.execute("""INSERT INTO events(event_id,agent_id,model_ref,kind,
                entity,predicate,value_json,confidence_ppm,digest)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (event.event_id,event.agent_id,event.model_ref,event.kind,
                 event.entity,event.predicate,event.value_json,
                 event.confidence_ppm,event.digest))
        return event

    def events(self, *, after_seq: int = 0) -> list[LocalEvent]:
        with closing(_connect(self.path)) as conn:
            rows = conn.execute("""SELECT event_id,agent_id,model_ref,kind,entity,
                predicate,value_json,confidence_ppm,digest
                FROM events WHERE seq>? ORDER BY seq""", (after_seq,)).fetchall()
        result = [LocalEvent(self.identity, self.node_id, row[1], row[2], row[0], *row[3:]) for row in rows]
        for event in result:
            event.verify()
        return result


@dataclass(frozen=True, slots=True)
class Orientation:
    identity: str
    leader_node: str
    epoch: int
    revision: int


# The verifier is trusted runtime code (or a capability broker), not message text.
Authorize = Callable[[str, str, int, int, LocalEvent | None], bool]


class SharedOrientation:
    """Accepts evidence separately from adopting a proposition as shared state.

    In a real distributed deployment this DB must have one fenced authoritative
    writer backed by a real quorum/lease system. This V1 module does not
    implement a consensus algorithm or independent cryptographic authentication.
    """

    def __init__(self, db_path: str | Path, *, identity: str = "Vera",
                 leader_node: str = "VN1", authorize: Authorize | None = None):
        self.path = str(db_path)
        self.authorize = authorize
        identity, leader_node = _identity(identity), _identity(leader_node)
        with closing(_connect(self.path)) as conn, conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS meta (
                id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT NOT NULL,
                leader_node TEXT NOT NULL, epoch INTEGER NOT NULL, revision INTEGER NOT NULL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS candidates (
                node_id TEXT NOT NULL, event_id TEXT NOT NULL,
                digest TEXT NOT NULL, kind TEXT NOT NULL, entity TEXT NOT NULL,
                predicate TEXT NOT NULL, value_json TEXT NOT NULL,
                identity TEXT NOT NULL, agent_id TEXT NOT NULL,
                model_ref TEXT, confidence_ppm INTEGER NOT NULL,
                PRIMARY KEY(node_id,event_id))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS decisions (
                revision INTEGER PRIMARY KEY, epoch INTEGER NOT NULL,
                node_id TEXT NOT NULL, event_id TEXT NOT NULL,
                digest TEXT NOT NULL, accepted_by TEXT NOT NULL,
                entity TEXT NOT NULL, predicate TEXT NOT NULL,
                value_json TEXT NOT NULL,
                UNIQUE(node_id,event_id))""")
            meta = conn.execute("SELECT identity,leader_node FROM meta WHERE id=1").fetchone()
            if meta is None:
                conn.execute("INSERT INTO meta VALUES(1,?,?,1,0)",(identity,leader_node))
            elif meta != (identity,leader_node):
                raise FederationError("Shared identity or leader mismatch")

    def orientation(self) -> Orientation:
        with closing(_connect(self.path)) as conn:
            row = conn.execute("SELECT identity,leader_node,epoch,revision FROM meta WHERE id=1").fetchone()
        return Orientation(*row)

    def stage(self, event: LocalEvent, *, authenticated_node_id: str) -> None:
        """Caller must supply a sender identity verified outside the message."""
        if not isinstance(event, LocalEvent):
            raise FederationError("Expected machine-native local event")
        event.verify()
        if event.node_id != authenticated_node_id:
            raise AuthorityError("Authenticated peer does not match event origin")
        if event.identity != self.orientation().identity:
            raise FederationError("Event claims another shared identity")
        with closing(_connect(self.path)) as conn, conn:
            # Receiver duplicate admission must be atomic under parallel delivery.
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT digest FROM candidates WHERE node_id=? AND event_id=?",
                                    (event.node_id,event.event_id)).fetchone()
            if existing is not None:
                if existing[0] != event.digest:
                    raise FederationError("Conflicting candidate event ID")
                return
            conn.execute("INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (event.node_id,event.event_id,event.digest,event.kind,
                          event.entity,event.predicate,event.value_json,event.identity,
                          event.agent_id,event.model_ref,event.confidence_ppm))

    def accept(self, *, source_node: str, event_id: str, accepted_by: str,
               expected_epoch: int, expected_revision: int) -> int:
        """An authenticated governor explicitly adopts one *proposal*.

        The authorization callback is invoked under the transaction and must
        evaluate the proposed effect and current authority, not sender claims.
        """
        _identity(source_node);_identity(event_id);_identity(accepted_by)
        with closing(_connect(self.path)) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                identity,leader,epoch,revision = conn.execute(
                    "SELECT identity,leader_node,epoch,revision FROM meta WHERE id=1"
                ).fetchone()
                if expected_epoch != epoch or expected_revision != revision:
                    raise StaleState("Orientation revision or authority epoch changed")
                row = conn.execute("""SELECT digest,kind,entity,predicate,value_json,
                    identity,agent_id,model_ref,confidence_ppm
                    FROM candidates WHERE node_id=? AND event_id=?""",
                    (source_node,event_id)).fetchone()
                if row is None or row[1] != "PROPOSAL":
                    raise FederationError("Only staged proposals can become shared commitments")
                if conn.execute("SELECT 1 FROM decisions WHERE node_id=? AND event_id=?",
                                (source_node,event_id)).fetchone() is not None:
                    raise FederationError("Proposal has already been adopted")
                digest,kind,entity,predicate,value_json,shared_id,agent_id,model_ref,confidence = row
                candidate = LocalEvent(shared_id,source_node,agent_id,model_ref,
                                       event_id,kind,entity,predicate,value_json,
                                       confidence,digest)
                candidate.verify()
                if self.authorize is None or not self.authorize(leader,accepted_by,epoch,revision,candidate):
                    raise AuthorityError("No externally verified adoption authority")
                new_rev = revision + 1
                conn.execute("""INSERT INTO decisions VALUES(?,?,?,?,?,?,?,?,?)""",
                             (new_rev,epoch,source_node,event_id,digest,accepted_by,
                              entity,predicate,value_json))
                conn.execute("UPDATE meta SET revision=? WHERE id=1",(new_rev,))
                conn.commit()
                return new_rev
            except Exception:
                conn.rollback()
                raise

    def latest(self, entity: str, predicate: str) -> Any | None:
        with closing(_connect(self.path)) as conn:
            row = conn.execute("""SELECT value_json FROM decisions
                WHERE entity=? AND predicate=? ORDER BY revision DESC LIMIT 1""",
                (entity,predicate)).fetchone()
        return json.loads(row[0]) if row else None

    def decisions(self) -> list[tuple]:
        with closing(_connect(self.path)) as conn:
            return conn.execute("""SELECT revision,epoch,node_id,event_id,digest,
                accepted_by,entity,predicate,value_json FROM decisions
                ORDER BY revision""").fetchall()
