"""Hostile, no-dependency checks of opt-in static Buildroot prerequisite gate."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "target_rootfs_preflight", ROOT / "tools/vm/Probe-ResidentTargetRootfs.py"
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class StaticTargetReadinessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="vera-os-readiness-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "target"

        def put(rel, value=b"placeholder"):
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(value)
            return p
        self.put = put
        self.link = put("usr/bin/python3")
        put("usr/bin/python3.12")
        real_is_link, real_readlink = Path.is_symlink, Path.readlink
        a = patch.object(Path, "is_symlink",
            lambda path: path == self.link or real_is_link(path))
        b = patch.object(Path, "readlink",
            lambda path: Path("python3.12") if path == self.link
            else real_readlink(path))
        a.start()
        b.start()
        self.addCleanup(a.stop)
        self.addCleanup(b.stop)
        for name in ("sqlite3/__init__.py", "ssl.py", "json/__init__.py",
                     "http/server.py", "socket.py"):
            put("usr/lib/python3.12/" + name)
        for name in ("_sqlite3", "_ssl"):
            put("usr/lib/python3.12/lib-dynload/" +
                name + ".cpython-312-x86_64-linux-gnu.so")
        for name in ("jsonschema", "cryptography", "yaml"):
            put("usr/lib/python3.12/site-packages/" + name + "/__init__.py")
        for name in ("libsqlite3.so.0", "libssl.so.3", "libcrypto.so.3"):
            put("usr/lib/" + name)
        put("sbin/ip").chmod(0o755)
        put("usr/bin/cog")
        put("usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        for name in ("pid1.py", "resident.py", "desktop.py"):
            put("opt/veraos/src/veraos/" + name,
                (ROOT / "src/veraos" / name).read_bytes())
        put("sbin/vera-init",
            (ROOT / "buildroot/board/veraos/x86_64/rootfs-overlay/sbin/vera-init").read_bytes())

    def test_complete_static_tree_does_not_prove_runtime(self):
        result = checker.audit(self.root, ROOT)
        self.assertEqual(result["status"], "TARGET_ROOTFS_STATIC_PRESENT_GUEST_UNQUALIFIED", result["missing"])
        self.assertEqual(result["missing"], [])
        for key in ("target_import_executed", "pid1_executed", "cog_rendered",
                    "image_built_by_this_probe", "model_activated",
                    "canonical_memory_mutated", "protected_effect_authority"):
            self.assertIs(result[key], False)

    def test_missing_modules_assets_and_pid1_all_fail(self):
        missing = {
            "usr/lib/python3.12/sqlite3/__init__.py": "sqlite3",
            "usr/lib/python3.12/lib-dynload/_sqlite3.cpython-312-x86_64-linux-gnu.so": "_sqlite3",
            "usr/lib/python3.12/lib-dynload/_ssl.cpython-312-x86_64-linux-gnu.so": "_ssl",
            "usr/lib/python3.12/site-packages/cryptography/__init__.py": "cryptography",
            "usr/lib/python3.12/site-packages/yaml/__init__.py": "yaml",
            "usr/bin/cog": "cog",
            "usr/share/fonts/truetype/dejavu/DejaVuSans.ttf": "DejaVuSans.ttf",
            "opt/veraos/src/veraos/resident.py": "resident.py",
            "sbin/vera-init": "vera-init",
        }
        for rel, diagnostic in missing.items():
            with self.subTest(rel=rel):
                p = self.root / rel
                raw = p.read_bytes()
                p.unlink()
                outcome = checker.audit(self.root, ROOT)
                self.assertEqual(outcome["status"], "NOT_READY_MISSING_TARGET_PREREQUISITES")
                self.assertTrue(any(diagnostic in s for s in outcome["missing"]))
                self.assertIs(outcome["target_import_executed"], False)
                p.write_bytes(raw)

    def test_missing_explicit_shared_library_dependencies_fail(self):
        for soname in ("libsqlite3.so.0", "libssl.so.3", "libcrypto.so.3"):
            with self.subTest(soname=soname):
                path = self.root / "usr/lib" / soname
                original = path.read_bytes()
                path.unlink()
                result = checker.audit(self.root, ROOT)
                self.assertIn("/usr/lib/" + soname, result["missing"])
                self.assertEqual(result["status"], "NOT_READY_MISSING_TARGET_PREREQUISITES")
                path.write_bytes(original)

    def test_missing_or_nonexecutable_pid1_loopback_tool_holds(self):
        # PID1 invokes this exact absolute path before it admits Cog.
        loopback_tool = self.root / "sbin/ip"
        loopback_tool.unlink()
        self.assertIn("/sbin/ip executable", checker.audit(self.root, ROOT)["missing"])
        loopback_tool.write_bytes(b"synthetic host-only fixture")
        loopback_tool.chmod(0o644)
        self.assertIn("/sbin/ip executable", checker.audit(self.root, ROOT)["missing"])
        loopback_tool.chmod(0o755)
        self.assertNotIn("/sbin/ip executable", checker.audit(self.root, ROOT)["missing"])

    def test_malformed_pid1_and_source_mismatch_fail(self):
        pid = self.root / "sbin/vera-init"
        pid.write_bytes(b"#!/bin/sh\nexec /usr/bin/cog\n")
        desktop = self.root / "opt/veraos/src/veraos/desktop.py"
        desktop.write_bytes(desktop.read_bytes() + b"\n# unauthorized\n")
        violations = checker.audit(self.root, ROOT)["missing"]
        self.assertTrue(any("invalid PID1" in x for x in violations))
        self.assertTrue(any("source mismatch" in x for x in violations))

    def test_wrong_python_minor_fails(self):
        real = Path.readlink
        with patch.object(Path, "readlink", lambda obj: Path("python3.11")
                          if obj == self.link else real(obj)):
            self.assertIn("/usr/bin/python3 -> python3.12",
                          checker.audit(self.root, ROOT)["missing"])

    def test_post_build_has_target_byte_and_prerequisite_gates(self):
        text = (ROOT / "buildroot/board/veraos/x86_64/post-build.sh").read_text()
        self.assertLess(text.index('cp -R "$stage/components/."'),
                        text.index("Verify-VeraOSResidentFiles.py"))
        self.assertLess(text.index("Verify-VeraOSResidentFiles.py"),
                        text.index("Probe-ResidentTargetRootfs.py"))
        self.assertIn('python3.12|/usr/bin/python3.12)', text)
        self.assertNotIn("python3.13|python3.14", text)
        self.assertIn('--rootfs-directory "$target_dir"', text)


if __name__ == "__main__":
    unittest.main()
