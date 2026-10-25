"""Physical Linux synthetic mke2fs execution; not selected Buildroot output."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
import os
import shutil

HERE=Path(__file__).resolve().parents[1]/"tools/vm"
SPEC=importlib.util.spec_from_file_location("synthetic_fd_packer",HERE/"Observe-VeraOSLocalPacker.py")
module=importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name]=module
SPEC.loader.exec_module(module)

@unittest.skipUnless(os.name=="posix" and shutil.which("mke2fs") and shutil.which("debugfs"),
                     "Linux ext2 utilities required")
class LocalPackerFdTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="os46-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.stage=self.root/"stage"
        self.stage.mkdir()
        self.member=self.stage/"opt/veraos/probe"
        self.member.parent.mkdir(parents=True)
        self.member.write_bytes(b"selected-fixture-member\n")
        self.tool=module._tool_observer().measure_tool("mke2fs").sha256

    def test_actual_fd_launched_packer_produces_debugfs_readable_bytes(self):
        with module.observe_synthetic_ext2_pack(self.stage,expected_packer_sha256=self.tool) as (image,receipt):
            self.assertEqual(receipt.measured_tool_sha256,receipt.launched_descriptor_sha256)
            self.assertGreater(receipt.child_pid,0)
            self.assertEqual(receipt.child_exit_code,0)
            self.assertEqual(receipt.output_relative_path,"output/images/rootfs.ext2")
            self.assertEqual(receipt.output_bytes,8*1024*1024)
            self.assertEqual(receipt.status,"LOCAL_SYNTHETIC_PACKER_FD_LAUNCH_ONLY")
            for name in ("packed_member_semantics_verified","buildroot_selected_source_consumption_verified",
                         "actual_buildroot_output_images_verified","transitive_toolchain_closure_verified",
                         "future_execve_identity_verified","bootloader_consumption_verified",
                         "guest_boot_verified","qualified_vera_runtime_consumed"):
                self.assertFalse(getattr(receipt,name),name)
            proc=subprocess.run(["debugfs","-R","cat /opt/veraos/probe",str(image)],
                                capture_output=True,check=True)
            self.assertEqual(proc.stdout,b"selected-fixture-member\n")

    def test_bad_expected_executable_digest_never_launches(self):
        with self.assertRaisesRegex(ValueError,"digest differs"):
            with module.observe_synthetic_ext2_pack(self.stage,expected_packer_sha256="0"*64):
                self.fail("unrecognized tool launched")

    def test_disallow_oversized_or_bool_fixture_size(self):
        for size in (3,17,True):
            with self.subTest(size=size),self.assertRaisesRegex(module.PackerObservationHold,"4..16"):
                with module.observe_synthetic_ext2_pack(self.stage,expected_packer_sha256=self.tool,size_mib=size):
                    self.fail("invalid size launched")

    def test_empty_fixture_is_held(self):
        empty=self.root/"empty";empty.mkdir()
        with self.assertRaisesRegex(module.PackerObservationHold,"empty"):
            with module.observe_synthetic_ext2_pack(empty,expected_packer_sha256=self.tool):
                self.fail("empty fixture launched")

    def test_member_symlink_is_held(self):
        (self.stage/"alias").symlink_to(self.member)
        with self.assertRaisesRegex(module.PackerObservationHold,"symlink"):
            with module.observe_synthetic_ext2_pack(self.stage,expected_packer_sha256=self.tool):
                self.fail("symlink fixture launched")

    def test_source_root_symlink_is_held(self):
        alias=self.root/"alias"
        alias.symlink_to(self.stage,target_is_directory=True)
        with self.assertRaisesRegex(module.PackerObservationHold,"real directory"):
            with module.observe_synthetic_ext2_pack(alias,expected_packer_sha256=self.tool):
                self.fail("source alias launched")

    def test_too_many_fixture_members_held(self):
        for x in range(65):
            (self.stage/f"{x}.txt").write_text("x")
        with self.assertRaisesRegex(module.PackerObservationHold,"tiny bound"):
            with module.observe_synthetic_ext2_pack(self.stage,expected_packer_sha256=self.tool):
                self.fail("overbound source launched")

if __name__=="__main__":
    unittest.main()
