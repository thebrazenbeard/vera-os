"""Verify private VeraOS branding is opt-in and copied only after hash verification."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
POST_BUILD = ROOT / "buildroot/board/veraos/x86_64/post-build.sh"
WRAPPER = ROOT / "tools/vm/Build-VeraOSVm.ps1"

try:
    from PIL import Image
except ImportError:
    Image = None

import importlib.util
spec = importlib.util.spec_from_file_location("branding_under_test", HERE / "Stage-VeraOSBranding.py")
branding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(branding)


class BrandingBuildBindingTests(unittest.TestCase):
    def test_wrapper_is_opt_in_and_guest_render_unqualified(self):
        src = WRAPPER.read_text(encoding="utf-8")
        self.assertIn('[string]$DesktopAssetStage = ""', src)
        self.assertIn("DesktopAssetStagePackaged = [bool]$desktopAssetStageResolved", src)
        self.assertIn("DesktopAssetsRenderedQualified = $false", src)
        self.assertIn("target=/branding,readonly", src)
        self.assertIn("VERAOS_DESKTOP_STAGE=/branding", src)
        self.assertIn("private desktop asset stage must remain outside", src.lower())

    def test_post_build_verifies_before_install(self):
        src = POST_BUILD.read_text(encoding="utf-8")
        self.assertIn("VERAOS_DESKTOP_STAGE:-", src)
        self.assertLess(src.index("--verify-stage"), src.index('install -d "$target_dir/usr/share/veraos/branding"'))
        self.assertIn("VERA_OS_LOCAL_BRANDING_BUILD_RECEIPT_V1.json", src)

    @unittest.skipIf(Image is None or os.name == "nt", "Needs Linux shell and Pillow")
    def test_post_build_copies_only_verified_stage(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            originals = base / "originals"
            originals.mkdir()
            Image.new("RGB", (1920, 1080), (50, 6, 23)).save(originals / branding.WALLPAPER_SOURCE)
            Image.new("RGBA", (256, 256), (181, 67, 85, 255)).save(originals / branding.ICON_SOURCE)
            stage = base / "stage"
            branding.create(originals, stage)
            fake_root = base / "target"
            (fake_root / "sbin").mkdir(parents=True)
            (fake_root / "sbin/vera-init").write_text("#!/bin/sh\nexit 0\n")
            env = os.environ.copy()
            env.pop("VERAOS_REQUIRE_RESIDENT_CORE", None)
            env["VERAOS_DESKTOP_STAGE"] = str(stage)
            done = subprocess.run(["sh", str(POST_BUILD), str(fake_root)], env=env,
                                  capture_output=True, text=True, timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr)
            target = fake_root / "usr/share/veraos/branding"
            for asset in branding.EXPECTED:
                self.assertEqual(branding.sha256_file(stage / asset), branding.sha256_file(target / asset))
            self.assertFalse((target / "avatar-512.png").exists())
            receipt = fake_root / "etc/veraos/architecture/VERA_OS_LOCAL_BRANDING_BUILD_RECEIPT_V1.json"
            self.assertEqual(branding.sha256_file(receipt), branding.sha256_file(stage / "branding-receipt.json"))

    @unittest.skipIf(Image is None or os.name == "nt", "Needs Linux shell and Pillow")
    def test_tampered_stage_cannot_be_packaged(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            originals = base / "originals"
            originals.mkdir()
            Image.new("RGB", (1920, 1080), (50, 6, 23)).save(originals / branding.WALLPAPER_SOURCE)
            Image.new("RGBA", (256, 256), (181, 67, 85, 255)).save(originals / branding.ICON_SOURCE)
            stage = base / "stage"
            branding.create(originals, stage)
            with (stage / "launcher-64.png").open("ab") as stream:
                stream.write(b"bad")
            fake_root = base / "target"
            (fake_root / "sbin").mkdir(parents=True)
            (fake_root / "sbin/vera-init").write_text("#!/bin/sh\nexit 0\n")
            env = os.environ.copy()
            env.pop("VERAOS_REQUIRE_RESIDENT_CORE", None)
            env["VERAOS_DESKTOP_STAGE"] = str(stage)
            done = subprocess.run(["sh", str(POST_BUILD), str(fake_root)], env=env,
                                  capture_output=True, text=True, timeout=60)
            self.assertNotEqual(done.returncode, 0)
            self.assertFalse((fake_root / "usr/share/veraos/branding").exists())


if __name__ == "__main__":
    unittest.main()
