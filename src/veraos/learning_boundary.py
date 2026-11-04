"""Synthetic-only quarantine seam. Not an authorization or runtime adapter."""
from dataclasses import dataclass
import hashlib
import json
import re
import sqlite3

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[0-9a-f]{32}\Z")
_FIELDS = {"schema", "event_id", "seed", "action", "outcome", "generation_sha256"}


def _digest(value):
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError("expected lowercase SHA-256")
    return value


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


@dataclass(frozen=True)
class SyntheticEvent:
    event_id: str
    seed: int
    action: int
    outcome: int
    generation_sha256: str

    @classmethod
    def parse(cls, raw):
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > 512:
            raise ValueError("invalid event size")
        value = json.loads(raw, object_pairs_hook=_no_duplicates,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite")))
        if not isinstance(value, dict) or set(value) != _FIELDS or value["schema"] != "synthetic-event-v1":
            raise ValueError("invalid event schema")
        if not isinstance(value["event_id"], str) or not _ID.fullmatch(value["event_id"]):
            raise ValueError("invalid event id")
        for key, maximum in (("seed", 65535), ("action", 15), ("outcome", 1)):
            if type(value[key]) is not int or not 0 <= value[key] <= maximum:
                raise ValueError("invalid synthetic integer")
        return cls(value["event_id"], value["seed"], value["action"], value["outcome"],
                   _digest(value["generation_sha256"]))

    def canonical(self):
        # Revalidate even if a caller directly constructed the dataclass.
        raw = json.dumps({"schema": "synthetic-event-v1", **self.__dict__},
                         sort_keys=True, separators=(",", ":"), allow_nan=False)
        parsed = SyntheticEvent.parse(raw)
        return json.dumps({"schema": "synthetic-event-v1", **parsed.__dict__},
                          sort_keys=True, separators=(",", ":"))


class QuarantineJournal:
    """Local SQLite only. Caller controls local path and lifecycle; not a privacy store."""
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS synthetic_events (event_id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        self.db.commit()

    def append(self, event):
        if type(event) is not SyntheticEvent:
            raise ValueError("synthetic event required")
        body = event.canonical()
        with self.db:
            inserted = self.db.execute(
                "INSERT OR IGNORE INTO synthetic_events VALUES (?, ?)",
                (event.event_id, body),
            ).rowcount == 1
            row = self.db.execute("SELECT body FROM synthetic_events WHERE event_id=?", (event.event_id,)).fetchone()
            if row is None or row[0] != body:
                raise ValueError("event id conflict")
            return inserted

    def close(self):
        self.db.close()


@dataclass(frozen=True)
class CandidateRef:
    base_sha256: str
    tokenizer_sha256: str
    template_sha256: str
    config_sha256: str
    adapter_sha256: str

    def __post_init__(self):
        for value in self.__dict__.values():
            _digest(value)


@dataclass(frozen=True)
class EvaluationRef:
    candidate: CandidateRef
    report_sha256: str

    def __post_init__(self):
        if type(self.candidate) is not CandidateRef:
            raise ValueError("candidate required")
        _digest(self.report_sha256)


@dataclass(frozen=True)
class GenerationSnapshot:
    """A request-bound value, not proof that a provider or generation exists."""
    request_id: str
    candidate: CandidateRef
    evaluation: EvaluationRef

    def __post_init__(self):
        if not isinstance(self.request_id, str) or not _ID.fullmatch(self.request_id):
            raise ValueError("invalid request id")
        if type(self.candidate) is not CandidateRef or type(self.evaluation) is not EvaluationRef:
            raise ValueError("invalid references")
        if self.candidate != self.evaluation.candidate:
            raise ValueError("candidate/evaluation mismatch")


def production_admitted(*_args, **_kwargs):
    """No input, including a claimed approval or PASS, can admit production use."""
    return False
