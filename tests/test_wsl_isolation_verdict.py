"""Source-only denial matrix regression; never a real OS isolation probe."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veraos.worker_isolation_verdict import (  # noqa: E402
    REQUIRED_PROBES, SCHEMA, assess_reported_denials,
)


def _complete_claim():
    return {
        "schema": SCHEMA, "worker_role": "inspect",
        "worker_uid": 2001, "coordinator_uid": 1000,
        "probes": {name: True for name in REQUIRED_PROBES},
    }


class IsolationDenialReportTests(unittest.TestCase):
    def assert_held(self, report):
        verdict = assess_reported_denials(report)
        self.assertEqual(verdict.evidence, "CALLER_SUPPLIED_SOURCE_REPORT")
        self.assertEqual(verdict.production_worker_isolation, "HOLD")
        self.assertEqual(verdict.protected_effects, "DENIED")
        return verdict

    def test_perfect_forged_claim_only_reports_completeness(self):
        verdict = self.assert_held(_complete_claim())
        self.assertTrue(verdict.report_complete)
        self.assertEqual(verdict.reported_probe_failures, ())
        self.assertIn("reported_denials_complete_but_untrusted", verdict.reasons)
        with self.assertRaises(FrozenInstanceError):
            verdict.protected_effects = "GRANTED"

    def test_missing_extra_and_malformed_fields_never_qualify(self):
        for change in ("missing", "extra", "wrong_schema", "wrong_role",
                       "same_uid", "root_uid", "bool_uid", "string_uid",
                       "negative_parent", "no_probes", "extra_probe"):
            report = _complete_claim()
            if change == "missing":
                del report["worker_uid"]
            elif change == "extra":
                report["host_signature"] = "valid"
            elif change == "wrong_schema":
                report["schema"] = "veraos.worker-isolation-denial.v999"
            elif change == "wrong_role":
                report["worker_role"] = "state"
            elif change == "same_uid":
                report["worker_uid"] = 1000
            elif change == "root_uid":
                report["worker_uid"] = 0
            elif change == "bool_uid":
                report["worker_uid"] = True
            elif change == "string_uid":
                report["worker_uid"] = "2001"
            elif change == "negative_parent":
                report["coordinator_uid"] = -1
            elif change == "no_probes":
                report["probes"] = {}
            elif change == "extra_probe":
                report["probes"]["permission_granted"] = True
            with self.subTest(change=change):
                self.assertFalse(self.assert_held(report).report_complete)

    def test_every_missing_failed_or_untyped_probe_is_a_hold(self):
        for probe in sorted(REQUIRED_PROBES):
            for mode in ("missing", "failed", "string", "integer", "null"):
                report = _complete_claim()
                if mode == "missing":
                    del report["probes"][probe]
                else:
                    report["probes"][probe] = {
                        "failed": False, "string": "true", "integer": 1,
                        "null": None,
                    }[mode]
                with self.subTest(probe=probe, mode=mode):
                    verdict = self.assert_held(report)
                    self.assertFalse(verdict.report_complete)
                    if mode != "missing":
                        self.assertIn(probe, verdict.reported_probe_failures)

    def test_untrusted_mapping_and_hostile_object_not_inspected(self):
        class Hostile(dict):
            def keys(self):
                raise AssertionError("should not invoke caller getter")

        class HostileObject:
            def __bool__(self):
                raise AssertionError("should not inspect")

        for report in (Hostile(_complete_claim()), HostileObject(), None,
                       [], "valid", True):
            with self.subTest(report=type(report).__name__):
                self.assertFalse(self.assert_held(report).report_complete)


if __name__ == "__main__":
    unittest.main()
