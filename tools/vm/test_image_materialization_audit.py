"""Adversarial fixtures for the static VeraOS repository materialization audit."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "veraos_image_materialization",
    Path(__file__).with_name("Audit-VeraOSImage.py"),
)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ImageMaterializationAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rootfs = self.root / "rootfs"
        self.rootfs.mkdir()
        self.requirements = AUDIT.read_json(
            ROOT / "architecture/os/VERA_OS_CORE_IMAGE_CONTENT_REQUIREMENTS_V1.json"
        )
        self.composition = AUDIT.read_json(
            ROOT / "architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json"
        )

    def add(self, virtual_path, payload=b"test module bytes"):
        path = self.rootfs / virtual_path.lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def add_image_catalogs(self):
        source_files = {
            "composition": "architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json",
            "capability_map": "architecture/capabilities/VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json",
            "implementation": "architecture/portfolio/VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json",
        }
        for key, virtual in self.requirements["embedded_catalogs"].items():
            self.add(virtual, (ROOT / source_files[key]).read_bytes())

    def add_python(self, version):
        marker = self.rootfs / self.requirements["python_runtime_marker"].lstrip("/")
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.symlink_to("python" + version)

    def add_all_core(self):
        for item in self.requirements["required_components"]:
            self.add(item["package_marker"], b"# content marker for " + item["component"].encode())
        self.add(self.requirements["native_os_marker"])
        self.add_image_catalogs()

    def add_receipt(self):
        entries = []
        catalog = {item["repository"]: item for item in self.composition["repositories"]}
        for core in self.requirements["required_components"]:
            target = self.rootfs / core["package_marker"].lstrip("/")
            entries.append({
                "repository": core["repository"],
                "source_head": catalog[core["repository"]]["exact_head"],
                "marker_path": core["package_marker"],
                "marker_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            })
        receipt = {
            "schema": "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1",
            "components": entries,
            "authority": False,
        }
        self.add(
            "/etc/veraos/architecture/VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json",
            json.dumps(receipt).encode("utf-8"),
        )
        return receipt

    def check(self):
        return AUDIT.audit(AUDIT.DirectoryRootfs(self.rootfs), ROOT)

    def test_catalog_covers_ninety_not_all_installed(self):
        self.assertEqual(len(self.composition["repositories"]), 90)
        self.assertEqual(self.composition["counts"]["integrated"], 85)
        self.assertEqual(self.composition["counts"]["excluded"], 5)
        result = self.check()
        self.assertEqual(result["status"], "HOLD_INCOMPLETE_IMAGE")
        self.assertFalse(result["catalog_is_implementation"])
        self.assertFalse(result["resident_runtime_qualified"])
        self.assertTrue(all(not x["source_file_packaged"] for x in result["core_components"]))

    def test_catalog_only_never_proves_runtime(self):
        self.add_image_catalogs()
        self.add(self.requirements["native_os_marker"])
        self.add_python("3.12")
        r = self.check()
        self.assertTrue(all(x["exact_bytes_match_source"] for x in r["embedded_catalogs"].values()))
        self.assertFalse(r["ready_for_guest_import_tests"])
        self.assertEqual(r["status"], "HOLD_INCOMPLETE_IMAGE")

    def test_python_311_blocks_newer_core(self):
        self.add_all_core()
        self.add_receipt()
        self.add_python("3.11")
        r = self.check()
        self.assertFalse(r["ready_for_guest_import_tests"])
        self.assertEqual(r["python_version"], "3.11")
        self.assertFalse(next(x for x in r["core_components"] if x["repository"].endswith("vera-mono"))["image_python_compatible"])
        self.assertTrue(next(x for x in r["core_components"] if x["repository"].endswith("volition"))["image_python_compatible"])

    def test_all_markers_without_receipt_still_hold(self):
        self.add_all_core()
        self.add_python("3.12")
        r = self.check()
        self.assertFalse(r["ready_for_guest_import_tests"])
        self.assertEqual(r["resident_receipt_state"], "ABSENT")

    def test_valid_marker_receipt_only_enables_guest_import_probe(self):
        self.add_all_core()
        self.add_python("3.12")
        self.add_receipt()
        r = self.check()
        self.assertTrue(r["ready_for_guest_import_tests"])
        self.assertEqual(r["status"], "READY_FOR_GUEST_IMPORT_PROBES_NOT_QUALIFIED")
        self.assertEqual(r["resident_receipt_state"], "MARKER_HASHES_VALID_NOT_INDEPENDENTLY_ATTESTED")
        self.assertFalse(r["resident_runtime_qualified"])
        self.assertFalse(r["p_o_r_t_a_l_route_qualified"])
        self.assertFalse(r["trained_model_consumption_qualified"])

    def test_wrong_receipt_digest_holds(self):
        self.add_all_core()
        self.add_python("3.12")
        rec = self.add_receipt()
        rec["components"][0]["marker_sha256"] = "0" * 64
        self.add(
            "/etc/veraos/architecture/VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json",
            json.dumps(rec).encode(),
        )
        r = self.check()
        self.assertEqual(r["resident_receipt_state"], "INVALID")
        self.assertFalse(r["ready_for_guest_import_tests"])

    def test_wrong_receipt_head_holds(self):
        self.add_all_core()
        self.add_python("3.12")
        rec = self.add_receipt()
        rec["components"][0]["source_head"] = "a" * 40
        self.add(
            "/etc/veraos/architecture/VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json",
            json.dumps(rec).encode(),
        )
        self.assertFalse(self.check()["ready_for_guest_import_tests"])

    def test_stale_embedded_catalog_holds(self):
        self.add_all_core()
        self.add_python("3.12")
        self.add_receipt()
        self.add(self.requirements["embedded_catalogs"]["composition"], b"{}")
        r = self.check()
        self.assertFalse(r["embedded_catalogs"]["composition"]["exact_bytes_match_source"])
        self.assertFalse(r["ready_for_guest_import_tests"])

    def test_missing_core_marker_holds(self):
        self.add_all_core()
        self.add_python("3.12")
        self.add_receipt()
        target = self.rootfs / self.requirements["required_components"][1]["package_marker"].lstrip("/")
        target.unlink()
        r = self.check()
        self.assertFalse(r["ready_for_guest_import_tests"])
        self.assertIn("MISSING_FROM_IMAGE", [x["status"] for x in r["core_components"]])

    def test_symlink_escape_does_not_count_as_packaged(self):
        self.add_all_core()
        self.add_python("3.12")
        target = self.rootfs / self.requirements["required_components"][0]["package_marker"].lstrip("/")
        original = target.read_bytes()
        target.unlink()
        foreign = self.root / "outside"
        foreign.write_bytes(original)
        target.symlink_to(foreign)
        result = self.check()
        self.assertFalse(result["core_components"][0]["source_file_packaged"])

    def test_new_repos_classified_not_autoboot(self):
        byrepo = {row["repository"]: row for row in self.composition["repositories"]}
        for name in ("vera-adapter", "blotter", "RSLinux5000000", "vera-agi"):
            row = byrepo["thebrazenbeard/" + name]
            self.assertFalse(row["runtime_authority"])
            self.assertNotEqual(row["boot_policy"], "CORE")
        self.assertEqual(byrepo["thebrazenbeard/vera-agi"]["boot_policy"], "NEVER")

    def test_only_four_core_code_requirements(self):
        self.assertEqual(
            {item["repository"] for item in self.requirements["required_components"]},
            {"thebrazenbeard/vera-mono", "thebrazenbeard/portal",
             "thebrazenbeard/pre-active", "thebrazenbeard/volition"},
        )


if __name__ == "__main__":
    unittest.main()
