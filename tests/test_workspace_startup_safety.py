"""Source-only guard: do not execute disguised fonts or editor startup tasks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
BLOCKED_GIT_BLOBS = {
    "31ce18eddf4c96c1a705dbceaec4304f953d4dc3",
    "60e613b9bcbd179b2c27b96c2130cd7db2e4250b",
}


def read_jsonc(path: Path) -> object:
    return json.loads(re.sub(r",\s*(?=[}\]])", "", path.read_text(encoding="utf-8")))


def has_folder_open(value: object) -> bool:
    if isinstance(value, dict):
        return value.get("runOn") == "folderOpen" or any(
            has_folder_open(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(has_folder_open(item) for item in value)
    return False


def git_blob_digest(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def workspace_startup_risks(path: Path) -> tuple[str, ...]:
    """Inspect VS Code workspace settings without executing any referenced code."""
    workspace = read_jsonc(path)
    risks: list[str] = []
    if has_folder_open(workspace):
        risks.append("folderOpen task")
    if any(name in json.dumps(workspace) for name in ("fa-solid.lkf", "fa-solid-500.woff2")):
        risks.append("disguised executable reference")
    if isinstance(workspace, dict):
        settings = workspace.get("settings")
        if isinstance(settings, dict) and "task.allowAutomaticTasks" in settings:
            risks.append("automatic-task consent override")
    return tuple(risks)


class WorkspaceStartupSafetyTests(unittest.TestCase):
    def test_no_automatic_editor_task(self):
        tasks = read_jsonc(ROOT / ".vscode" / "tasks.json")
        self.assertFalse(has_folder_open(tasks))
        for name in ("fa-solid.lkf", "fa-solid-500.woff2"):
            self.assertNotIn(name, json.dumps(tasks))

    def test_no_workspace_override_or_embedded_task(self):
        settings = read_jsonc(ROOT / ".vscode" / "settings.json")
        self.assertIsInstance(settings, dict)
        self.assertNotIn("task.allowAutomaticTasks", settings)
        self.assertNotIn("tasks", settings)

    def test_workspace_files_reject_automatic_tasks(self):
        for path in ROOT.rglob("*.code-workspace"):
            if ".git" in path.parts or not path.is_file():
                continue
            self.assertEqual(workspace_startup_risks(path), (), str(path))

    def test_workspace_guard_detects_nested_autorun_fixture(self):
        import tempfile

        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "unsafe.code-workspace"
            path.write_text(
                json.dumps({"folders": [], "tasks": {"tasks": [
                    {"runOptions": {"runOn": "folderOpen"},
                     "command": "node ./public/fonts/fa-solid.lkf"}
                ]}}),
                encoding="utf-8",
            )
            risks = workspace_startup_risks(path)
            self.assertIn("folderOpen task", risks)
            self.assertIn("disguised executable reference", risks)

    def test_known_disguised_executable_blobs_absent(self):
        for known_path in ("public/fonts/fa-solid-500.woff2", "public/fonts/fa-solid.lkf"):
            self.assertFalse((ROOT / known_path).exists(), known_path)
        for path in ROOT.rglob("*"):
            if ".git" in path.parts or not path.is_file():
                continue
            if path.stat().st_size not in (12797, 27410):
                continue
            self.assertNotIn(
                git_blob_digest(path.read_bytes()), BLOCKED_GIT_BLOBS, str(path)
            )


if __name__ == "__main__":
    unittest.main()
