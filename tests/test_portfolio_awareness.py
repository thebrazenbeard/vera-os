from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from veraos.portfolio_awareness import (
    PortfolioAwarenessError,
    require_capability_dispositions,
    require_current_catalog,
    validate_capability_map,
)


CAPABILITY_MAP = (
    ROOT
    / "architecture"
    / "capabilities"
    / "VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json"
)


class PortfolioAwarenessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capability_map = json.loads(CAPABILITY_MAP.read_text(encoding="utf-8"))

    def test_private_map_covers_exactly_all_current_repositories(self) -> None:
        validate_capability_map(self.capability_map)
        records = self.capability_map["repositories"]
        self.assertEqual(86, len(records))
        self.assertEqual(86, len({r["repository"] for r in records}))
        self.assertEqual(81, self.capability_map["inventory"]["active_or_available"])
        self.assertEqual(5, self.capability_map["inventory"]["archived"])

    def test_current_catalog_accepts_exact_bound_inventory(self) -> None:
        live = [
            {
                "repository": row["repository"],
                "exact_head": row["exact_head"],
            }
            for row in self.capability_map["repositories"]
        ]
        require_current_catalog(self.capability_map, live)

    def test_changed_rezon_head_holds_assignment_and_requires_refresh(self) -> None:
        live = [
            {
                "repository": row["repository"],
                "exact_head": row["exact_head"],
            }
            for row in self.capability_map["repositories"]
        ]
        for row in live:
            if row["repository"] == "thebrazenbeard/rezon":
                row["exact_head"] = "0" * 40
                break

        with self.assertRaisesRegex(PortfolioAwarenessError, "rezon"):
            require_current_catalog(self.capability_map, live)

    def test_inventory_membership_change_holds_assignment_and_requires_refresh(self) -> None:
        live = [
            {
                "repository": row["repository"],
                "exact_head": row["exact_head"],
            }
            for row in self.capability_map["repositories"]
        ]
        live.pop()

        with self.assertRaisesRegex(PortfolioAwarenessError, "inventory changed"):
            require_current_catalog(self.capability_map, live)

    def test_reasoning_architecture_is_owned_by_rezon(self) -> None:
        owners = self.capability_map["capabilities"]["reasoning_architecture"]["owners"]
        self.assertIn("thebrazenbeard/rezon", owners)

    def test_discovery_owns_portfolio_capability_discovery(self) -> None:
        owners = self.capability_map["capabilities"]["portfolio_capability_discovery"]["owners"]
        self.assertIn("thebrazenbeard/discovery", owners)

    def test_failure_prevention_is_owned_by_fuckup(self) -> None:
        owners = self.capability_map["capabilities"]["failure_correction_prevention"]["owners"]
        self.assertIn("thebrazenbeard/fuckup", owners)

    def test_new_reasoning_architecture_without_rezon_disposition_fails(self) -> None:
        proposal = {
            "schema": "VERA_OS_CAPABILITY_ASSIGNMENT_PROPOSAL_V1",
            "proposal_id": "bad-reasoning-redesign",
            "capability": "reasoning_architecture",
            "proposed_owner": "thebrazenbeard/vera-os",
            "existing_owner_dispositions": [],
        }
        with self.assertRaisesRegex(PortfolioAwarenessError, "thebrazenbeard/rezon"):
            require_capability_dispositions(self.capability_map, proposal)

    def test_reasoning_reuse_disposition_passes(self) -> None:
        proposal = {
            "schema": "VERA_OS_CAPABILITY_ASSIGNMENT_PROPOSAL_V1",
            "proposal_id": "veraos-reuses-rezon",
            "capability": "reasoning_architecture",
            "proposed_owner": "thebrazenbeard/vera-os",
            "existing_owner_dispositions": [
                {
                    "repository": "thebrazenbeard/rezon",
                    "disposition": "REUSE",
                    "evidence": "Rezon is the executable multi-faceted reasoning system.",
                }
            ],
        }
        require_capability_dispositions(self.capability_map, proposal)

    def test_every_known_owner_requires_explicit_disposition(self) -> None:
        data = copy.deepcopy(self.capability_map)
        data["capabilities"]["reasoning_architecture"]["owners"].append(
            "thebrazenbeard/bt2"
        )
        proposal = {
            "schema": "VERA_OS_CAPABILITY_ASSIGNMENT_PROPOSAL_V1",
            "proposal_id": "partial-disposition",
            "capability": "reasoning_architecture",
            "proposed_owner": "thebrazenbeard/vera-os",
            "existing_owner_dispositions": [
                {
                    "repository": "thebrazenbeard/rezon",
                    "disposition": "REUSE",
                    "evidence": "Reuse Rezon.",
                }
            ],
        }
        with self.assertRaisesRegex(PortfolioAwarenessError, "thebrazenbeard/bt2"):
            require_capability_dispositions(data, proposal)

    def test_reject_or_supersede_requires_nonempty_evidence(self) -> None:
        proposal = {
            "schema": "VERA_OS_CAPABILITY_ASSIGNMENT_PROPOSAL_V1",
            "proposal_id": "unsupported-rejection",
            "capability": "reasoning_architecture",
            "proposed_owner": "thebrazenbeard/vera-os",
            "existing_owner_dispositions": [
                {
                    "repository": "thebrazenbeard/rezon",
                    "disposition": "REJECT",
                    "evidence": "",
                }
            ],
        }
        with self.assertRaisesRegex(PortfolioAwarenessError, "evidence"):
            require_capability_dispositions(self.capability_map, proposal)


if __name__ == "__main__":
    unittest.main()
