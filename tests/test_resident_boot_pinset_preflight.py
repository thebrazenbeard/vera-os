"""Fail-fast source pinset gate: no Docker, Buildroot, or guest invocation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools/vm/Assert-VeraOSPortfolioPinset.ps1"
BUILDER = ROOT / "tools/vm/Build-VeraOSVm.ps1"
PATHS = (
    "architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json",
    "architecture/capabilities/VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json",
    "architecture/portfolio/VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json",
)


class PinsetPreflightTests(unittest.TestCase):
    def test_build_guard_runs_before_docker_and_artifact_creation(self):
        source = BUILDER.read_text(encoding="utf-8")
        guard = source.index("Assert-VeraOSPortfolioPinset.ps1")
        self.assertLess(guard, source.index("New-Item -ItemType Directory -Force $artifacts"))
        self.assertLess(guard, source.index("& docker build"))
        self.assertIn('if ($Profile -eq "RESIDENT_BROWSER")', source[:guard])
    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"),
                         "native Windows PowerShell needed for direct execution")
    def test_complete_and_hostile_manifest_sets(self):
        with tempfile.TemporaryDirectory(prefix="veraos-pinset-") as directory:
            repo = Path(directory)
            records = [
                {"repository": "thebrazenbeard/portal", "exact_head": "a" * 40},
                {"repository": "thebrazenbeard/vera-mono", "exact_head": "b" * 40},
            ]

            def write(index, values):
                target = repo / PATHS[index]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({"repositories": values}), encoding="utf-8")

            def run():
                return subprocess.run([
                    "powershell.exe", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", "-File", str(CHECKER),
                    "-RepoRoot", str(repo),
                ], capture_output=True, text=True, timeout=25)

            for i in range(3):
                write(i, records)
            passed = run()
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertIn("VERAOS_BOOT_PINSET_ALIGNED_V1 repositories=2", passed.stdout)
            hostile = [
                ([records[0], {**records[1], "exact_head": "c" * 40}],
                 "exact-head mismatch"),
                ([records[0]], "inventory count mismatch"),
                (records + [records[0]], "Duplicate"),
                ([records[0], {**records[1], "exact_head": "not-a-sha"}],
                 "Invalid"),
            ]
            for modified, reason in hostile:
                with self.subTest(reason=reason):
                    write(1, modified)
                    held = run()
                    self.assertNotEqual(held.returncode, 0)
                    self.assertIn(reason.lower(), held.stderr.lower())
                    write(1, records)

            (repo / PATHS[2]).unlink()
            held = run()
            self.assertNotEqual(held.returncode, 0)
            self.assertIn("Missing resident boot source manifest", held.stderr)


if __name__ == "__main__":
    unittest.main()
