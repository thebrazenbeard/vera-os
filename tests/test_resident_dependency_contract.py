"""Synthetic source-only tests; no model or historical component code executes."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools/vm/Verify-ResidentDependencies.py"
SPEC = importlib.util.spec_from_file_location("resident_dependencies", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResidentDependencySourceTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.stage = Path(self.scratch.name)
        for path, symbols in MODULE.CONTRACT.items():
            target = self.stage / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("\n".join(f"def {name}(): pass" for name in symbols), encoding="utf-8")

    def test_matching_sources_are_not_guest_or_model_qualification(self):
        result = MODULE.verify(self.stage)
        self.assertEqual(result["status"], "SOURCE_CONTRACT_CANDIDATE")
        self.assertEqual(result["defects"], [])
        for flag in ("guest_import_qualified", "installed", "model_admitted", "authority_granted"):
            self.assertIs(result[flag], False)

    def test_fabricated_model_pass_file_cannot_change_gate_or_admission(self):
        forged = self.stage / "provider-pass.json"
        forged.write_text(json.dumps({"issuer": "forged", "qualification": "PASS"}))
        result = MODULE.verify(self.stage)
        self.assertEqual(result["status"], "SOURCE_CONTRACT_CANDIDATE")
        self.assertIs(result["model_admitted"], False)
        self.assertIs(result["authority_granted"], False)

    def test_missing_mono_conversation_is_held(self):
        (self.stage / "vera_mono/packages/vera_core/src/vera_core/local_conversation.py").unlink()
        result = MODULE.verify(self.stage)
        self.assertEqual(result["status"], "HELD_SOURCE_CONTRACT")
        self.assertIn("local_conversation.py: required source missing", " ".join(result["defects"]))

    def test_missing_portal_handoff_symbol_is_held(self):
        path = self.stage / "portal/portal/vera_task_handoff.py"
        path.write_text("def unrelated(): pass\n", encoding="utf-8")
        result = MODULE.verify(self.stage)
        self.assertEqual(result["status"], "HELD_SOURCE_CONTRACT")
        self.assertIn("missing exported or defined assess_vera_task_route", " ".join(result["defects"]))

    def test_unparseable_or_oversized_source_is_held(self):
        path = self.stage / "portal/portal/vera_task_handoff.py"
        path.write_text("def bad(:\n", encoding="utf-8")
        self.assertIn("unparseable Python", " ".join(MODULE.verify(self.stage)["defects"]))
        path.write_bytes(b"#" * (MODULE.MAX_SOURCE_BYTES + 1))
        self.assertIn("exceeds 1 MiB", " ".join(MODULE.verify(self.stage)["defects"]))

    def test_symlinked_package_source_is_held(self):
        path = self.stage / "portal/portal/vera_task_handoff.py"
        target = self.stage / "other.py"
        target.write_text("def assess_vera_task_route(): pass\n", encoding="utf-8")
        path.unlink()
        try:
            path.symlink_to(target)
        except (NotImplementedError, OSError):
            self.skipTest("symlinks not available")
        self.assertIn("symlink not allowed", " ".join(MODULE.verify(self.stage)["defects"]))

    def test_cli_exits_two_on_missing_source(self):
        (self.stage / "vera_mono/packages/vera_core/src/vera_core/portal_task_handoff.py").unlink()
        run = subprocess.run(
            [sys.executable, str(SCRIPT), "--components-root", str(self.stage)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(run.returncode, 2)
        self.assertEqual(json.loads(run.stdout)["status"], "HELD_SOURCE_CONTRACT")


    def test_selected_postbuild_enforces_dependency_gate(self):
        postbuild = (SCRIPT.parents[2] / "buildroot/board/veraos/x86_64/post-build.sh").read_text()
        self.assertIn("Verify-ResidentDependencies.py", postbuild)
        self.assertLess(postbuild.index("Stage-VeraOSResidentSources.py"),
                        postbuild.index("Verify-ResidentDependencies.py"))


if __name__ == "__main__":
    unittest.main()
