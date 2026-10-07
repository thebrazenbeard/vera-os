from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class VmContractTests(unittest.TestCase):
    def test_flake_exposes_qualification_iso(self) -> None:
        text = (ROOT / "flake.nix").read_text(encoding="utf-8")
        self.assertIn("veraos-vm-iso", text)
        self.assertIn("nixos-unstable", text)

    def test_flake_lock_pins_exact_nixpkgs_input(self) -> None:
        lock = json.loads((ROOT / "flake.lock").read_text(encoding="utf-8"))
        locked = lock["nodes"]["nixpkgs"]["locked"]
        self.assertEqual("github", locked["type"])
        self.assertEqual("NixOS", locked["owner"])
        self.assertEqual("nixpkgs", locked["repo"])
        self.assertRegex(locked["rev"], re.compile(r"^[0-9a-f]{40}$"))
        self.assertTrue(str(locked["narHash"]).startswith("sha256-"))

    def test_base_image_embeds_and_validates_portfolio_lock(self) -> None:
        text = (ROOT / "nixos" / "modules" / "veraos-base.nix").read_text(
            encoding="utf-8"
        )
        self.assertIn("VERA_OS_PORTFOLIO_COMPOSITION_V1.json", text)
        self.assertIn("validate_manifest", text)
        self.assertIn("ambient_protected_effect_authority", text)
        self.assertIn("PATRICK_EXPLICIT_EXACT_TARGET_EFFECT", text)

    def test_vm_boot_marker_is_machine_readable_and_non_authoritative(self) -> None:
        text = (
            ROOT / "nixos" / "hosts" / "vm-qualification.nix"
        ).read_text(encoding="utf-8-sig")
        self.assertIn("VERAOS_VM_BOOT_OK", text)
        self.assertIn("ambient_protected_effect_authority=$ambient", text)
        self.assertNotIn("wheelNeedsPassword", text)
        self.assertNotIn("autologin", text)

    def test_qemu_runner_is_software_emulation_compatible(self) -> None:
        text = (
            ROOT / "tools" / "vm" / "qemu-runner.Dockerfile"
        ).read_text(encoding="utf-8")
        self.assertIn("qemu-system-x86", text)
        self.assertIn('ENTRYPOINT ["qemu-system-x86_64"]', text)


if __name__ == "__main__":
    unittest.main()
