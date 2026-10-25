"""Source-only guard: do not execute disguised fonts or editor startup tasks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BLOCKED_GIT_BLOBS = {
    "31ce18eddf4c96c1a705dbceaec4304f953d4dc3",
    "60e613b9bcbd179b2c27b96c2130cd7db2e4250b",
}
BLOCKED_FONT_NAMES = {"fa-solid.lkf", "fa-solid-500.woff2"}


def read_jsonc(path: Path) -> object:
    return json.loads(re.sub(r",\s*(?=[}\]])", "", path.read_text(encoding="utf-8")))


def has_folder_open(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).casefold() == "runon" and str(item).casefold() == "folderopen"
            for key, item in value.items()
        ) or any(has_folder_open(item) for item in value.values())
    if isinstance(value, list):
        return any(has_folder_open(item) for item in value)
    return False


def git_blob_digest(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def prohibited_source_paths(root: Path) -> list[str]:
    """Find known filename aliases and symlinks, including ancestor aliases."""
    findings = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        if path.name.rstrip(" .").casefold() in BLOCKED_FONT_NAMES:
            findings.append(relative.as_posix())
        elif path.is_symlink():
            findings.append(relative.as_posix() + " (symlink)")
    return findings


def unsafe_editor_configs(root: Path) -> list[str]:
    """Check any nested workspace root, not just the repository root."""
    findings = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".git" in relative.parts or path.is_symlink() or not path.is_file():
            continue
        name = path.name.casefold()
        in_editor_dir = path.parent.name.casefold() == ".vscode"
        if not ((in_editor_dir and name in {"tasks.json", "settings.json"})
                or name.endswith(".code-workspace")):
            continue
        data = read_jsonc(path)
        content = json.dumps(data).casefold()
        if has_folder_open(data) or any(name in content for name in BLOCKED_FONT_NAMES):
            findings.append(relative.as_posix() + " (autostart or known loader)")
        if in_editor_dir and name == "settings.json":
            if not isinstance(data, dict):
                findings.append(relative.as_posix() + " (invalid settings)")
            elif {key.casefold() for key in data} & {"tasks", "task.allowautomatictasks"}:
                findings.append(relative.as_posix() + " (workspace task override)")
    return findings


class WorkspaceStartupSafetyTests(unittest.TestCase):
    def test_no_automatic_editor_task(self):
        self.assertTrue((ROOT / ".vscode" / "tasks.json").is_file())
        self.assertEqual([], unsafe_editor_configs(ROOT))

    def test_no_workspace_override_or_embedded_task(self):
        self.assertTrue((ROOT / ".vscode" / "settings.json").is_file())
        self.assertEqual([], unsafe_editor_configs(ROOT))

    def test_known_disguised_executable_blobs_absent(self):
        self.assertEqual([], prohibited_source_paths(ROOT))
        for path in ROOT.rglob("*"):
            if ".git" in path.parts or not path.is_file() or path.is_symlink():
                continue
            if path.stat().st_size in (12797, 27410):
                self.assertNotIn(
                    git_blob_digest(path.read_bytes()), BLOCKED_GIT_BLOBS, str(path)
                )
            if path.suffix.casefold() == ".woff2":
                with path.open("rb") as stream:
                    self.assertEqual(b"wOF2", stream.read(4), str(path))

    def test_case_and_symlink_aliases_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fonts = root / "public" / "fonts"
            fonts.mkdir(parents=True)
            (fonts / "FA-SOLID-500.WOFF2").write_bytes(b"not a font")
            (fonts / "Fa-Solid.LkF.").write_bytes(b"not a font")
            dangling = fonts / "ordinary.woff2"
            dangling.symlink_to("missing-target")
            (root / "ancestor-link").symlink_to(fonts, target_is_directory=True)
            findings = prohibited_source_paths(root)
            self.assertEqual(4, len(findings), findings)
            self.assertTrue(any("ordinary.woff2 (symlink)" in item for item in findings))
            self.assertTrue(any("ancestor-link (symlink)" in item for item in findings))

    def test_nested_workspace_autostart_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            editor = root / "nested" / ".VSCODE"
            editor.mkdir(parents=True)
            (editor / "TASKS.JSON").write_text(
                '{"tasks":[{"runOn":"folderOpen","command":"echo unsafe"}]}',
                encoding="utf-8",
            )
            (root / "nested" / "other.code-workspace").write_text(
                '{"tasks":{"tasks":[{"runOn":"folderOpen"}]}}',
                encoding="utf-8",
            )
            findings = unsafe_editor_configs(root)
            self.assertEqual(2, len(findings), findings)


if __name__ == "__main__":
    unittest.main()
