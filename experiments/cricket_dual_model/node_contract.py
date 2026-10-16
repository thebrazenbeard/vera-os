"""Pure candidate node-lease classification, not cryptographic authorization.

It does not execute work or certify a lease signature. The effect broker remains external.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class NodeState:
    node_id: str
    generation: int
    now_epoch: int
    connected: bool
    capabilities: frozenset[str]


@dataclass(frozen=True)
class TaskLease:
    task_id: str
    lease_id: str
    node_id: str
    generation: int
    valid_from: int
    valid_until: int
    capability: str
    effect_class: str
    input_digest: str
    idempotency_key: str


def classify_lease(node: NodeState, lease: TaskLease,
                   completed_keys: frozenset[str]) -> str:
    """A positive outcome is only an advisory classification, never execution authority."""
    if not all((lease.task_id, lease.lease_id, lease.node_id,
                lease.input_digest, lease.idempotency_key)):
        return "HOLD_INCOMPLETE_LEASE"
    if lease.node_id != node.node_id:
        return "HOLD_WRONG_NODE"
    if lease.generation != node.generation:
        return "HOLD_STALE_GENERATION"
    if not lease.valid_from <= node.now_epoch < lease.valid_until:
        return "HOLD_EXPIRED_OR_EARLY"
    if lease.idempotency_key in completed_keys:
        return "HOLD_REPLAY"
    if lease.capability not in node.capabilities:
        return "HOLD_SCOPE"
    if lease.capability == "canonical_memory_write":
        return "HOLD_CANONICAL_MEMORY"
    if lease.effect_class == "protected":
        return "HOLD_EFFECT_BROKER"
    if lease.effect_class not in ("none", "reversible"):
        return "HOLD_UNKNOWN_EFFECT"
    if not node.connected and lease.effect_class != "none":
        return "HOLD_OFFLINE_EFFECT"
    return "READY_LOCAL_PROPOSAL_ONLY"
