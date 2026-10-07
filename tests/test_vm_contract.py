from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class VmContractTests(unittest.TestCase):
    def test_buildroot_source_is_exactly_pinned(self) -> None:
        lines = (ROOT / "buildroot" / "BUILDROOT_VERSION").read_text(
            encoding="utf-8"
        ).splitlines()
        self.assertEqual("2024.02.4", lines[0])
        self.assertEqual(
            "e0a2687421a4f93e65aa00a30bcb0b4817f7a195",
            lines[1],
        )

    def test_buildroot_core_image_uses_vera_pid1_without_browser_stack(self) -> None:
        text = (
            ROOT / "buildroot" / "configs" / "veraos_x86_64_defconfig"
        ).read_text(encoding="utf-8")
        self.assertIn("BR2_INIT_NONE=y", text)
        self.assertIn("BR2_PACKAGE_PYTHON3=y", text)
        self.assertNotIn("BR2_PACKAGE_WPEWEBKIT=y", text)
        self.assertNotIn("BR2_PACKAGE_COG=y", text)
        self.assertNotIn("BR2_PACKAGE_HOST_QEMU=y", text)
        self.assertIn('BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE="6.6.69"', text)

    def test_buildroot_browser_profile_packages_wpe_and_cog(self) -> None:
        core_text = (
            ROOT / "buildroot" / "configs" / "veraos_x86_64_defconfig"
        ).read_text(encoding="utf-8")
        text = (
            ROOT / "buildroot" / "configs" / "veraos_x86_64_browser_defconfig"
        ).read_text(encoding="utf-8")
        self.assertIn("BR2_PACKAGE_WPEWEBKIT=y", text)
        self.assertIn("BR2_PACKAGE_WPEWEBKIT_SANDBOX=y", text)
        self.assertIn("BR2_PACKAGE_WPEWEBKIT_WEBDRIVER=y", text)
        self.assertIn("BR2_PACKAGE_COG=y", text)
        self.assertIn("BR2_PACKAGE_COG_PLATFORM_DRM=y", text)
        self.assertNotIn("BR2_PACKAGE_HOST_QEMU=y", text)
        core_settings = {
            line for line in core_text.splitlines()
            if line and not line.startswith("#")
        }
        browser_settings = {
            line for line in text.splitlines()
            if line and not line.startswith("#")
        }
        self.assertTrue(core_settings <= browser_settings)

    def test_rootfs_overlay_installs_vera_as_pid1(self) -> None:
        text = (
            ROOT
            / "buildroot"
            / "board"
            / "veraos"
            / "x86_64"
            / "rootfs-overlay"
            / "sbin"
            / "vera-init"
        ).read_text(encoding="utf-8")
        self.assertTrue(text.startswith("#!/usr/bin/python3"))
        self.assertIn("from veraos.pid1 import main", text)

    def test_vm_build_and_qualification_no_longer_depend_on_nix(self) -> None:
        build = (ROOT / "tools" / "vm" / "Build-VeraOSVm.ps1").read_text(
            encoding="utf-8"
        )
        test = (ROOT / "tools" / "vm" / "Test-VeraOSVm.ps1").read_text(
            encoding="utf-8"
        )
        combined = build + test
        self.assertIn("Buildroot", build)
        self.assertIn("VERA_OS_BUILDROOT_BUILD_RESULT_V1", build)
        self.assertIn("Select-Object -First 1", build)
        self.assertNotIn(").Trim()", build)
        self.assertIn('$script = $script -replace "`r`n", "`n"', build)
        self.assertIn('veraos-buildroot-build.sh', build)
        self.assertIn('[System.IO.File]::WriteAllText(', build)
        self.assertNotIn('"-lc", $script', build)
        self.assertIn('BR2_JLEVEL="$VERAOS_JOBS"', build)
        self.assertIn('BuildProfile = "CORE_BOOT"', build)
        self.assertIn('BrowserPackaged = $false', build)
        self.assertIn("init=/sbin/vera-init", test)
        self.assertIn('$quotedAppend = \'"\' + $append + \'"\'', test)
        self.assertIn('"-append", $quotedAppend', test)
        self.assertNotIn('"-append", $append', test)
        self.assertIn("VERAOS_BOOT_READY_V1", test)
        self.assertIn('browser_packaged = $false', test)
        self.assertNotIn("flake", combined.lower())
        self.assertNotIn("nix ", combined.lower())

    def test_nix_primary_scaffold_is_absent(self) -> None:
        self.assertFalse((ROOT / "flake.nix").exists())
        self.assertFalse((ROOT / "flake.lock").exists())
        self.assertFalse((ROOT / "nixos").exists())


if __name__ == "__main__":
    unittest.main()
