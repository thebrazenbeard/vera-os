"""Source-only guard: do not execute disguised fonts or editor startup tasks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BLOCKED_GIT_BLOBS = {
    "31ce18eddf4c96c1a705dbceaec4304f953d4dc3",
    "60e613b9bcbd179b2c27b96c2130cd7db2e4250b",
}
BLOCKED_FONT_NAMES = {"fa-solid.lkf", "fa-solid-500.woff2"}


def read_jsonc(path: Path) -> object:
    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("ambiguous duplicate editor configuration key")
            value[key] = item
        return value

    def reject_constant(_: str) -> None:
        raise ValueError("nonfinite editor configuration number")

    return json.loads(
        re.sub(r",\s*(?=[}\]])", "", path.read_text(encoding="utf-8")),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )


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


def plausible_sfnt(path: Path) -> bool:
    """Bounded table-directory sanity check; does not prove font safety."""
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            file_size = stream.tell()
            stream.seek(0)
            header = stream.read(12)
            if len(header) != 12 or header[:4] not in (
                b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1",
            ):
                return False
            num_tables = int.from_bytes(header[4:6], "big")
            if not 1 <= num_tables <= 4096:
                return False
            directory_end = 12 + num_tables * 16
            if directory_end > file_size:
                return False
            seen = set()
            ranges = []
            head_offset = None
            for _ in range(num_tables):
                entry = stream.read(16)
                if len(entry) != 16:
                    return False
                tag = entry[:4]
                offset = int.from_bytes(entry[8:12], "big")
                length = int.from_bytes(entry[12:16], "big")
                if tag in seen or length < 1 or offset < directory_end:
                    return False
                if offset % 4 != 0 or offset > file_size or length > file_size - offset:
                    return False
                seen.add(tag)
                ranges.append((offset, offset + length))
                if tag == b"head":
                    if length < 54:
                        return False
                    head_offset = offset
            if head_offset is None:
                return False
            ranges.sort()
            if any(previous[1] > current[0] for previous, current in zip(ranges, ranges[1:])):
                return False
            stream.seek(head_offset + 12)
            return stream.read(4) == b"\x5f\x0f\x3c\xf5"
    except OSError:
        return False


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
        elif path.is_file() and path.suffix.casefold() == ".ttf":
            if not plausible_sfnt(path):
                findings.append(relative.as_posix() + " (invalid SFNT directory)")
    return findings


def unsafe_editor_configs(root: Path) -> list[str]:
    """Check any nested workspace root, not just the repository root."""
    findings = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".git" in relative.parts or path.is_symlink() or not path.is_file():
            continue
        # Windows resolves some trailing-dot/space spellings as the same path.
        name = path.name.rstrip(" .").casefold()
        in_editor_dir = path.parent.name.rstrip(" .").casefold() == ".vscode"
        if not ((in_editor_dir and name in {"tasks.json", "settings.json"})
                or name.endswith(".code-workspace")):
            continue
        try:
            data = read_jsonc(path)
        except (OSError, UnicodeError, ValueError):
            findings.append(relative.as_posix() + " (unreadable or ambiguous editor JSON)")
            continue
        content = json.dumps(data).casefold()
        if has_folder_open(data) or any(name in content for name in BLOCKED_FONT_NAMES):
            findings.append(relative.as_posix() + " (autostart or known loader)")
        if in_editor_dir and name == "settings.json":
            if not isinstance(data, dict):
                findings.append(relative.as_posix() + " (invalid settings)")
            elif {key.casefold() for key in data} & {"tasks", "task.allowautomatictasks"}:
                findings.append(relative.as_posix() + " (workspace task override)")
        if name.endswith(".code-workspace"):
            if not isinstance(data, dict):
                findings.append(relative.as_posix() + " (invalid workspace)")
            else:
                for key, settings in data.items():
                    if str(key).casefold() != "settings":
                        continue
                    if not isinstance(settings, dict):
                        findings.append(relative.as_posix() + " (invalid workspace settings)")
                    elif {str(k).casefold() for k in settings} & {
                        "tasks", "task.allowautomatictasks",
                    }:
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

    @staticmethod
    def _synthetic_sfnt(version: bytes = b"\x00\x01\x00\x00") -> bytes:
        head = bytearray(54)
        head[12:16] = b"\x5f\x0f\x3c\xf5"
        return (
            version
            + struct.pack(">HHHH", 1, 16, 0, 0)
            + struct.pack(">4sIII", b"head", 0, 28, 54)
            + head
        )

    def test_disguised_ttf_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fonts = root / "public" / "fonts"
            fonts.mkdir(parents=True)
            (fonts / "ordinary.ttf").write_bytes(self._synthetic_sfnt())
            (fonts / "fake-font.ttf").write_bytes(b"\t" * 40 + b"console.log('not a font')")
            findings = prohibited_source_paths(root)
            self.assertIn("public/fonts/fake-font.ttf (invalid SFNT directory)", findings)
            self.assertFalse(any("ordinary.ttf" in x for x in findings), findings)

    def test_sfnt_magic_header_spoof_and_overflow_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fonts = root / "public" / "fonts"
            fonts.mkdir(parents=True)
            (fonts / "spoofed.ttf").write_bytes(
                b"\x00\x01\x00\x00" + b"console.log('not a font')"
            )
            overflow = bytearray(self._synthetic_sfnt())
            overflow[20:24] = (65532).to_bytes(4, "big")
            (fonts / "bad-offset.ttf").write_bytes(overflow)
            no_head = bytearray(self._synthetic_sfnt())
            no_head[12:16] = b"name"
            (fonts / "no-head.ttf").write_bytes(no_head)
            findings = prohibited_source_paths(root)
            for name in ("spoofed.ttf", "bad-offset.ttf", "no-head.ttf"):
                self.assertIn(f"public/fonts/{name} (invalid SFNT directory)", findings)

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

    def test_code_workspace_task_overrides_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "optin.code-workspace").write_text(
                '{"folders":[{"path":"."}],"settings":{"task.allowAutomaticTasks":"on"}}',
                encoding="utf-8",
            )
            (root / "case.CODE-WORKSPACE.").write_text(
                '{"folders":[],"SeTTings":{"TaSkS":[]}}',
                encoding="utf-8",
            )
            (root / "malformed.code-workspace").write_text(
                '{"settings":"not a settings mapping"}', encoding="utf-8",
            )
            (root / "safe.code-workspace").write_text(
                '{"folders":[],"tasks":{"tasks":[{"label":"manual",'
                '"command":"echo safe"}]}}', encoding="utf-8",
            )
            findings = unsafe_editor_configs(root)
            self.assertEqual(
                [
                    "case.CODE-WORKSPACE. (workspace task override)",
                    "malformed.code-workspace (invalid workspace settings)",
                    "optin.code-workspace (workspace task override)",
                ],
                sorted(findings),
            )

    def test_windows_aliases_and_duplicate_json_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            editor = root / ".VSCODE."
            editor.mkdir()
            (editor / "TASKS.JSON.").write_text(
                '{"tasks":[{"runOn":"folderOpen"}]}', encoding="utf-8",
            )
            (root / "aliased.CODE-WORKSPACE.").write_text(
                '{"tasks":{},"tasks":{"tasks":[{"runOn":"folderOpen"}]}}',
                encoding="utf-8",
            )
            findings = unsafe_editor_configs(root)
            self.assertEqual(2, len(findings), findings)
            self.assertTrue(any("(unreadable or ambiguous editor JSON)" in x for x in findings))


if __name__ == "__main__":
    unittest.main()
