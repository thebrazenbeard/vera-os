"""Source-only rooted runtime graph: guards against accidental sibling admission."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BOM = ROOT / "architecture/os/VERA_OS_MINIMAL_CANONICAL_COMPOSITION_V1.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def component_names():
    module = ast.parse((ROOT / "src/veraos/resident.py").read_text())
    return tuple(next(ast.literal_eval(n.value) for n in module.body
                      if isinstance(n, ast.Assign) and
                      any(isinstance(t, ast.Name) and t.id == "COMPONENT_NAMES"
                          for t in n.targets)))


class MinimalCompositionContract(unittest.TestCase):
    def setUp(self):
        self.graph = read(BOM)

    def test_four_source_roots_match_actual_resident_and_source_receipt(self):
        rows = self.graph["selected_source_components"]
        self.assertEqual([r["component"] for r in rows],
                         ["vera_mono", "portal", "pre_active", "volition"])
        self.assertEqual(component_names(),
                         ("vera_core", "portal", "pre_active", "volition"))
        self.assertEqual(sum(row["file_count"] for row in rows), 431)
        self.assertEqual(len(set(row["repository"] for row in rows)), 4)
        self.assertEqual(self.graph["source_receipt_sha256"],
                         "6f0031c1fcbaed41e4e3f6947e90a92ed5656ac3e09329de7d8e0b0f8417eca5")

    def test_mono_self_contained_without_live_sibling_dependency(self):
        package_ids = self.graph["selected_source_components"][0]["internal_package_ids"]
        self.assertEqual(len(package_ids), 12)
        self.assertEqual(len(set(package_ids)), len(package_ids))
        for name in ("vera_core", "vera_memory", "vera_assurance",
                     "vera_recovery", "rezon", "portfolio_runtime"):
            self.assertIn(name, package_ids)
        selected = {x["repository"] for x in self.graph["selected_source_components"]}
        excluded = set(self.graph["excluded_as_mandatory_guest_runtime"])
        self.assertFalse(selected.intersection(excluded))
        self.assertIn("thebrazenbeard/rezon", excluded)
        self.assertIn("rezon", package_ids)
        self.assertFalse(self.graph["identity"]["shared_state_root"])
        self.assertFalse(self.graph["identity"]["shared_physical_writer"])
        self.assertFalse(self.graph["identity"]["locator_authenticates_user"])

    def test_host_root_and_pid1_are_explicit_source_contracts(self):
        graph = self.graph
        self.assertEqual(graph["normal_init"]["entrypoint"], "/sbin/vera-init")
        self.assertEqual(graph["normal_init"]["resident_module"], "veraos.resident")
        self.assertEqual(graph["normal_init"]["browser_command"], [
            "/usr/bin/cog", "--platform=drm", "http://127.0.0.1:18765/"])
        self.assertEqual(graph["identity"]["linux"]["project_id"], "veraos")
        self.assertEqual(graph["identity"]["windows"]["project_id"], "VERA_MONO")
        self.assertNotEqual(graph["identity"]["linux"]["canonical_state"],
                            graph["identity"]["windows"]["canonical_state"])
        resident = (ROOT / "src/veraos/resident.py").read_text()
        pid1 = (ROOT / "src/veraos/pid1.py").read_text()
        self.assertIn('state_root / "vera-state", project_id="veraos", identity_id="VERA"', resident)
        self.assertIn('["/usr/bin/cog", "--platform=drm", "http://127.0.0.1:18765/"]', pid1)

    def test_original_boot_contract_version_is_not_current_candidate(self):
        source = read(ROOT / "architecture/os/VERA_OS_RESIDENT_BUILDROOT_CANDIDATE_V1.json")
        historical = read(ROOT / "architecture/os/VERA_OS_BOOT_CONTRACT_V1.json")
        newer = self.graph["buildroot"]
        self.assertEqual(newer["source_version"], source["candidate"]["version"])
        self.assertEqual(newer["peeled_source_commit"],
                         source["candidate"]["peeled_git_commit"])
        self.assertEqual(newer["selected_defconfig"],
                         source["candidate"]["source_defconfig"])
        self.assertEqual(newer["source_historical_boot_contract_buildroot"],
                         historical["product"]["image_builder_version"])
        self.assertNotEqual(newer["source_version"],
                            historical["product"]["image_builder_version"])
        self.assertFalse(newer["resolved_kconfig"])
        self.assertFalse(newer["build_executed"])
        self.assertFalse(newer["image_accepted"])
        self.assertFalse(newer["target_imports_executed"])

    def test_staged_sources_are_not_proof_of_minimal_boot_requirements(self):
        graph = self.graph
        self.assertEqual(graph["current_resident_required_source_components"],
                         ["vera_mono", "portal", "pre_active", "volition"])
        candidate = graph["minimal_no_provider_boot_without_preactive_and_volition"]
        self.assertEqual(candidate["status"], "NOT_IMPLEMENTED_NOT_QUALIFIED")
        self.assertFalse(graph["buildroot"]["build_executed"])

    def test_no_false_build_guest_provider_or_effect_claim(self):
        q = self.graph["qualification"]
        self.assertEqual(q["resolved_buildroot_kconfig"], "UNEXECUTED")
        self.assertEqual(q["built_rootfs_and_image"], "NOT_BUILT")
        self.assertEqual(q["pid1_cog_graphical_two_boot"], "NOT_GUEST_QUALIFIED")
        self.assertEqual(q["provider_model"], "HOLD")
        self.assertEqual(q["protected_effects"], "DENIED")
        self.assertFalse(self.graph["normal_init"]["guest_graphics_verified"])


if __name__ == "__main__":
    unittest.main()
