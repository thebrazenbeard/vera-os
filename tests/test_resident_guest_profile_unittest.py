import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "resident_guest_profile", ROOT / "tools/vm/Verify-VeraOSResidentGuestProfile.py"
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class ResidentGuestProfileTests(unittest.TestCase):
    def setUp(self):
        def read(path):
            return json.loads((ROOT / path).read_text(encoding="utf-8"))
        self.profile = read("architecture/os/VERA_OS_RESIDENT_GUEST_PROFILE_V1.json")
        self.candidate = read("architecture/os/VERA_OS_RESIDENT_BUILDROOT_CANDIDATE_V1.json")
        self.legacy = read("architecture/os/VERA_OS_BOOT_CONTRACT_V1.json")
        heads = self.profile["selected_stage"]["component_heads"]
        self.receipt = json.dumps({
            "schema": "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1",
            "authority": False,
            "components": [{"repository": k, "source_head": v, "file_count": 0, "files": []}
                           for k, v in heads.items()],
        }).encode()

    def assert_hold(self, *, profile=None, candidate=None, legacy=None, receipt=None):
        with self.assertRaises(mod.ResidentGuestProfileError):
            mod.validate_guest_profile(profile or self.profile, candidate or self.candidate,
                                       legacy or self.legacy, receipt or self.receipt)

    def test_historical_contract_remains_unchanged_separate_guest_scope(self):
        self.assertEqual(self.legacy["product"]["image_builder_version"], "2024.02.4")
        self.assertEqual(self.candidate["candidate"]["version"], "2025.02.18")
        self.assertFalse(self.profile["proof"]["booted_guest"])
        self.assert_hold()  # fabricated 0-file receipt cannot match 431-file frozen stage

    def test_selected_builder_substitution_held(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["candidate"]["peeled_git_commit"] = "0" * 40
        self.assert_hold(candidate=candidate)

    def test_guest_profile_cannot_promote_an_unbuilt_image(self):
        profile = copy.deepcopy(self.profile)
        profile["proof"]["selected_final_image"] = True
        self.assert_hold(profile=profile)

    def test_nixos_primary_host_cannot_be_silently_retired(self):
        profile = copy.deepcopy(self.profile)
        profile["product_primary_host"]["nixos"] = "RETIRED"
        self.assert_hold(profile=profile)

    def test_target_python_is_pinned_separately_from_abi(self):
        profile = copy.deepcopy(self.profile)
        profile["target_python"]["version"] = "3.12.0"
        self.assert_hold(profile=profile)


if __name__ == "__main__":
    unittest.main()
