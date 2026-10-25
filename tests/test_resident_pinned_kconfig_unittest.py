"""Fail-closed tests for source-only effective Buildroot Kconfig receipts."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("veraos_kconfig", HERE / "tools/vm/Probe-ResidentKconfig.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

class PinnedKconfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="vn2-kconfig-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.external = self.root / "external"
        self.external.mkdir()
        files = {
            "external.desc": b"name: VERAOS\n",
            "Config.in": b"menu \"VeraOS\"\nendmenu\n",
            "configs/resident_defconfig": (
                b"BR2_x86_64=y\nBR2_PACKAGE_PYTHON3=y\nBR2_PACKAGE_COG=y\n"
                b"BR2_GLOBAL_PATCH_DIR=\"$(BR2_EXTERNAL_VERAOS_PATH)/patches\"\n"
                b"BR2_ROOTFS_OVERLAY=\"$(BR2_EXTERNAL_VERAOS_PATH)/overlay\"\n"
                b"BR2_ROOTFS_POST_BUILD_SCRIPT=\"$(BR2_EXTERNAL_VERAOS_PATH)/post-build.sh\"\n"),
            "post-build.sh": b"#!/bin/sh\nexit 0\n",
            "overlay/sbin/vera-init": b"#!/bin/sh\nexit 0\n",
            "patches/cog/0001.patch": b"example\n",
        }
        for name, content in files.items():
            p = self.external / name
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(content)
        (self.external/"post-build.sh").chmod(0o755)
        self.archive = self.root / "buildroot.tgz"
        self.archive.write_bytes(b"synthetic archive identifier - not Buildroot")
        self.config = self.root / "output/.config"
        self.config.parent.mkdir()
        self.config.write_bytes(files["configs/resident_defconfig"])
        self.manifest = self.root / "pins.json"
        self.pins = {
            "schema":"VERAOS_BUILDROOT_KCONFIG_PINNED_INPUTS_V1",
            "veraos_reviewed_source_head":"test-fixture",
            "buildroot_source_commit":"fixture-source-commit",
            "upstream_archive_sha256":sha(self.archive.read_bytes()),
            "defconfig":"configs/resident_defconfig",
            "external_git_blob_sha1":{name:git_blob(content) for name,content in files.items()},
            "required_effective_symbols":["BR2_x86_64","BR2_PACKAGE_PYTHON3","BR2_PACKAGE_COG"],
            "external_paths":{"BR2_GLOBAL_PATCH_DIR":"dir","BR2_ROOTFS_OVERLAY":"dir",
                              "BR2_ROOTFS_POST_BUILD_SCRIPT":"executable"},
        }
        self.save()

    def save(self):
        self.manifest.write_text(json.dumps(self.pins,sort_keys=True),encoding="utf-8")

    def audit(self):
        return mod.audit(self.manifest,self.external,self.config,self.archive)

    def test_valid_resolved_source_receipt_is_explicitly_not_image_qualification(self):
        r = self.audit()
        self.assertEqual(r["status"],"PINNED_KCONFIG_RESOLVED_SOURCE_ONLY")
        self.assertEqual(r["requested_symbols_retained"], 6)
        self.assertFalse(r["image_built"])
        self.assertFalse(r["target_python_import_executed"])
        self.assertFalse(r["protected_effect_authority"])

    def test_resolved_gui_symbol_dropped_fails_closed(self):
        self.config.write_text(self.config.read_text().replace("BR2_PACKAGE_COG=y","BR2_PACKAGE_COG=n"))
        with self.assertRaisesRegex(mod.KconfigHold, "BR2_PACKAGE_COG"):
            self.audit()

    def test_duplicate_or_conflicting_config_symbol_fails(self):
        with self.config.open("a") as f: f.write("\nBR2_PACKAGE_COG=y\n")
        with self.assertRaisesRegex(mod.KconfigHold, "duplicate"):
            self.audit()

    def test_checkout_line_ending_mutation_is_not_equivalent_git_byte_identity(self):
        p=self.external/"Config.in"
        p.write_bytes(p.read_bytes().replace(b"\n",b"\r\n"))
        with self.assertRaisesRegex(mod.KconfigHold, "Git blob mismatch"):
            self.audit()

    def test_missing_postbuild_or_patched_source_holds(self):
        (self.external/"post-build.sh").unlink()
        with self.assertRaises(mod.KconfigHold):
            self.audit()

    def test_missing_external_overlay_directory_holds(self):
        (self.external/"overlay/sbin/vera-init").unlink()
        with self.assertRaisesRegex(mod.KconfigHold, "external Git source"):
            self.audit()

    def test_wrong_upstream_source_archive_holds(self):
        self.archive.write_bytes(b"changed upstream source")
        with self.assertRaisesRegex(mod.KconfigHold, "Buildroot archive"):
            self.audit()

    def test_external_path_escaping_root_holds(self):
        s=self.config.read_text()
        self.config.write_text(s.replace("$(BR2_EXTERNAL_VERAOS_PATH)/patches","$(BR2_EXTERNAL_VERAOS_PATH)/../escape"))
        with self.assertRaises(mod.KconfigHold):
            self.audit()

    def test_missing_selection_boolean_rejected(self):
        self.config.write_text(self.config.read_text().replace("BR2_PACKAGE_COG=y","# BR2_PACKAGE_COG is not set"))
        with self.assertRaisesRegex(mod.KconfigHold,"BR2_PACKAGE_COG"):
            self.audit()

    def test_real_vn2_effective_kconfig_if_explicitly_bound(self):
        workspace=os.environ.get("VERAOS_VN2_PINNED_KCONFIG_WORKSPACE")
        if not workspace:
            self.skipTest("no expressly pinned VN2 Kconfig workspace")
        root=Path(workspace)
        actual=mod.audit(
            HERE/"architecture/os/VERAOS_PINNED_BUILDROOT_KCONFIG_V1.json",
            root/"veraos-external",root/"output/.config",root/"buildroot.tgz")
        self.assertEqual(actual["status"],"PINNED_KCONFIG_RESOLVED_SOURCE_ONLY")
        self.assertEqual(actual["requested_symbols_retained"],51)
        self.assertFalse(actual["image_built"])

    def _select_v2(self):
        self.pins["schema"] = "VERAOS_BUILDROOT_KCONFIG_PINNED_INPUTS_V2"
        self.pins["veraos_reviewed_source_head"] = "10dfe758479573468b091cd260c57e8d65cc6942"
        self.pins["buildroot_source_commit"] = "d030e36bbc9669230c015be971b14b6e062cfdde"
        self.save()

    def test_v2_accepts_exact_reviewed_source_pin_without_claiming_image(self):
        self._select_v2()
        result = self.audit()
        self.assertEqual(result["source_head"], "10dfe758479573468b091cd260c57e8d65cc6942")
        self.assertFalse(result["image_built"])
        self.assertFalse(result["protected_effect_authority"])

    def test_v2_rejects_placeholder_or_future_reviewed_head(self):
        self._select_v2()
        for bad_head in ("test-fixture", "f" * 40):
            self.pins["veraos_reviewed_source_head"] = bad_head
            self.save()
            with self.assertRaisesRegex(mod.KconfigHold, "reviewed source"):
                self.audit()

    def test_v2_rejects_wrong_upstream_commit(self):
        self._select_v2()
        self.pins["buildroot_source_commit"] = "f" * 40
        self.save()
        with self.assertRaisesRegex(mod.KconfigHold, "Buildroot source"):
            self.audit()

    def test_v2_rejects_postbuild_drift(self):
        self._select_v2()
        (self.external/"post-build.sh").write_bytes(b"#!/bin/sh\nexit 42\n")
        with self.assertRaisesRegex(mod.KconfigHold, "Git blob mismatch"):
            self.audit()

    def test_v2_candidate_matches_reviewed_exact_git_tree(self):
        pins = json.loads((HERE/"architecture/os/VERAOS_PINNED_BUILDROOT_KCONFIG_V2.json").read_text())
        self.assertEqual(pins["schema"], "VERAOS_BUILDROOT_KCONFIG_PINNED_INPUTS_V2")
        self.assertEqual(pins["veraos_reviewed_source_head"],
                         "10dfe758479573468b091cd260c57e8d65cc6942")
        self.assertEqual(pins["buildroot_source_commit"],
                         "d030e36bbc9669230c015be971b14b6e062cfdde")
        self.assertEqual(len(pins["external_git_blob_sha1"]), 10)
        # GitHub exact-head blob on 2026-10-25; historical V1 has 52c7de61...
        self.assertEqual(pins["external_git_blob_sha1"]["board/veraos/x86_64/post-build.sh"],
                         "836e94cc2eebd96a31a85c533dcc12240bbe1823")

if __name__ == "__main__":
    unittest.main()
