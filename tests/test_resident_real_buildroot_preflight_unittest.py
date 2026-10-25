"""Optional pinned upstream Buildroot source / negative profile checks.

Offline source-only, no make/Kconfig resolution, compilation or QEMU.
Supply VERAOS_BUILDROOT_CHECKOUT pointing to tag 2025.02.18 detached source.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "bound_real_buildroot", ROOT / "tools/vm/Probe-ResidentBuildroot.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@unittest.skipUnless(os.environ.get("VERAOS_BUILDROOT_CHECKOUT"),
                     "exact upstream Buildroot checkout unavailable")
class UpstreamBuildrootPreflightTests(unittest.TestCase):
    def setUp(self):
        self.upstream = Path(os.environ["VERAOS_BUILDROOT_CHECKOUT"])
        tmp = tempfile.TemporaryDirectory(prefix="veraos-source-profile-")
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        source_profile = ROOT / "buildroot/configs/veraos_x86_64_resident_browser_defconfig"
        profile = self.repo / "buildroot/configs"
        profile.mkdir(parents=True)
        shutil.copyfile(source_profile, profile / source_profile.name)
        source_contract = ROOT / "architecture/os/VERA_OS_RESIDENT_BUILDROOT_CANDIDATE_V1.json"
        contract = self.repo / "architecture/os"
        contract.mkdir(parents=True)
        shutil.copyfile(source_contract, contract / source_contract.name)
        self.profile = profile / source_profile.name

    def test_real_buildroot_source_reports_not_ready_without_resolved_kconfig(self):
        result = probe.probe(self.upstream, self.repo)
        self.assertEqual(result["pinned_commit"],
                         "d030e36bbc9669230c015be971b14b6e062cfdde")
        self.assertEqual(result["expected_python"], "3.12.14")
        self.assertEqual(result["build_readiness"], "NOT_READY_KCONFIG_UNRESOLVED")
        self.assertIs(result["ready_for_authorized_build"], False)
        self.assertIs(result["image_built"], False)
        self.assertIs(result["resident_runtime_qualified"], False)

    def test_missing_browser_font_and_python_flags_refused(self):
        original = self.profile.read_text()
        for flag in ("BR2_PACKAGE_COG", "BR2_PACKAGE_COG_PLATFORM_DRM",
                     "BR2_PACKAGE_DEJAVU", "BR2_PACKAGE_DEJAVU_SANS",
                     "BR2_PACKAGE_PYTHON3_SQLITE", "BR2_PACKAGE_PYTHON3_SSL"):
            with self.subTest(flag=flag):
                self.profile.write_text(original.replace(flag + "=y\n", ""))
                with self.assertRaisesRegex(ValueError, flag):
                    probe.probe(self.upstream, self.repo)
        self.profile.write_text(original)

    def test_unpinned_buildroot_identity_fails(self):
        path = self.repo / "architecture/os/VERA_OS_RESIDENT_BUILDROOT_CANDIDATE_V1.json"
        value = json.loads(path.read_text())
        value["candidate"]["peeled_git_commit"] = "0"*40
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "pinned peeled"):
            probe.probe(self.upstream, self.repo)


if __name__ == "__main__":
    unittest.main()
