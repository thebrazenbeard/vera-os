import importlib.util
from pathlib import Path
import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "measured_build_tools", ROOT / "tools/vm/Inspect-VeraOSBuilderTools.py")
import sys
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


@unittest.skipUnless(os.name == "posix", "POSIX-only artifact")
class BuilderToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="veraos-os45-tools-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.binary = self.dir / "real-make"
        self.binary.write_bytes(b"#!/bin/sh\necho local-fixed\n")
        self.binary.chmod(0o755)
        self.alias = self.dir / "make"
        self.alias.symlink_to(self.binary)

    def measure(self, expected=None):
        with patch.object(module.shutil, "which", return_value=str(self.alias)):
            return module.measure_tool("make", expected_sha256=expected)

    def test_real_open_descriptor_bytes_and_alias_flag(self):
        record = self.measure()
        self.assertEqual(record.sha256, hashlib.sha256(self.binary.read_bytes()).hexdigest())
        self.assertTrue(record.path_is_symlink)
        self.assertFalse(record.future_exec_identity_verified)
        self.assertFalse(record.dependency_closure_verified)

    def test_wrong_or_malformed_expected_digest_holds(self):
        for value in ("0" * 64, "ABC", "F" * 64):
            with self.subTest(value=value):
                with self.assertRaises(module.BuilderToolHold):
                    self.measure(value)

    def test_missing_tool_holds(self):
        with patch.object(module.shutil, "which", return_value=None):
            with self.assertRaisesRegex(module.BuilderToolHold, "missing"):
                module.measure_tool("make")

    def test_mutated_tool_bytes_rehash_to_new_identity(self):
        old = self.measure()
        self.binary.write_bytes(b"#!/bin/sh\necho changed!\n")
        with self.assertRaisesRegex(module.BuilderToolHold, "differs"):
            self.measure(old.sha256)
        self.assertNotEqual(old.sha256, self.measure().sha256)

    def test_nonexecutable_file_holds(self):
        self.binary.chmod(0o600)
        with self.assertRaisesRegex(module.BuilderToolHold, "not an executable"):
            self.measure()

    def test_overlarge_sparse_binary_holds(self):
        with self.binary.open("wb") as writer:
            writer.truncate(module.MAX_TOOL_SIZE_BYTES + 1)
        with self.assertRaisesRegex(module.BuilderToolHold, "size range"):
            self.measure()

    def test_no_false_build_or_boot_qualification(self):
        m = self.measure()
        receipt = module.BuilderToolInventory(tools=(m,), platform="test", process_pid=1)
        self.assertEqual(receipt.status, "LOCAL_BUILDER_TOOL_BYTES_OBSERVED_ONLY")
        for field in ("buildroot_source_binding_verified", "container_image_rebuild_reproducible",
                      "transitive_dependencies_verified", "subsequent_execve_binding_verified",
                      "final_output_images_verified", "guest_boot_verified", "qualified_runtime_consumed"):
            self.assertFalse(getattr(receipt, field))


if __name__ == "__main__":
    unittest.main()
