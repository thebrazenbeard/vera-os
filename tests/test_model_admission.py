from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from veraos.model_admission import (
    ModelAdmissionError,
    local_model_route_eligible,
    validate_local_model_provider_candidate,
)


def candidate() -> dict:
    return {
        "schema": "VERA_OS_LOCAL_MODEL_PROVIDER_CANDIDATE_V1",
        "artifact_id": "vera-qwen35-test",
        "producer": {
            "repository": "thebrazenbeard/model-training",
            "source_branch": "work/test",
            "source_commit": "1" * 40,
        },
        "base": {
            "repository": "example/base",
            "revision": "2" * 40,
            "format": "Hugging Face sharded safetensors",
        },
        "artifacts": [
            {"path": "adapter_model.safetensors", "sha256": "3" * 64},
            {"path": "adapter_config.json", "sha256": "4" * 64},
        ],
        "training": {
            "artifact_manifest_sha256": "5" * 64,
            "training_corpus_id": "CORPUS_V1",
            "train_sha256": "6" * 64,
            "receipt_sha256": "7" * 64,
            "runtime_binding_sha256": "8" * 64,
        },
        "qualification": {
            "status": "PASS",
            "issuer_repository": "thebrazenbeard/vera-os",
            "artifact_manifest_sha256": "5" * 64,
            "suite_sha256": "9" * 64,
            "runtime_binding_sha256": "a" * 64,
            "capabilities": ["text", "reasoning"],
        },
        "authority": {
            "identity_authority": False,
            "canonical_memory_write_authority": False,
            "protected_effect_authority": False,
            "browser_authority": False,
        },
        "admission": {
            "status": "VERAOS_ROUTE_ELIGIBLE",
            "route_class": "COGNITION_ONLY",
            "selector_owner": "thebrazenbeard/portal",
            "identity_runtime_owner": "thebrazenbeard/vera-mono",
            "integration": "OPTIONAL_PROVIDER",
        },
    }


class ModelAdmissionTests(unittest.TestCase):
    def test_exact_candidate_is_structurally_valid_but_not_route_eligible(self) -> None:
        item = candidate()
        validate_local_model_provider_candidate(item)
        self.assertFalse(local_model_route_eligible(item))

    def test_claimed_pass_and_forged_hashes_cannot_admit_route(self) -> None:
        item = candidate()
        item["artifact_id"] = "attacker-synthetic-forgery"
        item["producer"]["source_commit"] = "f" * 40
        item["base"]["repository"] = "attacker/unverified-weights"
        item["base"]["revision"] = "d" * 40
        item["training"]["train_sha256"] = "f" * 64
        item["training"]["receipt_sha256"] = "e" * 64
        item["qualification"]["suite_sha256"] = "d" * 64
        validate_local_model_provider_candidate(item)
        self.assertFalse(local_model_route_eligible(item))

    def test_training_repo_cannot_self_issue_final_qualification(self) -> None:
        item = candidate()
        item["qualification"]["issuer_repository"] = "thebrazenbeard/model-training"

        with self.assertRaisesRegex(ModelAdmissionError, "separate"):
            validate_local_model_provider_candidate(item)

    def test_legacy_producer_alias_not_accepted_as_current_source(self) -> None:
        item = candidate()
        item["producer"]["repository"] = "thebrazenbeard/vera_model_training"
        with self.assertRaisesRegex(ModelAdmissionError, "producer"):
            validate_local_model_provider_candidate(item)

    def test_arbitrary_qualifier_cannot_claim_final_admission(self) -> None:
        item = candidate()
        item["qualification"]["issuer_repository"] = "untrusted/fake-reviewer"
        with self.assertRaisesRegex(ModelAdmissionError, "VeraOS"):
            validate_local_model_provider_candidate(item)

    def test_qualification_must_bind_exact_artifact_manifest(self) -> None:
        item = candidate()
        item["qualification"]["artifact_manifest_sha256"] = "b" * 64

        with self.assertRaisesRegex(ModelAdmissionError, "exact training artifact"):
            validate_local_model_provider_candidate(item)

    def test_authority_inflation_is_rejected(self) -> None:
        for key in (
            "identity_authority",
            "canonical_memory_write_authority",
            "protected_effect_authority",
            "browser_authority",
        ):
            item = candidate()
            item["authority"][key] = True
            with self.assertRaises(ModelAdmissionError):
                validate_local_model_provider_candidate(item)

    def test_nonpass_candidate_must_remain_held(self) -> None:
        item = candidate()
        item["qualification"]["status"] = "HOLD"
        item["admission"]["status"] = "HELD"

        validate_local_model_provider_candidate(item)
        self.assertFalse(local_model_route_eligible(item))

    def test_provider_does_not_name_or_own_effect_executor(self) -> None:
        item = candidate()
        self.assertNotIn("effect_executor_owner", item["admission"])
        validate_local_model_provider_candidate(item)

    def test_route_owner_boundaries_are_fail_closed(self) -> None:
        changes = (
            ("selector_owner", "thebrazenbeard/vera_model_training"),
            ("identity_runtime_owner", "thebrazenbeard/portal"),
            ("integration", "REQUIRED_PROVIDER"),
        )
        for key, value in changes:
            item = candidate()
            item["admission"][key] = value
            with self.assertRaises(ModelAdmissionError):
                validate_local_model_provider_candidate(item)


if __name__ == "__main__":
    unittest.main()

