"""Source-only regression contracts for the selected VeraOS resident Docker builder.

No Docker, Buildroot, or untrusted historical editor task is executed here.
A green test proves static wiring, not a compiled or booted image.
"""
from pathlib import Path
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
        self.assertIn("cp -n /work/output/images/bzImage /artifacts/veraos-bzImage", self.source)
        self.assertIn("cp -n /work/output/images/rootfs.ext2 /artifacts/veraos-rootfs.ext2", self.source)


if __name__ == "__main__":
    unittest.main()
