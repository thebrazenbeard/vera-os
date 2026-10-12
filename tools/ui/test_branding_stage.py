"""Test local-only VeraOS branded desktop assets without private user images."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("veraos_branding", HERE / "Stage-VeraOSBranding.py")
stager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stager)

try:
    from PIL import Image
except ImportError:
    Image = None


@unittest.skipIf(Image is None, "Pillow is needed only for generating local image fixtures")
class BrandingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sources = self.root / "originals"
        self.sources.mkdir()
        self.stage = self.root / "staged"
        Image.new("RGBA", (1920, 1080), (85, 12, 35, 240)).save(
            self.sources / stager.WALLPAPER_SOURCE
        )
        Image.new("RGBA", (255, 256), (190, 55, 80, 200)).save(
            self.sources / stager.ICON_SOURCE
        )
        Image.new("RGB", (1086, 1448), (72, 60, 66)).save(
            self.sources / stager.AVATAR_SOURCE
        )
        self.sources_before = {
            p.name: stager.sha256_file(p) for p in self.sources.iterdir()
        }

    def test_wallpaper_icons_receipts_and_preservation(self):
        report = stager.create(self.sources, self.stage)
        self.assertEqual(report["asset_count"], 5)
        self.assertFalse(report["avatar_included"])
        self.assertFalse(report["guest_installed"])
        self.assertFalse(report["desktop_render_qualified"])
        self.assertEqual(report["status"], "LOCAL_BRANDING_FILES_HASH_VERIFIED_NOT_RENDERED")
        with Image.open(self.stage / stager.TARGET_WALLPAPER) as wall:
            self.assertEqual(wall.size, (1920, 1080))
        for size in stager.ICON_SIZES:
            with Image.open(self.stage / f"launcher-{size}.png") as icon:
                self.assertEqual(icon.size, (size, size))
        self.assertEqual(
            self.sources_before,
            {p.name: stager.sha256_file(p) for p in self.sources.iterdir()},
        )
        self.assertEqual(
            stager.verify_stage(self.stage)["receipt_sha256"],
            report["receipt_sha256"]
        )

    def test_optional_portrait_not_copied_by_default(self):
        stager.create(self.sources, self.stage)
        self.assertFalse((self.stage / "avatar-512.png").exists())

    def test_optional_portrait_is_explicit(self):
        report = stager.create(self.sources, self.stage, include_avatar=True)
        self.assertEqual(report["asset_count"], 6)
        self.assertTrue(report["avatar_included"])
        self.assertTrue((self.stage / "avatar-512.png").is_file())

    def test_existing_output_not_overwritten(self):
        self.stage.mkdir()
        sentinel = self.stage / "keep.txt"
        sentinel.write_text("DO NOT ERASE")
        with self.assertRaises(FileExistsError):
            stager.create(self.sources, self.stage)
        self.assertEqual(sentinel.read_text(), "DO NOT ERASE")

    def test_changed_bytes_same_length_hold(self):
        stager.create(self.sources, self.stage)
        path = self.stage / "launcher-64.png"
        with path.open("r+b") as stream:
            stream.seek(-1, 2)
            stream.write(b"X")
        with self.assertRaisesRegex(stager.BrandingError, "changed"):
            stager.verify_stage(self.stage)

    def test_missing_asset_holds(self):
        stager.create(self.sources, self.stage)
        (self.stage / "launcher-32.png").unlink()
        with self.assertRaisesRegex(stager.BrandingError, "Unexpected file"):
            stager.verify_stage(self.stage)

    def test_extra_asset_holds(self):
        stager.create(self.sources, self.stage)
        (self.stage / "unexpected.exe").write_bytes(b"bad")
        with self.assertRaisesRegex(stager.BrandingError, "Unexpected"):
            stager.verify_stage(self.stage)

    def test_bogus_install_claim_holds(self):
        stager.create(self.sources, self.stage)
        manifest = self.stage / "branding-receipt.json"
        data = json.loads(manifest.read_text())
        data["installed"] = True
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(stager.BrandingError, "cannot claim"):
            stager.verify_stage(self.stage)

    def test_missing_originals_rejected_before_creating_output(self):
        (self.sources / stager.ICON_SOURCE).unlink()
        with self.assertRaisesRegex(stager.BrandingError, "missing"):
            stager.create(self.sources, self.stage)
        self.assertFalse(self.stage.exists())


if __name__ == "__main__":
    unittest.main()
