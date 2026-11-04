"""Trusted in-memory synthetic fixture; not a security boundary."""
from dataclasses import asdict, dataclass
import hashlib
import json
import re
import threading

from .learning_lease import Lease, Decision, Outcome, SyntheticLease

_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def _digest(domain, value):
    data = json.dumps({"domain": domain, "value": value}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def _valid_id(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _valid_hash(value):
    return type(value) is str and _HASH.fullmatch(value) is not None


@dataclass(frozen=True)
class RunSpec:
    run_id: str
    max_events: int
    rewards_by_action: tuple


@dataclass(frozen=True)
class Request:
    event_id: str
    generation_sha256: str
    pre_policy_sha256: str


@dataclass(frozen=True)
class Receipt:
    request: Request
    facade_id: str
    sequence: int
    decision: Decision
    outcome: Outcome
    pre_policy_sha256: str
    post_policy_sha256: str
    prior_receipt_sha256: str
    receipt_sha256: str


@dataclass(frozen=True)
class Snapshot:
    run_sha256: str
    policy_sha256: str
    counts: tuple
    reward_sums: tuple
    updates: int
    reserved_events: int
    receipt_sha256: str
    faulted: bool
    revoked: bool
    watermark: object


class _Facade:
    def __init__(self, broker, facade_id):
        self._broker = broker
        self._facade_id = facade_id

    def step(self, request, now):
        return self._broker._step(self._facade_id, request, now)


class SyntheticRun:
    def __init__(self, spec, lease):
        if type(spec) is not RunSpec or type(lease) is not Lease:
            raise ValueError("exact fixture types required")
        lease.validate()
        if (not _valid_id(spec.run_id) or type(spec.max_events) is not int
                or not 1 <= spec.max_events <= min(256, lease.max_steps, lease.max_queries)
                or type(spec.rewards_by_action) is not tuple
                or len(spec.rewards_by_action) != len(lease.actions)
                or any(type(r) is not int or r not in (0, 1)
                       for r in spec.rewards_by_action)):
            raise ValueError("invalid run configuration")
        self._spec = spec
        self._lease = lease
        self._lease_state = SyntheticLease(lease)
        self._lock = threading.Lock()
        self._run_hash = _digest("synthetic-run-config-v1",
                                 {"spec": asdict(spec), "lease_sha256": lease.digest()})
        self._counts = [0] * len(lease.actions)
        self._sums = [0] * len(lease.actions)
        self._updates = 0
        self._reserved = 0
        self._receipts = {}
        self._last_receipt = "0" * 64
        self._watermark = None
        self._revoked = False
        self._faulted = False

    def _policy_hash(self):
        return _digest("synthetic-run-policy-v1", {
            "run_sha256": self._run_hash,
            "generation_sha256": self._lease.generation_sha256,
            "counts": self._counts, "reward_sums": self._sums, "updates": self._updates})

    def snapshot(self):
        with self._lock:
            return Snapshot(self._run_hash, self._policy_hash(), tuple(self._counts),
                            tuple(self._sums), self._updates, self._reserved,
                            self._last_receipt, self._faulted, self._revoked, self._watermark)

    def facade(self, facade_id):
        if type(facade_id) is not str or facade_id not in ("a", "b"):
            raise ValueError("unknown facade")
        return _Facade(self, facade_id)

    def revoke(self):
        with self._lock:
            self._revoked = True
            self._lease_state.revoke()

    def _step(self, facade_id, request, now):
        with self._lock:
            if type(now) is not int or not 0 <= now <= 2**63 - 1:
                raise ValueError("invalid time")
            if self._watermark is not None and now < self._watermark:
                raise ValueError("clock moved backwards")
            self._watermark = now
            if self._revoked or self._faulted or now >= self._lease.expiry:
                raise ValueError("run unavailable")
            if (type(request) is not Request or not _valid_id(request.event_id)
                    or not _valid_hash(request.generation_sha256)
                    or not _valid_hash(request.pre_policy_sha256)):
                raise ValueError("invalid request")
            prior = self._receipts.get(request.event_id)
            if prior is not None:
                if prior.facade_id != facade_id or prior.request != request:
                    raise ValueError("event conflict")
                return prior
            if (request.generation_sha256 != self._lease.generation_sha256
                    or request.pre_policy_sha256 != self._policy_hash()):
                raise ValueError("generation or policy mismatch")
            if self._reserved >= self._spec.max_events:
                raise ValueError("root budget exhausted")
            try:
                self._reserved += 1
                index = next((i for i, n in enumerate(self._counts) if n == 0), None)
                if index is None:
                    index = 0
                    for i in range(1, len(self._counts)):
                        if self._sums[i] * self._counts[index] > self._sums[index] * self._counts[i]:
                            index = i
                count, total = self._counts[index], self._sums[index]
                predicted = int(count > 0 and 2 * total >= count)
                sequence = self._reserved
                d = Decision(request.event_id, self._lease.lease_id, self._lease.digest(),
                             self._lease.generation_sha256, sequence, 1, sequence,
                             self._lease.actions[index],
                             tuple(1_000_000 if i == index else 0 for i in range(len(self._counts))),
                             1_000_000, predicted)
                self._lease_state.precommit(d, now)
                reward = self._spec.rewards_by_action[index]
                o = Outcome(d.event_id, d.lease_id, d.lease_sha256, d.generation_sha256,
                            d.sequence, d.episode, d.step, d.action, self._lease.evaluator_sha256,
                            self._lease.reward_sha256, "DECLARED_EXTERNAL_VERIFIER", reward)
                self._lease_state.record_outcome(o, now)
                self._counts[index] += 1
                self._sums[index] += reward
                self._updates += 1
                fields = dict(request=request, facade_id=facade_id, sequence=sequence,
                              decision=d, outcome=o, pre_policy_sha256=request.pre_policy_sha256,
                              post_policy_sha256=self._policy_hash(),
                              prior_receipt_sha256=self._last_receipt)
                digest = _digest("synthetic-run-receipt-v1",
                                 {k: asdict(v) if k in ("request", "decision", "outcome") else v
                                  for k, v in fields.items()})
                receipt = Receipt(**fields, receipt_sha256=digest)
                self._receipts[request.event_id] = receipt
                self._last_receipt = digest
                return receipt
            except BaseException:
                self._faulted = True
                raise
