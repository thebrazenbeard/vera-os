"""Source-only regression contracts for the selected VeraOS resident Docker builder.

No Docker, Buildroot, or untrusted historical editor task is executed here.
A green test proves static wiring, not a compiled or booted image.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools/vm/Build-VeraOSVm.ps1"


class ResidentBuilderWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = BUILDER.read_text(encoding="utf-8")
        first = cls.source.index("$dockerArgs = @(")
        resident = cls.source.index("if ($residentSourceStageResolved) {", first)
        cls.base_arguments = cls.source[first:resident]
        cls.resident_arguments = cls.source[resident:cls.source.index("& docker @dockerArgs", resident)]

    def test_resident_env_matches_postbuild_contract(self):
        # buildroot/board/veraos/x86_64/post-build.sh requires this exact value.
        self.assertIn('"--env", "VERAOS_REQUIRE_RESIDENT_CORE=1"', self.resident_arguments)
        self.assertIn('"--env", "VERAOS_RESIDENT_STAGE=/resident"', self.resident_arguments)
        self.assertIn('"--env", "VERAOS_RESIDENT_GUEST_PROFILE=2025.02.18"', self.resident_arguments)
        self.assertNotIn("VERAOS_RESIDENT_GUEST_PROFILE", self.base_arguments)

    def test_legacy_2024_and_resident_2025_keep_distinct_defaults(self):
        self.assertIn('"veraos-buildroot-builder:2024.02.4"', self.source)
        self.assertIn('"veraos-buildroot-builder:2025.02.18"', self.source)
        self.assertIn('"veraos-buildroot-work"', self.source)
        self.assertIn('"veraos-resident-browser-python312-20261012"', self.source)
        self.assertIn('"e0a2687421a4f93e65aa00a30bcb0b4817f7a195"', self.source)
        self.assertIn('"d030e36bbc9669230c015be971b14b6e062cfdde"', self.source)

    def test_missing_resident_source_stage_fails_before_docker(self):
        self.assertIn("RESIDENT_BROWSER requires an explicit, separately verified resident source stage", self.source)
        self.assertLess(self.source.index("requires an explicit, separately verified resident source stage"),
                        self.source.index("& docker build"))

    def test_existing_image_receipt_or_artifact_blocks_before_docker(self):
        guard = self.source.index("Refusing to overwrite existing VeraOS build artifact")
        self.assertLess(guard, self.source.index("& docker build"))
        for filename in ("veraos-bzImage", "veraos-rootfs.ext2",
                         "veraos-bzImage.sha256", "veraos-rootfs.ext2.sha256",
                         "veraos-build-result.json", "veraos-buildroot-build.sh"):
            with self.subTest(filename=filename):
                self.assertIn('"' + filename + '"', self.source[:guard])
        self.assertIn("[IO.FileMode]::CreateNew", self.source)

    def test_child_shell_outputs_refuse_clobber(self):
        self.assertIn("set -euC", self.source)
        # CORE_BOOT/BROWSER use /work/output; RESIDENT_BROWSER gets a fresh,
        # source-head-scoped output directory. Both paths must share the same
        # exclusive-creation contract rather than hard-code the legacy path.
        self.assertIn("  output=/work/output", self.source)
        self.assertIn('  output="/work/output-resident-$VERAOS_SOURCE_HEAD"', self.source)
        for filename in ("bzImage", "rootfs.ext2"):
            with self.subTest(filename=filename):
                self.assertIn(f'test -f "$output/images/{filename}"', self.source)
                self.assertIn(
                    f'dd if="$output/images/{filename}" of=/artifacts/veraos-{filename} '
                    'bs=4M status=none conv=excl,fsync',
                    self.source,
                )
        self.assertNotIn('cp -n "$output/images/', self.source)

    @unittest.skipUnless(os.name == "posix" and shutil.which("dd"),
                         "POSIX GNU dd not available on this host")
    def test_exclusive_copy_refuses_race_created_destination(self):
        # Reproduce the child copy's flags, including creation of an existing
        # path between the host preflight and the child write.
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            destination = Path(temp) / "artifact"
            source.write_bytes(b"new qualified bytes")
            destination.write_bytes(b"old artifact bytes")
            argv = ["dd", f"if={source}", f"of={destination}", "bs=4M",
                    "status=none", "conv=excl,fsync"]
            refused = subprocess.run(argv, capture_output=True, check=False)
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(destination.read_bytes(), b"old artifact bytes")
            destination.unlink()
            created = subprocess.run(argv, capture_output=True, check=False)
            self.assertEqual(created.returncode, 0, created.stderr.decode(errors="replace"))
            self.assertEqual(destination.read_bytes(), source.read_bytes())


if __name__ == "__main__":
    unittest.main()
