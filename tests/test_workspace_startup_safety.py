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

    def test_known_disguised_executable_blobs_absent(self):
        self.assertFalse((ROOT / "public/fonts/fa-solid-500.woff2").exists())
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
