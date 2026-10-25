"""Physical native Linux synthetic ext2 regression; not a final Buildroot image."""
import importlib.util
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("veraos_pinned_ext2", ROOT / "tools/vm/Verify-VeraOSPinnedExt2.py")
pinned = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pinned)

@unittest.skipUnless(os.name == "posix" and shutil.which("mke2fs") and shutil.which("debugfs"),
                     "requires native Linux mke2fs and debugfs")
class PinnedImageCustody(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="integration-ext2-custody-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def image(self, label: str, content: bytes) -> Path:
        stage = self.root / ("stage-" + label)
        member = stage / "opt/veraos/components/vera_mono/provenance.py"
        member.parent.mkdir(parents=True)
        member.write_bytes(content)
        image = self.root / (label + ".ext2")
        subprocess.run(["mke2fs", "-q", "-F", "-t", "ext2", "-d", str(stage),
                        str(image), "8M"], check=True, capture_output=True)
        return image

    def read_member(self, image: Path) -> bytes:
        result = subprocess.run(["debugfs", "-R", "cat /opt/veraos/components/vera_mono/provenance.py",
                                 str(image)], capture_output=True, check=True)
        return result.stdout

    def test_snapshot_matches_selected_ext2_and_exact_member(self):
        original = b"selected resident A\n"
        image = self.image("A", original)
        digest = pinned._sha256(image)
        with pinned.pinned_ext2_snapshot(image, digest) as (snap, binding):
            self.assertEqual(self.read_member(snap), original)
            self.assertEqual(binding["image_sha256"], digest)
            self.assertEqual(pinned._sha256(snap), digest)

    def test_atomic_path_replacement_detected_even_when_snapshot_remains_correct(self):
        image = self.image("A", b"selected resident A\n")
        replacement = self.image("B", b"unselected resident B\n")
        digest = pinned._sha256(image)
        with self.assertRaisesRegex(pinned.ArtifactCustodyError, "alias or snapshot"):
            with pinned.pinned_ext2_snapshot(image, digest) as (snap, _):
                os.replace(replacement, image)
                self.assertEqual(self.read_member(snap), b"selected resident A\n")
                self.assertEqual(self.read_member(image), b"unselected resident B\n")
                self.assertNotEqual(pinned._sha256(image), digest)

    def test_in_place_change_detected_after_member_audit(self):
        image = self.image("A", b"selected resident A\n")
        digest = pinned._sha256(image)
        with self.assertRaisesRegex(pinned.ArtifactCustodyError, "alias or snapshot"):
            with pinned.pinned_ext2_snapshot(image, digest) as (snap, _):
                self.assertEqual(self.read_member(snap), b"selected resident A\n")
                with image.open("r+b") as writer:
                    writer.seek(4096)
                    writer.write(b"C")
                    writer.flush()
                    os.fsync(writer.fileno())

    def test_wrong_expected_digest_is_held(self):
        image = self.image("A", b"selected resident A\n")
        with self.assertRaisesRegex(pinned.ArtifactCustodyError, "digest mismatch"):
            with pinned.pinned_ext2_snapshot(image, "0" * 64):
                self.fail("wrong digest was accepted")

if __name__ == "__main__":
    unittest.main()
