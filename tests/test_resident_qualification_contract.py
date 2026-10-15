"""Source guard against premature resident-browser image qualification."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FINALIZE = ROOT / "tools/vm/Finalize-VeraOSResidentBuild.ps1"
TEST = ROOT / "tools/vm/Test-VeraOSVm.ps1"


class ResidentCompletionContractTests(unittest.TestCase):
    def test_completion_requires_exact_input_provenance_and_terminal_artifacts(self):
        s = FINALIZE.read_text(encoding="utf-8")
        self.assertIn("ExpectedSourceHead", s)
        self.assertIn("Stage-VeraOSResidentSources.py", s)
        self.assertIn("--verify-stage", s)
        self.assertIn("volume=$BuildVolume", s)
        self.assertIn('Build result exists: refuse overwrite', s)
        self.assertIn("[IO.FileMode]::CreateNew", s)
        self.assertIn("Get-FileHash", s)
        self.assertIn('Builder SHA manifest disagrees with final image', s)
        self.assertIn("d030e36bbc9669230c015be971b14b6e062cfdde", s)
        self.assertIn("readonly", s)
        self.assertIn('ResidentCoreImportQualified = $false', s)
        self.assertIn('OfflinePortfolioMountedInGuest = $false', s)
        self.assertIn('ProtectedEffectAuthority = $false', s)
        self.assertNotIn('diskpart ', s.lower())
        self.assertNotIn('docker rm -f', s.lower())
        self.assertNotIn('schtasks', s.lower())

    def test_qemu_boot_supports_resident_profile_without_promoting_import(self):
        s = TEST.read_text(encoding="utf-8")
        self.assertIn('elseif ($buildProfile -eq "RESIDENT_BROWSER")', s)
        self.assertIn('veraos_x86_64_resident_browser_defconfig', s)
        self.assertIn('BuildrootVersion -ne "2025.02.18"', s)
        self.assertIn('ResidentCoreSourceStaged -ne $true', s)
        self.assertIn('ResidentCoreImportQualified -ne $false', s)
        self.assertIn('resident_core_import_qualified = $false', s)
        self.assertIn('trained_model_route_qualified = $false', s)
        self.assertIn('offline_portfolio_guest_mount_qualified = $false', s)
        self.assertIn('"none"', s)
        self.assertIn('"qcow2"', s)
        self.assertIn('restart_boot_passes = 2', s)

    def test_legacy_profiles_remain_supported(self):
        s = TEST.read_text(encoding="utf-8")
        for marker in ('"CORE_BOOT"', '"BROWSER"', '"RESIDENT_BROWSER"'):
            self.assertIn(marker, s)
        self.assertIn('image_builder = ("BUILDROOT_"', s)


if __name__ == "__main__":
    unittest.main()
