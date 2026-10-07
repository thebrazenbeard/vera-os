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
        self.path = ROOT / "architecture" / "portfolio" / "VERA_OS_PORTFOLIO_COMPOSITION_V1.json"
        self.manifest = json.loads(self.path.read_text(encoding="utf-8"))

    def test_manifest_validates(self) -> None:
        validate_manifest(self.manifest)

    def test_all_84_live_inventory_repositories_are_represented_once(self) -> None:
        repos = [item["repository"] for item in self.manifest["repositories"]]
        self.assertEqual(len(repos), 84)
        self.assertEqual(len(repos), len(set(repos)))

    def test_archived_repositories_are_excluded_and_nonarchived_are_integrated(self) -> None:
        for item in self.manifest["repositories"]:
            if item["archived"]:
                self.assertEqual(item["disposition"], "EXCLUDED")
                self.assertEqual(item["exclusion_reason"], "ARCHIVED")
            else:
                self.assertEqual(item["disposition"], "INTEGRATED")

    def test_core_runtime_owners_are_exact_and_non_ambient(self) -> None:
        roles = self.manifest["runtime_roles"]
        self.assertEqual(roles["identity_runtime"]["repository"], "thebrazenbeard/vera-mono")
        self.assertEqual(roles["portfolio_coordinator"]["repository"], "thebrazenbeard/portal")
        self.assertEqual(roles["preactive_admission"]["repository"], "thebrazenbeard/pre-active")
        self.assertEqual(roles["volition"]["repository"], "thebrazenbeard/volition")
        effect_repo = "thebrazenbeard/" + "fuck" + "up"
        self.assertEqual(roles["effect_executor"]["repository"], effect_repo)
        self.assertFalse(self.manifest["authority"]["ambient_protected_effect_authority"])
        self.assertEqual(
            self.manifest["authority"]["protected_effect_authority_source"],
            "PATRICK_EXPLICIT_EXACT_TARGET_EFFECT",
        )

    def test_model_artifacts_are_cognition_engines_not_identity(self) -> None:
        model = self.manifest["runtime_roles"]["model_production"]
        policy = self.manifest["model_policy"]
        inference = self.manifest["runtime_roles"]["inference_router"]

        self.assertEqual(model["repository"], "thebrazenbeard/vera_model_training")
        self.assertFalse(model["is_identity_authority"])
        self.assertFalse(model["route_authority"])
        self.assertFalse(model["protected_effect_authority"])

        self.assertEqual(
            inference["model_identity_rule"],
            "MODEL_PROVENANCE_IS_NOT_VERA_IDENTITY",
        )
        self.assertEqual(
            inference["candidate_schema"],
            "VERA_OS_COGNITION_ENGINE_CANDIDATE_V1",
        )
        self.assertEqual(
            inference["qualification_binding_rule"],
            "EXACT_ARTIFACT_MANIFEST_AND_SEPARATE_ISSUER",
        )

        self.assertEqual(policy["trained_model_role"], "COGNITION_ENGINE")
        self.assertEqual(policy["route_class"], "COGNITION_ONLY")
        self.assertFalse(policy["identity_authority"])
        self.assertFalse(policy["canonical_memory_write_authority"])
        self.assertFalse(policy["protected_effect_authority"])
        self.assertTrue(
            policy["final_qualification_issuer_must_differ_from_producer"]
        )
        self.assertTrue(policy["qualification_must_bind_artifact_manifest"])

    def test_historical_lineages_are_integrated_as_provenance_not_runtime_authority(self) -> None:
        by_repo = {item["repository"]: item for item in self.manifest["repositories"]}
        for repo in (
            "thebrazenbeard/vera",
            "thebrazenbeard/vera-R9A0",
            "thebrazenbeard/unbound-sol",
        ):
            self.assertEqual(by_repo[repo]["integration_mode"], "PROVENANCE")
            self.assertFalse(by_repo[repo]["runtime_authority"])


if __name__ == "__main__":
    unittest.main()
