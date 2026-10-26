"""Guard Buildroot non-root ext2 cleanup after copying a read-only stage."""
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
POST_BUILD = ROOT / "buildroot/board/veraos/x86_64/post-build.sh"
COPY = 'cp -R "$stage/components/." "$target_dir/opt/veraos/components/"'
REPAIR = 'find "$target_dir/opt/veraos/components" -type d -exec chmod u+w {} +'


class ResidentDirectoryModeTests(unittest.TestCase):
    def test_postbuild_repairs_target_only_before_audit(self):
        script = POST_BUILD.read_text(encoding="utf-8")
        self.assertIn(REPAIR, script)
        self.assertLess(script.index(COPY), script.index(REPAIR))
        self.assertLess(script.index(REPAIR), script.index("Verify-VeraOSResidentFiles.py"))
        self.assertNotIn('chmod -R', script)

    @unittest.skipUnless(os.name == "posix", "requires POSIX filesystem modes")
    def test_nonroot_cleanup_with_readonly_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stage = root / "frozen-stage"
            nested = stage / "components" / "portal" / "runner"
            nested.mkdir(parents=True)
            (nested / "module.py").write_bytes(b"immutable fixture\n")
            for directory in (stage / "components", stage / "components" / "portal", nested):
                directory.chmod(0o555)
            target = root / "target"
            dest = target / "opt" / "veraos" / "components"
            dest.mkdir(parents=True)
            subprocess.run(["cp", "-R", str(stage / "components") + "/.", str(dest)],
                           check=True)
            copied = dest / "portal" / "runner"
            self.assertFalse(copied.stat().st_mode & stat.S_IWUSR)
            subprocess.run(["sh", "-eu", "-c", REPAIR],
                           check=True, env={**os.environ, "target_dir": str(target)})
            self.assertTrue(copied.stat().st_mode & stat.S_IWUSR)
            self.assertEqual((copied / "module.py").read_bytes(), b"immutable fixture\n")
            self.assertFalse(nested.stat().st_mode & stat.S_IWUSR)
            shutil.rmtree(dest)
            self.assertFalse(dest.exists())
            for directory in (nested, stage / "components" / "portal", stage / "components"):
                directory.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
