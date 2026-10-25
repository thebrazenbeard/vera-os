"""Ensure Buildroot emits the .py files that resident post-build checks require."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEFCONFIG = ROOT / "buildroot/configs/veraos_x86_64_resident_browser_defconfig"
BUILDER = ROOT / "tools/vm/Build-VeraOSVm.ps1"
PROBE = ROOT / "tools/vm/Probe-ResidentTargetRootfs.py"


class PythonSourcePackagingTests(unittest.TestCase):
    def test_python_sources_and_bytecode_are_explicitly_selected(self):
        text = DEFCONFIG.read_text(encoding="utf-8")
        self.assertIn("BR2_PACKAGE_PYTHON3=y", text)
        self.assertIn("BR2_PACKAGE_PYTHON3_PY_PYC=y", text.splitlines())
        self.assertNotIn("BR2_PACKAGE_PYTHON3_PYC_ONLY=y", text.splitlines())

    def test_prebuild_guard_runs_before_docker_or_artifact_write(self):
        text = BUILDER.read_text(encoding="utf-8")
        start = text.index("Resident Buildroot requires .py and .pyc")
        self.assertLess(start, text.index("& docker build"))
        self.assertLess(start, text.index("New-Item -ItemType Directory -Force $artifacts"))

    def test_postbuild_checks_source_files_not_just_ambient_host_python(self):
        text = PROBE.read_text(encoding="utf-8")
        self.assertIn('require("/usr/lib/python3.12/" + name)', text)
        self.assertIn('package + "/__init__.py"', text)


if __name__ == "__main__":
    unittest.main()
