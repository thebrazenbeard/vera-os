"""Rootfs prerequisite resolution of *directory* guest symlinks, not guest execution.

The guest's absolute /usr/lib -> /lib-real must be interpreted in the target
namespace. A host absolute path must never satisfy an absent guest prerequisite.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "resident_rootfs_guest_parent", ROOT / "tools/vm/Probe-ResidentTargetRootfs.py"
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class GuestParentSymlinkScopeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="veraos-parent-link-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "guest"
        self.repo = self.base / "source"

        def put(path: str, value: bytes = b"guest-byte") -> Path:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)
            return target

        put("usr/bin/python3.12")
        (self.root / "usr/bin/python3").symlink_to("python3.12")
        for name in ("sqlite3/__init__.py", "ssl.py", "json/__init__.py",
                     "http/server.py", "socket.py"):
            put("usr/lib/python3.12/" + name)
        for name in ("_ssl", "_sqlite3"):
            put("usr/lib/python3.12/lib-dynload/" + name + ".cpython-312-x86_64-linux-gnu.so")
        for name in ("jsonschema", "cryptography", "yaml"):
            put("usr/lib/python3.12/site-packages/" + name + "/__init__.py")
        for name in ("libsqlite3.so.0", "libssl.so.3", "libcrypto.so.3"):
            put("usr/lib/" + name)
        put("usr/bin/cog")
        put("usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        for name in ("pid1.py", "resident.py", "desktop.py"):
            put("opt/veraos/src/veraos/" + name)
            original = self.root / "opt/veraos/src/veraos" / name
            target = self.repo / "src/veraos" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
        launcher = b"#!/usr/bin/python3\nfrom veraos.pid1 import main\nraise SystemExit(main())\n"
        put("sbin/vera-init", launcher)
        expected = self.repo / "buildroot/board/veraos/x86_64/rootfs-overlay/sbin/vera-init"
        expected.parent.mkdir(parents=True, exist_ok=True)
        expected.write_bytes(launcher)

    def audit(self):
        return checker.audit(self.root, self.repo)

    def test_normal_static_tree_and_missing_native_dependency(self):
        self.assertEqual(self.audit()["missing"], [])
        missing = self.root / "usr/lib/libcrypto.so.3"
        missing.unlink()
        report = self.audit()
        self.assertIn("/usr/lib/libcrypto.so.3", report["missing"])
        self.assertEqual(report["status"], "NOT_READY_MISSING_TARGET_PREREQUISITES")

    def test_final_guest_absolute_link_remains_within_rootfs(self):
        real = self.root / "usr/lib/libssl.so.3"
        real.rename(self.root / "libssl-real.so.3")
        real.symlink_to("/libssl-real.so.3")
        self.assertEqual(self.audit()["missing"], [])

    def test_final_host_absolute_symlink_never_reads_host_bytes(self):
        real = self.root / "usr/lib/libssl.so.3"
        outside = self.base / "host-libssl.so.3"
        real.rename(outside)
        real.symlink_to(outside)
        report = self.audit()
        self.assertIn("/usr/lib/libssl.so.3", report["missing"])

    def test_mismatched_guest_resident_source_rejected(self):
        resident = self.root / "opt/veraos/src/veraos/resident.py"
        resident.write_bytes(b"source modified")
        self.assertIn("source mismatch /opt/veraos/src/veraos/resident.py",
                      self.audit()["missing"])

    def test_absolute_guest_directory_link_uses_guest_files_not_host_path(self):
        real = self.root / "usr/lib"
        real.rename(self.root / "lib-real")
        real.symlink_to("/lib-real", target_is_directory=True)
        report = self.audit()
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["status"], "TARGET_ROOTFS_STATIC_PRESENT_GUEST_UNQUALIFIED")
        self.assertIs(report["target_import_executed"], False)

    def test_guest_directory_link_chain_and_font_asset(self):
        lib = self.root / "usr/lib"
        lib.rename(self.root / "lib-real")
        lib.symlink_to("/lib-stage", target_is_directory=True)
        (self.root / "lib-stage").symlink_to("/lib-real", target_is_directory=True)
        fonts = self.root / "usr/share/fonts"
        fonts.rename(self.root / "font-real")
        fonts.symlink_to("/font-real", target_is_directory=True)
        self.assertEqual(self.audit()["missing"], [])

    def test_guest_absolute_link_cannot_consume_existing_host_decoy(self):
        real = self.root / "usr/lib"
        host = self.base / "host-lib"
        real.rename(host)
        real.symlink_to(host, target_is_directory=True)
        try:
            report = self.audit()
        except checker.TargetPrerequisiteError:
            return  # Stronger fail-closed outcome is acceptable.
        self.assertNotEqual(report["status"], "TARGET_ROOTFS_STATIC_PRESENT_GUEST_UNQUALIFIED")

    def test_parent_symlink_cycle_fails_closed(self):
        real = self.root / "usr/lib"
        real.rename(self.root / "lib-real")
        real.symlink_to("/usr/lib", target_is_directory=True)
        with self.assertRaises(checker.TargetPrerequisiteError):
            self.audit()


if __name__ == "__main__":
    unittest.main()
