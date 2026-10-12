"""Tests for pinned Git-tree resident code staging and exact output custody."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "resident_stager",
    Path(__file__).with_name("Stage-VeraOSResidentSources.py"),
)
stager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stager)


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], stderr=subprocess.STDOUT, text=True
    ).strip()


class ResidentStageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.checkouts = self.root / "checkouts"
        self.checkouts.mkdir()
        self.source_root = self.root / "os-source"
        (self.source_root / "architecture/portfolio").mkdir(parents=True)
        self.output = self.root / "output" / "stage"
        self.pinned = {}
        for component, (repository, subdirs) in stager.COMPONENTS.items():
            repo = self.checkouts / component
            repo.mkdir()
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "build-test@example.invalid")
            git(repo, "config", "user.name", "Build Test")
            git(repo, "config", "core.autocrlf", "false")
            for rel in subdirs:
                root = repo / rel
                root.mkdir(parents=True)
                (root / "module.py").write_bytes(b"committed module\n")
            if component == "vera_mono":
                marker = repo/"packages/vera_core/src/vera_core/__init__.py"
            elif component == "portal":
                marker = repo/"portal/__init__.py"
            else:
                marker = repo/f"src/{component}/__init__.py"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_bytes(b"committed marker\n")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "frozen source")
            (repo / ".private-untracked").write_text("NOT FOR STAGE")
            self.pinned[repository] = git(repo, "rev-parse", "HEAD")
        composition = {
            "repositories": [
                {"repository": repo, "exact_head": head, "boot_policy": "CORE"}
                for repo, head in self.pinned.items()
            ]
        }
        plan = {
            "repositories": [
                {"repository": repo, "exact_head": head, "activation_policy": "CORE"}
                for repo, head in self.pinned.items()
            ]
        }
        (self.source_root / "architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json").write_text(json.dumps(composition))
        (self.source_root / "architecture/portfolio/VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json").write_text(json.dumps(plan))

    def stage(self):
        return stager.stage(self.checkouts, self.output, self.source_root)

    def test_exact_pinned_sources_are_staged_and_verified(self):
        result = self.stage()
        self.assertEqual(len(result["components"]), 4)
        self.assertFalse(result["installed"])
        verified = stager.verify_stage(self.output, self.source_root)
        self.assertEqual(verified["status"], "PINNED_SOURCE_FILES_VERIFIED_NOT_INSTALLED")
        self.assertEqual(verified["component_count"], 4)
        self.assertFalse(verified["guest_import_qualified"])
        self.assertFalse(verified["protected_effect_authority"])
        self.assertEqual(result["receipt_sha256"], verified["receipt_sha256"])

    def test_untracked_private_and_changed_worktree_are_not_packaged(self):
        repo = self.checkouts / "portal"
        (repo / "portal/__init__.py").write_bytes(b"uncommitted mutation\n")
        result = self.stage()
        self.assertEqual(
            (self.output/"components/portal/portal/__init__.py").read_bytes(),
            b"committed marker\n",
        )
        self.assertEqual(result["source_material"], "EXACT_COMMITTED_GIT_TREE_IGNORE_MUTABLE_WORKTREE")
        self.assertFalse(any(x.name == ".private-untracked" for x in self.output.rglob("*")))

    def test_wrong_source_head_rejected(self):
        path = self.source_root/"architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json"
        manifest = json.loads(path.read_text())
        manifest["repositories"][0]["exact_head"] = "0"*40
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(stager.StageError, "Exact source head mismatch"):
            self.stage()

    def test_existing_output_not_overwritten(self):
        self.output.mkdir(parents=True)
        sentry = self.output/"owner-file"
        sentry.write_text("keep")
        with self.assertRaisesRegex(stager.StageError, "must not exist"):
            self.stage()
        self.assertEqual(sentry.read_text(), "keep")

    def test_modified_staged_bytes_fail_reverification(self):
        self.stage()
        marker = self.output / "components/portal/portal/__init__.py"
        marker.write_bytes(b"changed")
        with self.assertRaisesRegex(stager.StageError, "modified"):
            stager.verify_stage(self.output, self.source_root)

    def test_extra_staged_file_fails_reverification(self):
        self.stage()
        (self.output/"components/portal/extra.py").write_bytes(b"unlisted")
        with self.assertRaisesRegex(stager.StageError, "inventory mismatch"):
            stager.verify_stage(self.output, self.source_root)

    def test_unbound_receipt_head_fails_reverification(self):
        self.stage()
        receipt_path = self.output/"VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["components"][0]["source_head"] = "f"*40
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(stager.StageError, "head mismatch"):
            stager.verify_stage(self.output, self.source_root)


if __name__ == "__main__":
    unittest.main()
