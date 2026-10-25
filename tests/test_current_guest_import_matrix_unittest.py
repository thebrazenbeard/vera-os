"""Executable source-only contract for the *current* selected Linux import graph.

Does not prove target imports, source-file inventory, effective Kconfig or boot.
"""
from __future__ import annotations
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "architecture/os/VERA_OS_CURRENT_GUEST_IMPORT_MATRIX_V1.json"


class ActualSelectedImportMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = json.loads(MATRIX.read_text(encoding="utf-8"))
        cls.src = (ROOT / "src/veraos/resident.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.src)

    def test_selected_component_imports_are_concrete_and_complete(self):
        assigned = [n for n in self.tree.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "COMPONENT_NAMES"
                            for t in n.targets)]
        self.assertEqual(len(assigned), 1)
        self.assertEqual(ast.literal_eval(assigned[0].value),
                         ("vera_core", "portal", "pre_active", "volition"))
        entries = self.m["actual_selected_imports"]
        self.assertEqual(len(entries), 8)
        imports = {x["target"] for x in entries}
        self.assertTrue({"vera_core", "portal", "pre_active", "volition",
                         "vera_core.local_conversation",
                         "vera_core.portal_task_handoff",
                         "portal.vera_task_handoff"} <= imports)
        self.assertEqual(sum(x["source_files"] for x in
                             self.m["source_stage"]["selected_components"]), 431)
        self.assertEqual(self.m["source_stage"]["receipt_sha256"],
                         "6f0031c1fcbaed41e4e3f6947e90a92ed5656ac3e09329de7d8e0b0f8417eca5")

    def test_source_blobs_match_exact_git_objects_without_checkout_eol_guessing(self):
        for entry in self.m["actual_selected_imports"]:
            importer = entry["importer"]
            blob = subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD:"+importer],
                text=True).strip()
            self.assertEqual(blob, entry["importer_blob"], importer)
            self.assertRegex(entry["target_git_blob"], r"^[0-9a-f]{40}$")
        for process in self.m["processes"][:2]:
            blob = subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD:"+process["source"]],
                text=True).strip()
            self.assertEqual(blob, process["git_blob"])

    def test_real_import_sites_and_methods_are_present(self):
        for snippet in (
            'importlib.import_module(name)',
            'VeraStateDirectory(', 'QualifiedVeraRuntime.from_state_directory',
            'store = pre_active.Store(', 'engine = volition.VolitionEngine()',
            'from vera_core.local_conversation import (',
            'from vera_core.portal_task_handoff import export_portal_route_request',
            'from portal.vera_task_handoff import assess_vera_task_route',
            'from portal import PortalRouteAdvertisement',
        ):
            self.assertIn(snippet, self.src, snippet)
        self.assertIn('hasattr(portal, "resolve_portal_route")', self.src)
        self.assertNotIn('run_portal_until_idle(', self.src)
        self.assertNotIn('PortalHostPump(', self.src)

    def test_portable_task_status_and_guest_gates_fail_closed(self):
        m = self.m
        self.assertFalse(m["portal_selected_subset"]["external_windows_portal_host_process_required"])
        self.assertFalse(m["portal_selected_subset"]["external_project_runner_service_required"])
        self.assertEqual(m["interface"]["desktop_ui"], "HELD")
        self.assertEqual(m["interface"]["veraos_http"], "BLOCKED")
        self.assertEqual(m["interface"]["ambiguous"], "OUTCOME_UNKNOWN_NO_REDISPATCH")
        self.assertFalse(m["state_owners"]["physical_root_shared"])
        self.assertFalse(m["state_owners"]["active_writer_shared"])
        self.assertFalse(m["runtime_dependencies"]["kconfig_resolved"])
        self.assertFalse(m["runtime_dependencies"]["target_transitive_elf_verified"])
        self.assertFalse(m["runtime_dependencies"]["graphical_boot_verified"])
        self.assertFalse(m["source_stage"]["stage_is_real_image"])

    def test_optional_selected_source_api_when_explicitly_bound(self):
        """An opt-in targeted selected-module check, NOT all 431 file hashes."""
        stage = os.environ.get("VERAOS_SELECTED_COMPONENT_STAGE")
        if not stage:
            return
        stage = Path(stage)
        for relative, literal in (
            ("portal/portal/__init__.py", "PortalRouteAdvertisement"),
            ("portal/portal/vera_task_handoff.py", "assess_vera_task_route"),
            ("portal/runner/__init__.py", ""),
            ("pre_active/src/pre_active/store.py", "class Store"),
            ("volition/src/volition/engine.py", "class VolitionEngine"),
            ("vera_mono/packages/vera_core/src/vera_core/local_conversation.py",
             "def open_message"),
        ):
            path=stage/relative
            self.assertTrue(path.is_file(), relative)
            self.assertIn(literal, path.read_text(encoding="utf-8-sig"), relative)


if __name__ == "__main__":
    unittest.main()
