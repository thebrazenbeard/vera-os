import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "builder_inputs", ROOT / "tools/vm/Inspect-VeraOSBuilderInputs.py")
mod = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)

HEAD = "d030e36bbc9669230c015be971b14b6e062cfdde"
TAG = "b611e07ef088c70c1e21f77c30872bce97a1f1c2"
RECEIPT = "6f0031c1fcbaed41e4e3f6947e90a92ed5656ac3e09329de7d8e0b0f8417eca5"


class BuilderInputsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="os44-inputs-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.builder = self.root / "buildroot"
        self.builder.mkdir()
        mk = self.builder / "package/python3/python3.mk"
        mk.parent.mkdir(parents=True)
        mk.write_text("PYTHON3_VERSION_MAJOR = 3.12\nPYTHON3_VERSION = $(PYTHON3_VERSION_MAJOR).14\n")
        self.repo = self.root / "veraos"
        profile = self.repo / "architecture/os/VERA_OS_RESIDENT_GUEST_PROFILE_V1.json"
        profile.parent.mkdir(parents=True)
        profile.write_text(json.dumps({
            "schema": "VERA_OS_RESIDENT_GUEST_PROFILE_V1",
            "builder": {
                "version": "2025.02.18", "peeled_git_commit": HEAD,
                "annotated_tag_sha": TAG,
                "source_defconfig": "buildroot/configs/veraos_x86_64_resident_browser_defconfig",
            },
            "target_python": {"version": "3.12.14"},
            "selected_stage": {"receipt_sha256": RECEIPT},
        }))
        conf = self.repo / "buildroot/configs/veraos_x86_64_resident_browser_defconfig"
        conf.parent.mkdir(parents=True)
        conf.write_bytes(b"frozen-test-defconfig\n")
        import hashlib
        self.sha = hashlib.sha256(conf.read_bytes()).hexdigest()
        self.git_return = [HEAD, TAG, HEAD, ""]

    def inspect(self):
        with patch.object(mod, "_git", side_effect=self.git_return):
            return mod.inspect_builder_inputs(
                self.builder, self.repo, expected_defconfig_sha256=self.sha)

    def test_exact_source_reports_no_image_selection(self):
        report = self.inspect()
        self.assertEqual(report.source_input_status, "SOURCE_INPUTS_MATCH_ONLY")
        self.assertFalse(report.selected_final_image)
        self.assertFalse(report.packed_source_bytes_verified)
        self.assertFalse(report.qualified_vera_runtime_consumed)

    def test_even_existing_images_directory_not_selected(self):
        (self.builder / "output/images").mkdir(parents=True)
        report = self.inspect()
        self.assertTrue(report.output_images_present_unqualified)
        self.assertFalse(report.selected_final_image)

    def test_wrong_head_or_tag_held(self):
        for i in (0, 1, 2):
            with self.subTest(i=i):
                self.git_return = [HEAD, TAG, HEAD, ""]
                self.git_return[i] = "f"*40
                with self.assertRaisesRegex(mod.BuilderInputHold, "mismatch"):
                    self.inspect()

    def test_dirty_builder_held(self):
        self.git_return = [HEAD, TAG, HEAD, " M package/python3/python3.mk"]
        with self.assertRaisesRegex(mod.BuilderInputHold, "modified"):
            self.inspect()

    def test_wrong_python_held(self):
        (self.builder/"package/python3/python3.mk").write_text(
            "PYTHON3_VERSION_MAJOR = 3.11\nPYTHON3_VERSION = $(PYTHON3_VERSION_MAJOR).14\n")
        with self.assertRaisesRegex(mod.BuilderInputHold, "Python version"):
            self.inspect()

    def test_defconfig_change_held(self):
        with patch.object(mod, "_git", side_effect=[HEAD, TAG, HEAD, ""]):
            with self.assertRaisesRegex(mod.BuilderInputHold, "defconfig digest"):
                mod.inspect_builder_inputs(self.builder,self.repo,
                    expected_defconfig_sha256="0"*64)


if __name__=="__main__":
    unittest.main()
