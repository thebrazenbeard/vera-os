import dataclasses
import unittest

from veraos.learning_lease import Decision, Lease, Outcome, SyntheticLease, production_admitted


def lease(**changes):
    values = dict(lease_id="lease", task_family="fixture", actions=("a", "b"),
                  generation_sha256="a" * 64, evaluator_sha256="b" * 64,
                  reward_sha256="c" * 64, max_episodes=2, max_steps=3,
                  max_queries=3, max_exploratory_actions=1,
                  exploration_cap_ppm=400_000, expiry=100)
    values.update(changes)
    return Lease(**values)


def decision(l, **changes):
    values = dict(event_id="event1", lease_id=l.lease_id, lease_sha256=l.digest(),
                  generation_sha256=l.generation_sha256, sequence=1, episode=1, step=1,
                  action="a", probabilities_ppm=(700_000, 300_000),
                  selected_propensity_ppm=700_000, predicted_outcome=1)
    values.update(changes)
    return Decision(**values)


def outcome(l, d, **changes):
    values = dict(event_id=d.event_id, lease_id=d.lease_id, lease_sha256=d.lease_sha256,
                  generation_sha256=d.generation_sha256, sequence=d.sequence,
                  episode=d.episode, step=d.step, action=d.action,
                  evaluator_sha256=l.evaluator_sha256, reward_sha256=l.reward_sha256,
                  source="DECLARED_EXTERNAL_VERIFIER", observed_outcome=0)
    values.update(changes)
    return Outcome(**values)


