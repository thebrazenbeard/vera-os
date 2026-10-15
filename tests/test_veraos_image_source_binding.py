"""Fail-closed verification: a qualifying VeraOS head cannot rewrite its image source."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/vm/Verify-VeraOSBuildSource.py"
SPEC = importlib.util.spec_from_file_location("veraos_image_source", SOURCE)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

VALID = {
    ("rev-parse", "HEAD"): "c" * 40,
    ("status", "--porcelain=v1", "--untracked-files=all"): "",
    ("merge-base", "--is-ancestor", guard.IMAGE_HEAD, "c" * 40): "",
    ("diff", "--no-renames", "--name-status", guard.IMAGE_HEAD, "c" * 40):
        "A\ttools/vm/Verify-VeraOSBuildSource.py\n"
        "A\ttools/vm/Finalize-VeraOSResidentBuild.ps1\n"
        "M\ttools/vm/Test-VeraOSVm.ps1\n",
}


class ImageSourceBindingTests(unittest.TestCase):
    def run_binding(self, overrides=None):
        with tempfile.TemporaryDirectory() as tmp:
            data = dict(VALID)
            data.update(overrides or {})

            def fake_git(repo, *args):
                key = tuple(args)
                if key not in data:
                    raise guard.ImageSourceError("Unexpected Git operation")
                value = data[key]
                if isinstance(value, Exception):
                    raise value
                return value

            with patch.object(guard, "git", fake_git):
                return guard.validate_image_source(Path(tmp))

    def test_immutable_builder_and_distinct_tool_heads(self):
        evidence = self.run_binding()
        self.assertEqual(evidence["image_build_source_head"], guard.IMAGE_HEAD)
        self.assertEqual(evidence["qualification_tool_head"], "c" * 40)
        self.assertTrue(evidence["image_source_unchanged_since_build"])

    def test_reject_dirty_checkout(self):
        with self.assertRaisesRegex(guard.ImageSourceError, "dirty"):
            self.run_binding({
                ("status", "--porcelain=v1", "--untracked-files=all"):
                    "?? unsafe-produced-file",
            })

    def test_reject_non_ancestor(self):
        with self.assertRaisesRegex(guard.ImageSourceError, "Git"):
            self.run_binding({
                ("merge-base", "--is-ancestor", guard.IMAGE_HEAD, "c" * 40):
                    guard.ImageSourceError("Git refused different ancestry")
            })

    def test_reject_buildroot_change(self):
        with self.assertRaisesRegex(guard.ImageSourceError, "changed image"):
            self.run_binding({
                ("diff", "--no-renames", "--name-status", guard.IMAGE_HEAD, "c" * 40):
                    "A\ttools/vm/Verify-VeraOSBuildSource.py\n"
                    "M\tbuildroot/configs/veraos_x86_64_resident_browser_defconfig",
            })

    def test_reject_runtime_change(self):
        with self.assertRaisesRegex(guard.ImageSourceError, "changed image"):
            self.run_binding({
                ("diff", "--no-renames", "--name-status", guard.IMAGE_HEAD, "c" * 40):
                    "A\ttools/vm/Verify-VeraOSBuildSource.py\n"
                    "M\tsrc/veraos/pid1.py",
            })

    def test_reject_renamed_or_deleted_paths(self):
        for action in ("D", "R100"):
            with self.subTest(action=action):
                with self.assertRaisesRegex(guard.ImageSourceError, "changed image|record"):
                    self.run_binding({
                        ("diff", "--no-renames", "--name-status", guard.IMAGE_HEAD, "c" * 40):
                            "A\ttools/vm/Verify-VeraOSBuildSource.py\n"
                            + action + "\ttools/vm/Test-VeraOSVm.ps1",
                    })

    def test_reject_unknown_builder_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(guard.ImageSourceError, "Unknown"):
                guard.validate_image_source(Path(tmp), "0" * 40)

    def test_reject_empty_or_missing_qualification_helper(self):
        with self.assertRaisesRegex(guard.ImageSourceError, "not pinned"):
            self.run_binding({
                ("diff", "--no-renames", "--name-status", guard.IMAGE_HEAD, "c" * 40):
                    "A\ttools/vm/Finalize-VeraOSResidentBuild.ps1",
            })

    def test_finalizer_and_boot_are_bound_to_original_image(self):
        finalizer = (ROOT / "tools/vm/Finalize-VeraOSResidentBuild.ps1").read_text("utf8")
        vm = (ROOT / "tools/vm/Test-VeraOSVm.ps1").read_text("utf8")
        self.assertIn("sourceBinding.image_build_source_head", finalizer)
        self.assertIn("SourceHead = $head", finalizer)
        self.assertIn("QualificationToolHead = $qualificationHead", finalizer)
        self.assertIn("$buildReceipt.SourceHead -ne $imageSource", vm)
        self.assertIn("$buildReceipt.QualificationToolHead -ne $currentHead", vm)
        self.assertIn("qualification_tool_head = $currentHead", vm)
        self.assertNotIn("ResidentCoreImportQualified = $true", finalizer)


if __name__ == "__main__":
    unittest.main()
