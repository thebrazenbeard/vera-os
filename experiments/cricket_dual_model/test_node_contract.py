"""No-effects tests for local node lease rehearsal."""
from __future__ import annotations
from dataclasses import replace
import unittest
from node_contract import NodeState, TaskLease, classify_lease


class NodeLeaseTests(unittest.TestCase):
    def setUp(self):
        self.node = NodeState("lappy", 4, 100, True,
                              frozenset({"read_code", "simulate", "canonical_memory_write"}))
        self.lease = TaskLease("task-9", "lease-1", "lappy", 4, 90, 105,
                               "read_code", "none", "sha256:abc", "task-9:1")

    def check(self, want, **fields):
        self.assertEqual(classify_lease(self.node, replace(self.lease, **fields),
                                        frozenset()), want)

    def test_readonly_valid_still_advisory(self):
        self.check("READY_LOCAL_PROPOSAL_ONLY")

    def test_wrong_machine(self):
        self.check("HOLD_WRONG_NODE", node_id="vn1")

    def test_stale_generation(self):
        self.check("HOLD_STALE_GENERATION", generation=3)

    def test_future_or_expired(self):
        self.check("HOLD_EXPIRED_OR_EARLY", valid_from=101)
        self.check("HOLD_EXPIRED_OR_EARLY", valid_until=100)

    def test_no_protected_effect_even_online(self):
        self.check("HOLD_EFFECT_BROKER", effect_class="protected")

    def test_no_canonical_memory(self):
        self.check("HOLD_CANONICAL_MEMORY", capability="canonical_memory_write")

    def test_capability_scope(self):
        self.check("HOLD_SCOPE", capability="merge_main")

    def test_missing_digest(self):
        self.check("HOLD_INCOMPLETE_LEASE", input_digest="")

    def test_completed_idempotency_key(self):
        self.assertEqual(classify_lease(self.node, self.lease,
                         frozenset({"task-9:1"})), "HOLD_REPLAY")

    def test_offline_effects_held(self):
        offline = replace(self.node, connected=False)
        self.assertEqual(classify_lease(offline, replace(
            self.lease, effect_class="reversible"), frozenset()), "HOLD_OFFLINE_EFFECT")
        self.assertEqual(classify_lease(offline, self.lease, frozenset()),
                         "READY_LOCAL_PROPOSAL_ONLY")

    def test_unknown_effect(self):
        self.check("HOLD_UNKNOWN_EFFECT", effect_class="unclassified")


if __name__ == "__main__":
    unittest.main()
