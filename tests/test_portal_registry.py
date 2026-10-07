from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from veraos.portal_registry import (
    build_portal_project_registry,
    write_portal_project_registry,
)


CAPABILITY_MAP = (
    ROOT
    / "architecture"
    / "capabilities"
    / "VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json"
)


class PortalRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capability_map = json.loads(CAPABILITY_MAP.read_text(encoding="utf-8"))

    def test_registry_represents_all_private_catalog_repositories_once(self) -> None:
        registry = build_portal_project_registry(self.capability_map)
        projects = registry["projects"]

        self.assertEqual(86, len(projects))
        self.assertEqual(86, len({project["id"] for project in projects}))
        self.assertEqual(
            {
                row["repository"]
                for row in self.capability_map["repositories"]
            },
            {
                project["repositories"][0]
                for project in projects
            },
        )

    def test_awareness_bridge_does_not_activate_projects_or_authority(self) -> None:
        registry = build_portal_project_registry(self.capability_map)
        by_repo = {
            project["repositories"][0]: project
            for project in registry["projects"]
        }

        for row in self.capability_map["repositories"]:
            project = by_repo[row["repository"]]
            expected_state = "ARCHIVED" if row["archived"] else "HELD"
            self.assertEqual(expected_state, project["scheduling_state"])
            self.assertEqual("NONE", project["assignment_scope"])
            self.assertEqual("NONE", project["review_scope"])
            self.assertEqual(
                "private" if row["private"] else "public",
                project["visibility"],
            )
            self.assertEqual(
                sorted(set(row["capabilities"])),
                project["capabilities"],
            )
            self.assertIn(
                "effect authority require separate live evidence",
                project["scope_note"],
            )

    def test_project_ids_are_portal_safe_and_case_normalized(self) -> None:
        registry = build_portal_project_registry(self.capability_map)
        by_repo = {
            project["repositories"][0]: project
            for project in registry["projects"]
        }
        self.assertEqual("attune", by_repo["thebrazenbeard/Attune"]["id"])
        self.assertEqual(
            "workbridgemcp",
            by_repo["thebrazenbeard/WorkBridgeMCP"]["id"],
        )
        self.assertEqual(
            "repairtracker",
            by_repo["thebrazenbeard/RepairTracker"]["id"],
        )

    def test_written_registry_is_deterministic_and_digest_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "projects.private.json"
            digest = write_portal_project_registry(path, self.capability_map)
            raw = path.read_bytes()
            payload = json.loads(raw)

        self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
        self.assertEqual(
            build_portal_project_registry(self.capability_map),
            payload,
        )


if __name__ == "__main__":
    unittest.main()
