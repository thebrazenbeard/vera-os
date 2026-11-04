import dataclasses
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from veraos.learning_lease import Lease
from veraos.synthetic_run import Request, RunSpec, SyntheticRun


def lease():
    return Lease("lease", "task", ("first", "second"), "a" * 64,
                 "b" * 64, "c" * 64, 1, 10, 10, 0, 0, 100)


def broker(max_events=3):
    return SyntheticRun(RunSpec("run", max_events, (0, 1)), lease())


def request(b, event):
    return Request(event, "a" * 64, b.snapshot().policy_sha256)


class SyntheticRunTests(unittest.TestCase):
    def test_policy_chain_and_deterministic_receipts(self):
        def execute():
            b = broker()
            receipts = []
            for i in range(3):
                pre = b.snapshot().policy_sha256
                r = b.facade("a").step(request(b, f"e{i}"), i)
                self.assertEqual(r.pre_policy_sha256, pre)
                self.assertEqual(r.post_policy_sha256, b.snapshot().policy_sha256)
                if receipts:
                    self.assertEqual(r.prior_receipt_sha256, receipts[-1].receipt_sha256)
                    self.assertEqual(r.pre_policy_sha256, receipts[-1].post_policy_sha256)
                receipts.append(r)
            self.assertEqual([r.decision.action for r in receipts], ["first", "second", "second"])
            self.assertEqual(b.snapshot().counts, (1, 2))
            self.assertEqual(b.snapshot().reward_sums, (0, 2))
            return receipts
        self.assertEqual(execute(), execute())

    def test_shared_budget_and_historical_replay(self):
        b = broker(2)
        a, other = b.facade("a"), b.facade("b")
        req = request(b, "x")
        first = a.step(req, 1)
        other.step(request(b, "y"), 2)
        self.assertEqual(a.step(req, 3), first)
        with self.assertRaises(ValueError):
            other.step(req, 3)
        with self.assertRaises(ValueError):
            a.step(request(b, "z"), 3)
        self.assertEqual(b.snapshot().reserved_events, 2)

    def test_concurrent_last_slot_has_one_winner(self):
        b = broker(1)
        barrier = threading.Barrier(2)
        def run(event, facade):
            req = request(b, event)
            barrier.wait()
            try:
                return facade.step(req, 1)
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, "x", b.facade("a")),
                       pool.submit(run, "y", b.facade("b"))]
            result = [f.result() for f in futures]
        self.assertEqual(sum(x is not None for x in result), 1)
        self.assertEqual(b.snapshot().updates, 1)

    def test_concurrent_identical_event_updates_once(self):
        b = broker(1)
        facade, req = b.facade("a"), request(b, "x")
        barrier = threading.Barrier(2)
        def run():
            barrier.wait()
            return facade.step(req, 1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run) for _ in range(2)]
            self.assertEqual(futures[0].result(), futures[1].result())
        self.assertEqual(b.snapshot().updates, 1)
        self.assertEqual(b.snapshot().reserved_events, 1)

    def test_invalid_inputs_stale_and_conflicting_replay(self):
        b = broker()
        a = b.facade("a")
        req = request(b, "x")
        a.step(req, 1)
        for bad in (dataclasses.replace(req, generation_sha256="d" * 64),
                    dataclasses.replace(req, pre_policy_sha256="d" * 64),
                    Request("y", "d" * 64, b.snapshot().policy_sha256),
                    Request("z", "a" * 64, req.pre_policy_sha256),
                    Request(True, "a" * 64, b.snapshot().policy_sha256)):
            with self.assertRaises(ValueError):
                a.step(bad, 2)
        self.assertEqual(b.snapshot().updates, 1)

    def test_expiry_revoke_and_clock_precede_replay(self):
        for end in ("expiry", "revoke", "clock"):
            b = broker()
            a, req = b.facade("a"), request(b, "x")
            a.step(req, 2)
            if end == "revoke":
                b.revoke()
            with self.assertRaises(ValueError):
                a.step(req, {"expiry": 100, "revoke": 3, "clock": 1}[end])

    def test_exception_after_reservation_faults_without_refund(self):
        b = broker()
        def fail(*args):
            raise RuntimeError("injected")
        b._lease_state.precommit = fail
        req = request(b, "x")
        with self.assertRaises(RuntimeError):
            b.facade("a").step(req, 1)
        self.assertEqual(b.snapshot().reserved_events, 1)
        self.assertTrue(b.snapshot().faulted)
        with self.assertRaises(ValueError):
            b.facade("a").step(req, 2)

    def test_failure_after_precommit_faults_and_never_replays(self):
        b = broker()
        def fail(*args):
            raise RuntimeError("outcome failed")
        b._lease_state.record_outcome = fail
        req = request(b, "x")
        with self.assertRaises(RuntimeError):
            b.facade("a").step(req, 1)
        self.assertEqual(b.snapshot().reserved_events, 1)
        self.assertEqual(b.snapshot().updates, 0)
        self.assertTrue(b.snapshot().faulted)
        with self.assertRaises(ValueError):
            b.facade("a").step(req, 2)

    def test_predictions_are_computed_from_prior_state(self):
        b = broker()
        receipts = []
        for i in range(3):
            receipts.append(b.facade("a").step(request(b, f"e{i}"), i))
        self.assertEqual([r.decision.predicted_outcome for r in receipts], [0, 0, 1])
        self.assertEqual([r.outcome.observed_outcome for r in receipts], [0, 1, 1])
        self.assertEqual([r.decision.probabilities_ppm for r in receipts],
                         [(1000000, 0), (0, 1000000), (0, 1000000)])

    def test_rejected_new_request_advances_watermark(self):
        b = broker()
        bad = Request("x", "d" * 64, b.snapshot().policy_sha256)
        with self.assertRaises(ValueError):
            b.facade("a").step(bad, 5)
        self.assertEqual(b.snapshot().watermark, 5)
        with self.assertRaises(ValueError):
            b.facade("a").step(request(b, "x"), 4)
        self.assertEqual(b.snapshot().reserved_events, 0)

    def test_strict_config_and_time_validation(self):
        for spec in (RunSpec("run", True, (0, 1)), RunSpec("run", 11, (0, 1)),
                     RunSpec("run", 1, (False, 1)), RunSpec("run", 1, [0, 1]),
                     RunSpec("run", 1, (0,))):
            with self.assertRaises(ValueError):
                SyntheticRun(spec, lease())
        b = broker()
        with self.assertRaises(ValueError):
            b.facade("a").step(request(b, "x"), True)
        self.assertEqual(b.snapshot().reserved_events, 0)


if __name__ == "__main__":
    unittest.main()

