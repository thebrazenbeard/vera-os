"""Offline portfolio volume tests, including a real ext4 readback on Linux."""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("offline_volume", HERE / "Build-VeraOSOfflineVault.py")
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)


class VaultVolumeTests(unittest.TestCase):
    def test_geometry_rounds_up_without_truncating(self):
        one = v.geometry(601_795_187)
        self.assertEqual(one % v.SEGMENT, 0)
        self.assertGreater(one, 601_795_187)
        self.assertGreaterEqual(one, 256 * v.MIB)

    def test_geometry_rejects_negative_bool_or_empty(self):
        for n in (0, -1, True, False):
            with self.subTest(n=n), self.assertRaises(v.VolumeError):
                v.geometry(n)

    def test_refuse_existing_image(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            disk = root / "disk.ext4"
            disk.write_bytes(b"KEEP")
            with self.assertRaises(FileExistsError):
                v.package(root, root / "dummy.json", disk)
            self.assertEqual(disk.read_bytes(), b"KEEP")

    def test_invalid_output_extension(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            with self.assertRaises(v.VolumeError):
                v.package(root, root / "dummy.json", root / "image.vdi")

    def test_forbid_unsafe_virtual_path(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            with self.assertRaisesRegex(v.VolumeError, "Unsafe"):
                v._verified_image_bundle(root / "dummy.ext4", "/../secret", "0"*64, root / "dump")

    @unittest.skipUnless(shutil.which("mkfs.ext4") and shutil.which("debugfs"),
                         "Requires native Linux ext4 filesystem tools")
    def test_real_ext4_volume_contains_exact_bundle_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            folder = root / "src"
            (folder / "bundles").mkdir(parents=True)
            body = b"OFFLINE-PORTFOLIO-TEST" * 300
            (folder / "bundles" / "test-0123456789ab.bundle").write_bytes(body)
            image = root / "test.ext4"
            with image.open("wb") as stream:
                stream.truncate(32 * v.MIB)
            v._execute("mkfs.ext4", "-F", "-q", "-d", str(folder), str(image))
            extracted = root / "got.bundle"
            self.assertTrue(
                v._verified_image_bundle(image, "/bundles/test-0123456789ab.bundle",
                                         hashlib.sha256(body).hexdigest(), extracted)
            )
            self.assertEqual(extracted.read_bytes(), body)


if __name__ == "__main__":
    unittest.main()
