from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from veraos.portfolio_implementation import (
    PortfolioImplementationError,
    validate_implementation_plan,
)


PLAN = (
    ROOT
    / "architecture"
    / "portfolio"
    / "VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json"
)
CAPABILITY_MAP = (
    ROOT
    / "architecture"
    / "capabilities"
    / "VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json"
)
COMPOSITION = (
    ROOT
    / "architecture"
    / "portfolio"
    / "VERA_OS_PORTFOLIO_COMPOSITION_V1.json"
)


class PortfolioImplementationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = json.loads(PLAN.read_text(encoding="utf-8"))
        cls.capability_map = json.loads(CAPABILITY_MAP.read_text(encoding="utf-8"))
        cls.composition = json.loads(COMPOSITION.read_text(encoding="utf-8"))

    def test_every_current_repository_has_one_implementation_decision(self) -> None:
        validate_implementation_plan(
            self.plan,
            self.capability_map,
            self.composition,
        )
        rows = self.plan["repositories"]
        self.assertEqual(86, len(rows))
        self.assertEqual(86, len({row["repository"] for row in rows}))
        self.assertEqual(81, self.plan["inventory"]["active_or_available"])
        self.assertEqual(5, self.plan["inventory"]["archived"])

    def test_canonical_runtime_absorption_preserves_repository_primary_roles(self) -> None:
        absorption = self.plan["canonical_runtime_absorption"]
        self.assertFalse(absorption["direct_sibling_runtime_dependency"])
        by_source = {
            row["repository"]: row
            for row in absorption["sources"]
        }
        self.assertEqual(
            {
                "thebrazenbeard/Attune",
                "thebrazenbeard/ingest",
                "thebrazenbeard/intranel",
                "thebrazenbeard/project-lantern",
                "thebrazenbeard/roots",
                "thebrazenbeard/skeletonkey",
                "thebrazenbeard/vera-works",
            },
            set(by_source),
        )
        by_repo = {row["repository"]: row for row in self.plan["repositories"]}
        self.assertEqual(
            "COGNITIVE_RESEARCH_OR_SUBSYSTEM",
            by_repo["thebrazenbeard/Attune"]["implementation_class"],
        )
        self.assertEqual(
            "PORTAL_MANAGED_PROJECT",
            by_repo["thebrazenbeard/vera-works"]["implementation_path"],
        )
        self.assertEqual(
            "ABSORBED_MECHANISMS_ONLY",
            by_source["thebrazenbeard/vera-works"]["scope"],
        )

    def test_direct_sibling_runtime_dependency_is_rejected(self) -> None:
        bad = copy.deepcopy(self.plan)
        bad["repositories"][0]["direct_sibling_runtime_dependency"] = True
        with self.assertRaisesRegex(
            PortfolioImplementationError,
            "direct sibling runtime dependency forbidden",
        ):
            validate_implementation_plan(bad, self.capability_map, self.composition)

    def test_exact_head_drift_is_rejected(self) -> None:
        bad = copy.deepcopy(self.plan)
        target = next(
            row for row in bad["repositories"]
            if row["repository"] == "thebrazenbeard/portal"
        )
        target["exact_head"] = "0" * 40
        with self.assertRaisesRegex(
            PortfolioImplementationError,
            "exact-head mismatch",
        ):
            validate_implementation_plan(bad, self.capability_map, self.composition)

    def test_archived_repository_cannot_activate(self) -> None:
        bad = copy.deepcopy(self.plan)
        target = next(row for row in bad["repositories"] if row["archived"])
        target["activation_policy"] = "ON_DEMAND"
        with self.assertRaisesRegex(
            PortfolioImplementationError,
            "cannot be activated",
        ):
            validate_implementation_plan(bad, self.capability_map, self.composition)

    def test_vera_works_remains_managed_project_not_absorbed_runtime_donor(self) -> None:
        by_repo = {row["repository"]: row for row in self.plan["repositories"]}
        vera_works = by_repo["thebrazenbeard/vera-works"]
        self.assertEqual("MANAGED_APPLICATION_OR_PROJECT", vera_works["implementation_class"])
        self.assertEqual("PORTAL_MANAGED_PROJECT", vera_works["implementation_path"])
    def test_mediaphile_split_is_considered_but_not_promoted_from_plan_only(self) -> None:
        by_repo = {row["repository"]: row for row in self.plan["repositories"]}
        self.assertEqual(
            "PLAN_ONLY",
            by_repo["thebrazenbeard/mediaphile-client"]["source_maturity"],
        )
        self.assertEqual(
            "PLAN_ONLY",
            by_repo["thebrazenbeard/mediaphile-server"]["source_maturity"],
        )
        self.assertEqual(
            "PORTAL_MANAGED_PROJECT",
            by_repo["thebrazenbeard/mediaphile-server"]["implementation_path"],
        )


if __name__ == "__main__":
    unittest.main()
