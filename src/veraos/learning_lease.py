"""In-memory synthetic fixture contract; not authorization or a runtime adapter."""
from dataclasses import dataclass
import hashlib
import json
import re

_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_SCALE = 1_000_000


def _id(value):
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError("invalid fixture identifier")


def _hash(value):
    if type(value) is not str or not _HASH.fullmatch(value):
        raise ValueError("invalid declared digest")


def _int(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("invalid bounded integer")


@dataclass(frozen=True)
class Lease:
    lease_id: str
    task_family: str
    actions: tuple
    generation_sha256: str
    evaluator_sha256: str
    reward_sha256: str
    max_episodes: int
    max_steps: int
    max_queries: int
    max_exploratory_actions: int
    exploration_cap_ppm: int
    expiry: int
    mode: str = "SHADOW_ONLY"

    def validate(self):
        _id(self.lease_id)
        _id(self.task_family)
        if type(self.actions) is not tuple or not 1 <= len(self.actions) <= 32:
            raise ValueError("invalid action allowlist")
        for action in self.actions:
            _id(action)
        if len(set(self.actions)) != len(self.actions):
            raise ValueError("duplicate action")
        for digest in (self.generation_sha256, self.evaluator_sha256, self.reward_sha256):
            _hash(digest)
        for value in (self.max_episodes, self.max_steps, self.max_queries):
            _int(value, 1, 1_000_000)
        _int(self.exploration_cap_ppm, 0, _SCALE)
        _int(self.max_exploratory_actions, 0, 1_000_000)
        _int(self.expiry, 1, 2**63 - 1)
        if type(self.mode) is not str or self.mode != "SHADOW_ONLY":
            raise ValueError("shadow only")

    def digest(self):
        self.validate()
        raw = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(raw.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class Decision:
    event_id: str
    lease_id: str
    lease_sha256: str
    generation_sha256: str
    sequence: int
    episode: int
    step: int
    action: str
    probabilities_ppm: tuple
    selected_propensity_ppm: int
    predicted_outcome: int


@dataclass(frozen=True)
class Outcome:
    event_id: str
    lease_id: str
    lease_sha256: str
    generation_sha256: str
    sequence: int
    episode: int
    step: int
    action: str
    evaluator_sha256: str
    reward_sha256: str
    source: str
    observed_outcome: int


class SyntheticLease:
    """Single-writer, in-memory state. Caller is responsible for ordering and clock."""
    def __init__(self, lease):
        if type(lease) is not Lease:
            raise ValueError("exact lease required")
        lease.validate()
        self._lease = lease
        self._decisions = {}
        self._outcomes = {}
        self._pending = None
        self._last_time = None
        self._episode = 0
        self._step = 0
        self._revoked = False
        self._explorations = 0

    def _check(self, now):
        _int(now, 0, 2**63 - 1)
        if self._revoked or (self._last_time is not None and now < self._last_time):
            raise ValueError("revoked or clock moved backwards")
        self._last_time = now
        if now >= self._lease.expiry:
            raise ValueError("expired")

    def revoke(self):
        self._revoked = True

    def precommit(self, decision, now):
        self._check(now)
        if type(decision) is not Decision:
            raise ValueError("exact decision required")
        d, lease = decision, self._lease
        for value in (d.event_id, d.lease_id, d.action):
            _id(value)
        _hash(d.generation_sha256)
        _hash(d.lease_sha256)
        for value in (d.sequence, d.episode, d.step):
            _int(value, 1, 1_000_000)
        _int(d.predicted_outcome, 0, 1)
        _int(d.selected_propensity_ppm, 1, _SCALE)
        if type(d.probabilities_ppm) is not tuple or len(d.probabilities_ppm) != len(lease.actions):
            raise ValueError("invalid probabilities")
        for p in d.probabilities_ppm:
            _int(p, 0, _SCALE)
        if (d.lease_id != lease.lease_id or d.lease_sha256 != lease.digest()
                or d.generation_sha256 != lease.generation_sha256
                or d.action not in lease.actions or sum(d.probabilities_ppm) != _SCALE
                or d.selected_propensity_ppm != d.probabilities_ppm[lease.actions.index(d.action)]
                or _SCALE - max(d.probabilities_ppm) > lease.exploration_cap_ppm):
            raise ValueError("decision outside lease")
        if d.event_id in self._decisions:
            if self._decisions[d.event_id] != d:
                raise ValueError("decision id conflict")
            return False
        if self._pending is not None or d.sequence != len(self._decisions) + 1:
            raise ValueError("decision out of order")
        if (d.episode, d.step) not in ((self._episode, self._step + 1), (self._episode + 1, 1)):
            raise ValueError("episode or step out of order")
        exploratory = d.action != lease.actions[d.probabilities_ppm.index(max(d.probabilities_ppm))]
        if (d.episode > lease.max_episodes or d.sequence > lease.max_steps
                or self._explorations + exploratory > lease.max_exploratory_actions
                or d.sequence > lease.max_queries):
            raise ValueError("budget exceeded")
        self._decisions[d.event_id] = d
        self._pending = d.event_id
        self._episode, self._step = d.episode, d.step
        self._explorations += exploratory
        return True

    def record_outcome(self, outcome, now):
        self._check(now)
        if type(outcome) is not Outcome:
            raise ValueError("exact outcome required")
        o, lease = outcome, self._lease
        for value in (o.event_id, o.lease_id, o.action):
            _id(value)
        for value in (o.lease_sha256, o.generation_sha256, o.evaluator_sha256, o.reward_sha256):
            _hash(value)
        for value in (o.sequence, o.episode, o.step):
            _int(value, 1, 1_000_000)
        _int(o.observed_outcome, 0, 1)
        if type(o.source) is not str or o.source != "DECLARED_EXTERNAL_VERIFIER":
            raise ValueError("declared external verifier required")
        if o.event_id in self._outcomes:
            if self._outcomes[o.event_id] != o:
                raise ValueError("outcome id conflict")
            return False
        if self._pending != o.event_id:
            raise ValueError("outcome not pending")
        d = self._decisions[o.event_id]
        if ((o.lease_id, o.lease_sha256, o.generation_sha256, o.sequence, o.episode, o.step, o.action)
                != (d.lease_id, d.lease_sha256, d.generation_sha256, d.sequence, d.episode, d.step, d.action)
                or o.evaluator_sha256 != lease.evaluator_sha256 or o.reward_sha256 != lease.reward_sha256):
            raise ValueError("outcome context mismatch")
        self._outcomes[o.event_id] = o
        self._pending = None
        return True


def production_admitted(*_args, **_kwargs):
    return False
