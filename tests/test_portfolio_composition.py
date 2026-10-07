from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from veraos.composition import validate_manifest


class PortfolioCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = (
            ROOT
            / "architecture"
            / "portfolio"
            / "VERA_OS_PORTFOLIO_COMPOSITION_V1.json"
        )
        self.manifest = json.loads(self.path.read_text(encoding="utf-8"))

    def test_manifest_validates(self) -> None:
        validate_manifest(self.manifest)

    def test_all_current_inventory_repositories_are_represented_once(self) -> None:
        repos = [item["repository"] for item in self.manifest["repositories"]]
        self.assertEqual(86, len(repos))
        self.assertEqual(len(repos), len(set(repos)))
        self.assertEqual(81, self.manifest["counts"]["integrated"])
        self.assertEqual(5, self.manifest["counts"]["excluded"])

    def test_archived_repositories_are_excluded_and_nonarchived_are_integrated(self) -> None:
        for item in self.manifest["repositories"]:
            if item["archived"]:
                self.assertEqual(item["disposition"], "EXCLUDED")
                self.assertEqual(item["exclusion_reason"], "ARCHIVED")
            else:
                self.assertEqual(item["disposition"], "INTEGRATED")

    def test_core_runtime_owners_are_exact_and_non_ambient(self) -> None:
        roles = self.manifest["runtime_roles"]
        self.assertEqual(
            roles["identity_runtime"]["repository"],
            "thebrazenbeard/vera-mono",
        )
        self.assertEqual(
            roles["portfolio_coordinator"]["repository"],
            "thebrazenbeard/portal",
        )
        self.assertEqual(
            roles["portfolio_discovery"]["repository"],
            "thebrazenbeard/discovery",
        )
        self.assertEqual(
            roles["reasoning_architecture"]["repository"],
            "thebrazenbeard/rezon",
        )
        self.assertEqual(
            roles["model_composition"]["repository"],
            "thebrazenbeard/mosaic",
        )
        self.assertEqual(
            roles["failure_correction"]["repository"],
            "thebrazenbeard/fuckup",
        )
        self.assertEqual(
            roles["preactive_admission"]["repository"],
            "thebrazenbeard/pre-active",
        )
        self.assertEqual(
            roles["volition"]["repository"],
            "thebrazenbeard/volition",
        )
        self.assertFalse(
            self.manifest["authority"]["ambient_protected_effect_authority"]
        )
        self.assertEqual(
            self.manifest["authority"]["protected_effect_authority_source"],
            "PATRICK_EXPLICIT_EXACT_TARGET_EFFECT",
        )
        self.assertFalse(roles["effect_execution"]["protected_effect_authority"])
        self.assertIn(
            "thebrazenbeard/project-runner",
            roles["effect_execution"]["repositories"],
        )
        self.assertIn(
            "thebrazenbeard/executor",
            roles["effect_execution"]["repositories"],
        )

    def test_cognition_provider_is_optional_and_model_agnostic(self) -> None:
        provider = self.manifest["runtime_roles"]["cognition_provider_router"]
        model = self.manifest["runtime_roles"]["model_production"]
        policy = self.manifest["model_policy"]

        self.assertEqual(provider["repository"], "thebrazenbeard/portal")
        self.assertEqual(
            provider["provider_schema"],
            "VERA_OS_COGNITION_PROVIDER_V1",
        )
        self.assertFalse(provider["provider_required_for_boot"])
        self.assertEqual(
            provider["reasoning_owner"],
            "thebrazenbeard/rezon",
        )

        self.assertEqual(
            model["repository"],
            "thebrazenbeard/vera_model_training",
        )
        self.assertEqual(model["integration"], "OPTIONAL_LOCAL_PROVIDER")
        self.assertFalse(model["is_identity_authority"])
        self.assertFalse(model["route_authority"])
        self.assertFalse(model["protected_effect_authority"])

        self.assertFalse(policy["veraos_requires_trained_vera_model"])
        self.assertEqual(
            policy["candidate_schema"],
            "VERA_OS_LOCAL_MODEL_PROVIDER_CANDIDATE_V1",
        )
        self.assertEqual(policy["route_class"], "COGNITION_ONLY")
        self.assertFalse(policy["identity_authority"])
        self.assertFalse(policy["canonical_memory_write_authority"])
        self.assertFalse(policy["protected_effect_authority"])
        self.assertTrue(
            policy["final_qualification_issuer_must_differ_from_producer"]
        )
        self.assertTrue(policy["qualification_must_bind_artifact_manifest"])

    def test_mosaic_is_optional_composition_not_identity_or_reasoning_owner(self) -> None:
        mosaic = self.manifest["runtime_roles"]["model_composition"]
        self.assertEqual(mosaic["repository"], "thebrazenbeard/mosaic")
        self.assertEqual(mosaic["integration"], "OPTIONAL_COGNITION_COMPOSITION")
        self.assertEqual(
            mosaic["provider_contract"],
            "VERA_OS_COGNITION_PROVIDER_V1",
        )
        self.assertEqual(
            mosaic["canonical_runtime_owner"],
            "thebrazenbeard/vera-mono",
        )
        self.assertEqual(mosaic["reasoning_owner"], "thebrazenbeard/rezon")
        self.assertEqual(mosaic["route_owner"], "thebrazenbeard/portal")
        self.assertEqual(
            mosaic["qualification_state"],
            "RESEARCH_ONLY_NOT_ROUTE_ELIGIBLE",
        )
        self.assertFalse(mosaic["runtime_authority"])
        self.assertFalse(mosaic["identity_authority"])
        self.assertFalse(mosaic["canonical_memory_write_authority"])
        self.assertFalse(mosaic["protected_effect_authority"])

    def test_historical_lineages_are_integrated_as_provenance_not_runtime_authority(self) -> None:
        by_repo = {
            item["repository"]: item
            for item in self.manifest["repositories"]
        }
        for repo in (
            "thebrazenbeard/vera",
            "thebrazenbeard/vera-R9A0",
            "thebrazenbeard/unbound-sol",
        ):
            self.assertEqual(
                by_repo[repo]["integration_mode"],
                "PROVENANCE",
            )
            self.assertFalse(by_repo[repo]["runtime_authority"])


if __name__ == "__main__":
    unittest.main()
