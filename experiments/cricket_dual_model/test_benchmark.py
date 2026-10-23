"""Contract tests for synthetic benchmark, with no network or model calls."""
from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark
from cricket import ReviewRequest

ROOT = Path(__file__).resolve().parent

class FakeCritic:
    digest = "distinct-test-artifact"
    model = "fake"
    def __init__(self, findings):
        self.findings = findings
    def critique(self, *, prompt, request):
        return self.findings

class FailingCritic:
    digest = "unknown-test-artifact"
    model = "fake"
    def critique(self, *, prompt, request):
        raise ValueError("malformed model output")

class BenchmarkTests(unittest.TestCase):
    def test_seed_is_explicitly_synthetic_and_unique(self):
        cases = benchmark.read_cases(ROOT / "cases.json")
        self.assertEqual(len(cases), 14)
        self.assertEqual(len({x["id"] for x in cases}), 14)

    def test_current_cricket_baseline_is_measured_not_assumed(self):
        result = benchmark.run(benchmark.read_cases(ROOT / "cases.json"), mode="kernel")
        self.assertEqual(result["summary"]["scored"], 14)
        self.assertEqual(result["summary"]["true_positives"], 4)
        self.assertEqual(result["summary"]["false_positives"], 0)
        self.assertEqual(result["summary"]["false_negatives"], 4)

    def test_model_cannot_override_host_protected_block(self):
        cases = benchmark.read_cases(ROOT / "cases.json")[:1]
        result = benchmark.run(cases, mode="ollama", critic=FakeCritic([]))
        self.assertEqual(result["results"][0]["predicted"], "BLOCK")

    def test_model_generated_block_is_downgraded(self):
        cases = [benchmark.read_cases(ROOT / "cases.json")[11]]
        finding = {"severity": "BLOCK", "rule_id": "CRICKET.NEURAL.TEST",
                   "title": "Unsupported veto", "rationale": "Mock",
                   "evidence": "", "recommendation": "Recheck"}
        result = benchmark.run(cases, mode="ollama", critic=FakeCritic([finding]))
        self.assertEqual(result["results"][0]["predicted"], "CHALLENGE")

    def test_model_error_is_unknown_not_pass(self):
        case = benchmark.read_cases(ROOT / "cases.json")[11]
        result = benchmark.run([case], mode="ollama", critic=FailingCritic())
        self.assertEqual(result["summary"]["unknown"], 1)
        self.assertIsNone(result["results"][0]["predicted"])

    def test_duplicate_case_ids_rejected(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            cases = benchmark.read_cases(ROOT / "cases.json")
            path.write_text(json.dumps({"schema": "VERAOS_CRICKET_SYNTHETIC_SEED_V1",
                                        "cases": [cases[0], cases[0]]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                benchmark.read_cases(path)

    @patch.object(benchmark, "post_local")
    def test_distinct_role_rejects_identical_artifact(self, request):
        request.return_value = {"models": [{"name": "small:test", "digest": "hash-main"}]}
        with self.assertRaises(ValueError):
            benchmark.OllamaCritic("small:test", core_digest="hash-main",
                                   independent_claim=True)

    @patch.object(benchmark, "post_local")
    def test_distinct_role_requires_known_primary_digest(self, request):
        request.return_value = {"models": [{"name": "small:test", "digest": "hash-new"}]}
        with self.assertRaises(ValueError):
            benchmark.OllamaCritic("small:test", independent_claim=True)

    @patch.object(benchmark, "post_local")
    def test_fake_model_evidence_not_in_candidate_rejected(self, request):
        request.side_effect = [
            {"models": [{"name": "small:test", "digest": "hash-new"}]},
            {"message": {"content": json.dumps({"findings": [
                {"severity": "CHALLENGE", "evidence": "I never said this"}
            ]})}},
        ]
        critic = benchmark.OllamaCritic("small:test")
        case = benchmark.read_cases(ROOT / "cases.json")[11]
        with self.assertRaises(ValueError):
            critic.critique(prompt="check", request=ReviewRequest.from_dict(case["request"]))

    @patch.object(benchmark, "post_local")
    def test_malformed_model_json_rejected(self, request):
        request.side_effect = [
            {"models": [{"name": "small:test", "digest": "hash-new"}]},
            {"message": {"content": "NOT JSON"}},
        ]
        critic = benchmark.OllamaCritic("small:test")
        case = benchmark.read_cases(ROOT / "cases.json")[11]
        with self.assertRaises(ValueError):
            critic.critique(prompt="check", request=ReviewRequest.from_dict(case["request"]))

if __name__ == "__main__":
    unittest.main()
