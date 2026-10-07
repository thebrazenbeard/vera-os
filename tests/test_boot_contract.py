from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from veraos.boot_contract import BootContractError, validate_boot_contract
from veraos.pid1 import boot_marker, main as pid1_main, prepare_boot_state


BOOT_CONTRACT = ROOT / "architecture" / "os" / "VERA_OS_BOOT_CONTRACT_V1.json"
COMPOSITION = ROOT / "architecture" / "portfolio" / "VERA_OS_PORTFOLIO_COMPOSITION_V1.json"


class VeraOsBootContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(BOOT_CONTRACT.read_text(encoding="utf-8"))
        cls.composition = json.loads(COMPOSITION.read_text(encoding="utf-8"))

    def test_vera_is_base_and_linux_buildroot_are_substrate(self) -> None:
        validate_boot_contract(self.contract)
        product = self.contract["product"]
        self.assertEqual("VERA", product["base_identity"])
        self.assertEqual("KERNEL_DRIVER_HARDWARE_SUBSTRATE", product["linux_role"])
        self.assertEqual("BUILDROOT", product["image_builder"])
        self.assertFalse(product["image_builder_is_os_identity"])
        self.assertEqual("RETIRED", product["nixos_primary_path_status"])

    def test_runtime_owners_and_boot_independence_are_exact(self) -> None:
        runtime = self.contract["runtime"]
        self.assertEqual("thebrazenbeard/vera-mono", runtime["identity_runtime_owner"])
        self.assertEqual("thebrazenbeard/rezon", runtime["reasoning_owner"])
        self.assertEqual("thebrazenbeard/portal", runtime["provider_router"])
        self.assertFalse(runtime["cognition_provider_required_for_boot"])
        self.assertFalse(runtime["trained_vera_model_required_for_boot"])

    def test_browser_is_required_product_capability_not_boot_dependency(self) -> None:
        browser = self.contract["browser"]
        self.assertTrue(browser["first_class_capability_required"])
        self.assertFalse(browser["required_for_core_boot"])
        self.assertEqual("WPE_WEBKIT", browser["initial_engine"])
        self.assertEqual("COG", browser["initial_shell"])

    def test_nixos_cannot_be_reintroduced_as_base_identity(self) -> None:
        bad = json.loads(json.dumps(self.contract))
        bad["product"]["base_identity"] = "NIXOS"
        with self.assertRaisesRegex(BootContractError, "Vera must be"):
            validate_boot_contract(bad)

    def test_pid1_ready_marker_binds_portfolio_and_authority(self) -> None:
        state = prepare_boot_state(self.contract, self.composition, pid=1)
        self.assertEqual(84, state.portfolio_total)
        self.assertEqual(79, state.portfolio_integrated)
        self.assertEqual(5, state.portfolio_excluded)
        marker = boot_marker(state)
        self.assertIn("pid=1", marker)
        self.assertIn("base=VERA", marker)
        self.assertIn("cognition_required=false", marker)
        self.assertIn("browser_first_class=true", marker)
        self.assertIn("ambient_protected_effect_authority=false", marker)

    def test_pid1_source_can_be_qualified_without_becoming_host_pid1(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            contract = temp_path / "boot.json"
            composition = temp_path / "composition.json"
            run_root = temp_path / "run"
            contract.write_text(json.dumps(self.contract), encoding="utf-8")
            composition.write_text(json.dumps(self.composition), encoding="utf-8")
            result = pid1_main([
                "--allow-non-pid1",
                "--boot-contract", str(contract),
                "--composition", str(composition),
                "--run-root", str(run_root),
            ])
            self.assertEqual(0, result)
            state = json.loads((run_root / "boot-state.json").read_text(encoding="utf-8"))
            self.assertEqual("VERA", state["base_identity"])


if __name__ == "__main__":
    unittest.main()
