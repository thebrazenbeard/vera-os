import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).with_name("Build-VeraOSNative.sh")

class NativeBuilderGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.repo = self.root / "source"
        self.repo.mkdir()
        (self.repo / "buildroot").mkdir()
        (self.repo / "buildroot" / "external.desc").write_text("name: VERAOS\n")
        for args in [("init", "-q"), ("config", "user.email", "test@example.invalid"), ("config", "user.name", "Test"), ("add", "."), ("commit", "-qm", "init")]:
            subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def invoke(self, artifacts=None, profile="CORE_BOOT", jobs="4"):
        return subprocess.run(["bash", str(SCRIPT), str(self.repo), str(artifacts or self.root / "artifacts"), profile, jobs], capture_output=True, text=True)

    def test_dirty_source_rejected(self):
        (self.repo / "untracked").write_text("dirty")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dirty", result.stderr.lower())

    def test_artifacts_inside_source_rejected(self):
        result = self.invoke(self.repo / "artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside source", result.stderr)

    def test_unknown_profile_rejected(self):
        self.assertNotEqual(self.invoke(profile="UNKNOWN").returncode, 0)

    def test_bad_job_count_rejected(self):
        self.assertNotEqual(self.invoke(jobs="0").returncode, 0)

    def test_invalid_source_rejected(self):
        result = subprocess.run(["bash", str(SCRIPT), str(self.root), str(self.root / "artifacts")], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

if __name__ == "__main__":
    unittest.main()
