from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from veraos.capability_search import CapabilitySearch


class CapabilitySearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.search = CapabilitySearch(
            repository_catalog=(
                ROOT
                / "architecture"
                / "capabilities"
                / "VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json"
            ),
            plugin_catalog=(
                ROOT
                / "architecture"
                / "capabilities"
                / "CHATGPT_PLUGIN_CAPABILITY_INVENTORY_V1.json"
            ),
        )

    def test_reasoning_search_surfaces_rezon(self) -> None:
        hits = self.search.search("reasoning architecture", limit=12)
        self.assertTrue(
            any(
                hit.source_kind == "REPOSITORY"
                and hit.identifier == "thebrazenbeard/rezon"
                for hit in hits
            )
        )

    def test_browser_search_surfaces_plugin_or_tool_capability(self) -> None:
        hits = self.search.search("browser automation", limit=20)
        self.assertTrue(any(hit.source_kind in {"PLUGIN_SKILL", "TOOL_NAMESPACE"} for hit in hits))
        self.assertTrue(any("browser" in hit.evidence.casefold() for hit in hits))

    def test_repo_specific_plugin_skill_is_cross_linked(self) -> None:
        hits = self.search.search("rezon", limit=20)
        kinds = {(hit.source_kind, hit.identifier) for hit in hits}
        self.assertIn(("REPOSITORY", "thebrazenbeard/rezon"), kinds)
        self.assertIn(("PLUGIN_SKILL", "repo-rezon/repo-rezon"), kinds)

    def test_private_repo_names_are_available_only_from_private_catalog(self) -> None:
        private_repo = next(
            record["repository"]
            for record in self.search.repository_payload["repositories"]
            if record["private"]
        )
        hits = self.search.search(private_repo.split("/", 1)[1], limit=50)
        self.assertTrue(
            any(
                hit.source_kind == "REPOSITORY"
                and hit.identifier == private_repo
                for hit in hits
            )
        )


if __name__ == "__main__":
    unittest.main()
