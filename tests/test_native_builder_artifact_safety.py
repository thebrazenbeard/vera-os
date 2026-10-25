"""Offline/native source tests for anti-clobber VeraOS Buildroot artifacts.

Creates a disposable Git repository, never downloads Buildroot, compiles,
runs Docker, boots a guest, or modifies physical disks.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools/vm/Build-VeraOSNative.sh"


class NativeBuilderArtifactSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="veraos-native-clobber-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.repo = self.work / "repo"
        self.repo.mkdir()
        marker = self.repo / "buildroot/external.desc"
        marker.parent.mkdir()
        marker.write_text("name: VERAOS\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "buildroot/external.desc"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.invalid", "commit", "-q",
                        "-m", "fixture"], check=True)
        self.artifacts = self.work / "artifacts"
        self.artifacts.mkdir()

    def run_builder(self, profile="CORE_BOOT", artifact_path=None):
        return subprocess.run(
            ["bash", str(SCRIPT), str(self.repo),
             str(artifact_path or self.artifacts), profile, "1"],
            capture_output=True, text=True, timeout=8
        )

    def test_preexisting_artifacts_refused_before_network_or_build(self):
        for filename in ("veraos-bzImage", "veraos-rootfs.ext2",
                         "veraos-build-result.json"):
            with self.subTest(filename=filename):
                item = self.artifacts / filename
                item.write_bytes(b"historical-qualified-receipt")
                result = self.run_builder()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Refusing to overwrite existing VeraOS build artifact: " + filename,
                              result.stderr)
                self.assertEqual(item.read_bytes(), b"historical-qualified-receipt")
                self.assertFalse((self.artifacts / "work").exists())
                item.unlink()

    def test_symlinked_artifact_path_refused_without_touching_target(self):
        target = self.work / "keep"
        target.write_bytes(b"DO NOT TOUCH")
        alias = self.artifacts / "veraos-bzImage"
        alias.symlink_to(target)
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to overwrite existing VeraOS build artifact", result.stderr)
        self.assertEqual(target.read_bytes(), b"DO NOT TOUCH")

    def test_legacy_buildroot_profile_not_promoted_to_resident(self):
        result = self.run_builder("RESIDENT_BROWSER")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown profile", result.stderr)
        self.assertNotIn("Refusing to overwrite", result.stderr)

    def test_isolated_git_worktree_is_a_valid_source_checkout(self):
        linked = self.work / "linked"
        subprocess.run(["git", "-C", str(self.repo), "worktree", "add", "--detach",
                        str(linked)], check=True, capture_output=True, text=True)
        item = self.artifacts / "veraos-rootfs.ext2"
        item.write_bytes(b"historical-artifact")
        result = subprocess.run(
            ["bash", str(SCRIPT), str(linked), str(self.artifacts), "CORE_BOOT", "1"],
            capture_output=True, text=True, timeout=8,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to overwrite existing VeraOS build artifact", result.stderr)
        self.assertNotIn("Invalid VeraOS checkout", result.stderr)

    def test_source_uses_exclusive_creation_for_image_and_receipt(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('Path(target).open("xb")', source)
        self.assertIn("(root/'veraos-build-result.json').open('x'", source)
        self.assertIn("2024.02.4", source)
        self.assertIn("e0a2687421a4f93e65aa00a30bcb0b4817f7a195", source)


if __name__ == "__main__":
    unittest.main()