class LeaseTests(unittest.TestCase):
    def test_join_and_idempotence(self):
        l = lease(max_queries=1, max_steps=1)
        s, d = SyntheticLease(l), decision(l)
        o = outcome(l, d)
        self.assertTrue(s.precommit(d, 1))
        self.assertFalse(s.precommit(d, 1))
        self.assertTrue(s.record_outcome(o, 2))
        self.assertFalse(s.record_outcome(o, 2))
        with self.assertRaises(ValueError):
            s.precommit(decision(l, event_id="event2", sequence=2, step=2), 3)
        with self.assertRaises(ValueError):
            s.record_outcome(dataclasses.replace(o, observed_outcome=1), 3)
        with self.assertRaises(ValueError):
            s.precommit(dataclasses.replace(d, predicted_outcome=0), 3)
        self.assertFalse(production_admitted(approval=True))

    def test_outcome_requires_pending_exact_context(self):
        l = lease()
        s, d = SyntheticLease(l), decision(l)
        with self.assertRaises(ValueError):
            s.record_outcome(outcome(l, d), 1)
        s.precommit(d, 1)
        for changes in (dict(event_id="other"), dict(lease_id="other"),
                        dict(lease_sha256="f" * 64), dict(generation_sha256="f" * 64),
                        dict(sequence=2), dict(episode=2), dict(step=2), dict(action="b"),
                        dict(evaluator_sha256="f" * 64), dict(reward_sha256="f" * 64),
                        dict(source="SELF"), dict(source="UNKNOWN")):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                s.record_outcome(outcome(l, d, **changes), 2)
        with self.assertRaises(ValueError):
            s.precommit(decision(l, event_id="event2", sequence=2, step=2), 2)
        self.assertTrue(s.record_outcome(outcome(l, d), 2))

    def test_expiry_revocation_and_backwards_clock_precede_replay(self):
        l = lease()
        s, d = SyntheticLease(l), decision(l)
        s.precommit(d, 5)
        with self.assertRaises(ValueError):
            s.precommit(d, 4)
        with self.assertRaises(ValueError):
            s.record_outcome(outcome(l, d), 100)
        with self.assertRaises(ValueError):
            s.precommit(d, 99)
        s2 = SyntheticLease(l)
        s2.precommit(d, 1)
        s2.revoke()
        for operation in (lambda: s2.precommit(d, 2), lambda: s2.record_outcome(outcome(l, d), 2)):
            with self.assertRaises(ValueError):
                operation()

    def test_budget_sequence_and_exploration(self):
        l = lease(max_exploratory_actions=1)
        s = SyntheticLease(l)
        d = decision(l, action="b", selected_propensity_ppm=300_000)
        s.precommit(d, 1)
        self.assertFalse(s.precommit(d, 1))
        s.record_outcome(outcome(l, d), 2)
        for changes in (dict(sequence=3, step=2), dict(sequence=2, episode=2, step=2),
                        dict(sequence=2, step=2, action="b", selected_propensity_ppm=300_000)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                s.precommit(decision(l, event_id="event2", **changes), 3)
        s.precommit(decision(l, event_id="event2", sequence=2, episode=2, step=1), 3)
        s.record_outcome(outcome(l, decision(l, event_id="event2", sequence=2, episode=2, step=1)), 4)
        with self.assertRaises(ValueError):
            s.precommit(decision(l, event_id="event3", sequence=3, episode=3, step=1), 5)

    def test_tie_first_action_is_greedy_and_mass_cap_is_exact(self):
        l = lease(exploration_cap_ppm=500_000, max_exploratory_actions=0)
        s = SyntheticLease(l)
        with self.assertRaises(ValueError):
            s.precommit(decision(l, action="b", probabilities_ppm=(500_000, 500_000),
                                 selected_propensity_ppm=500_000), 1)
        self.assertTrue(s.precommit(decision(l, probabilities_ppm=(500_000, 500_000),
                                             selected_propensity_ppm=500_000), 1))
        l2 = lease(exploration_cap_ppm=499_999)
        with self.assertRaises(ValueError):
            SyntheticLease(l2).precommit(decision(l2, probabilities_ppm=(500_000, 500_000),
                                                   selected_propensity_ppm=500_000), 1)

    def test_values_types_and_lease_binding(self):
        l = lease()
        for changes in (dict(probabilities_ppm=(float('nan'), 0)),
                        dict(probabilities_ppm=(float('inf'), 0)),
                        dict(probabilities_ppm=(1_000_000,)),
                        dict(probabilities_ppm=(1_000_000, 0, 0)),
                        dict(probabilities_ppm=(True, 999_999)),
                        dict(probabilities_ppm=(0, 1_000_000), selected_propensity_ppm=0),
                        dict(probabilities_ppm=(700_000, 299_999)),
                        dict(selected_propensity_ppm=1), dict(action="unknown"),
                        dict(lease_sha256=dataclasses.replace(l, expiry=101).digest())):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                SyntheticLease(l).precommit(decision(l, **changes), 1)
        class FakeDecision(Decision):
            def __eq__(self, other):
                return True
        with self.assertRaises(ValueError):
            SyntheticLease(l).precommit(FakeDecision(**decision(l).__dict__), 1)
        class FakeString(str):
            def __eq__(self, other):
                return True
        with self.assertRaises(ValueError):
            SyntheticLease(l).precommit(decision(l, lease_sha256=FakeString(l.digest())), 1)
        for changes in (dict(mode="LIVE"), dict(actions=("a", "a")), dict(max_queries=True)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                SyntheticLease(lease(**changes))

    def test_rejection_preserves_budget_and_pending_except_clock(self):
        l = lease(max_queries=1, max_steps=1)
        s, d = SyntheticLease(l), decision(l)
        with self.assertRaises(ValueError):
            s.precommit(dataclasses.replace(d, action="unknown"), 2)
        self.assertTrue(s.precommit(d, 2))
        with self.assertRaises(ValueError):
            s.record_outcome(outcome(l, d, generation_sha256="f" * 64), 3)
        with self.assertRaises(ValueError):
            s.precommit(decision(l, event_id="event2", sequence=2, step=2), 3)
        self.assertFalse(s.precommit(d, 3))
        self.assertTrue(s.record_outcome(outcome(l, d), 3))
        with self.assertRaises(ValueError):
            s.precommit(decision(l, event_id="event2", sequence=2, step=2), 3)


if __name__ == "__main__":
    unittest.main()
