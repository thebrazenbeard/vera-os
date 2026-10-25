"""Six live repo descriptions are source awareness, not guest admission."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "architecture/capabilities"
FILE = CAP / "VERA_OS_DISCOVERY_GAP_AWARENESS_V1.json"


class GapAwarenessTests(unittest.TestCase):
    def test_six_exact_main_heads_without_mutating_historical_ninety(self):
        gaps = json.loads(FILE.read_text(encoding="utf-8"))
        legacy = json.loads((CAP / "VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json").read_text(encoding="utf-8-sig"))
        expected = {"human-shield", "physica", "redworm", "v-e-r-a", "vera-model", "vision"}
        rows = gaps["entries"]
        observed = {x["repository"].split("/", 1)[1] for x in rows}
        self.assertEqual(observed, expected)
        self.assertEqual(len(rows), gaps["gap_count"])
        self.assertEqual(gaps["scope"], "SOURCE_AWARENESS_ONLY")
        self.assertIs(gaps["authority"], False)
        self.assertTrue(gaps["requires_explicit_later_decision"])
        self.assertTrue(all(len(x["exact_main_head"]) == 40 and x["role"] for x in rows))
        self.assertEqual(len(legacy["repositories"]), 90)
        self.assertFalse(set(x["repository"] for x in rows) & set(
            x["repository"] for x in legacy["repositories"]))

    def test_six_source_repos_are_not_opt_in_guest_boot_or_image_inputs(self):
        gaps = json.loads(FILE.read_text(encoding="utf-8"))
        candidate = json.loads((ROOT / "architecture/os/VERA_OS_RESIDENT_BUILDROOT_CANDIDATE_V1.json").read_text())
        stage = json.loads((ROOT / "architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json").read_text())
        self.assertEqual(len(candidate["requires"]["target_core_code"]), 4)
        for x in gaps["entries"]:
            self.assertNotIn(x["repository"], candidate["requires"]["target_core_code"])
        # No claim that the historical 90-repository catalog is 96 or that
        # awareness has become an installed/selected resident source.
        self.assertEqual(len(stage["repositories"]), 90)


if __name__ == "__main__":
    unittest.main()
