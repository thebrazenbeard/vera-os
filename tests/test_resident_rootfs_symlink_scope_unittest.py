"""Target-rootfs static prerequisite gate must not read outside guest files."""
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import sys
import unittest

from test_resident_target_rootfs_preflight import (
    ROOT, StaticTargetReadinessTests, checker,
)


class GuestSymlinkBoundaryTests(unittest.TestCase):
    def setUp(self):
        fixture = StaticTargetReadinessTests(
            methodName="test_complete_static_tree_does_not_prove_runtime")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.python_link = fixture.link

    def _replace_with_link(self, rel, destination):
        original = self.root / rel
        destination.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(destination)

    def test_in_guest_relative_native_symlink_is_allowed(self):
        original = self.root / "usr/lib/libssl.so.3"
        relocated = self.root / "usr/lib/libssl-real.so.3"
        original.replace(relocated)
        original.symlink_to("libssl-real.so.3")
        outcome = checker.audit(self.root, ROOT)
        self.assertEqual(outcome["missing"], [])
        self.assertEqual(outcome["status"],
                         "TARGET_ROOTFS_STATIC_PRESENT_GUEST_UNQUALIFIED")

    def test_external_native_and_python_package_symlinks_hold(self):
        with TemporaryDirectory(prefix="veraos-host-decoy-") as td:
            for rel in ("usr/lib/libssl.so.3",
                        "usr/lib/python3.12/site-packages/yaml/__init__.py"):
                with self.subTest(rel=rel):
                    local = self.root / rel
                    original = local.read_bytes()
                    outside = Path(td) / ("host-" + local.name)
                    self._replace_with_link(rel, outside)
                    try:
                        # Absolute Linux links are guest paths; Windows drive
                        # paths are invalid. Neither may load host bytes.
                        try:
                            outcome = checker.audit(self.root, ROOT)
                        except checker.TargetPrerequisiteError:
                            pass
                        else:
                            self.assertNotEqual(outcome["status"],
                                "TARGET_ROOTFS_STATIC_PRESENT_GUEST_UNQUALIFIED")
                    finally:
                        local.unlink()
                        local.write_bytes(original)

    def test_cold_preflight_cannot_pass_host_native_decoy(self):
        self.python_link.unlink()
        self.python_link.symlink_to("python3.12")
        with TemporaryDirectory(prefix="veraos-host-decoy-") as td:
            self._replace_with_link(
                "usr/lib/libcrypto.so.3", Path(td) / "host-libcrypto.so.3")
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools/vm/Probe-ResidentTargetRootfs.py"),
                 "--rootfs-directory", str(self.root), "--repo-root", str(ROOT)],
                capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 2,
                             "Unsafe guest-path preflight unexpectedly passed")
            self.assertTrue("rootfs" in result.stderr or
                            "NOT_READY_MISSING_TARGET_PREREQUISITES" in result.stdout)


if __name__ == "__main__":
    unittest.main()
