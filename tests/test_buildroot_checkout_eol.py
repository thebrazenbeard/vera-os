"""Prove git checkout preserves required Buildroot parser bytes under CRLF policy."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ATTRS = (ROOT / ".gitattributes").read_text(encoding="utf-8")
BASELINE = ATTRS.split("# GNU make", 1)[0]
PARSER_FILES = (
    "buildroot/external.desc",
    "buildroot/external.mk",
    "buildroot/Config.in",
    "buildroot/configs/veraos_x86_64_defconfig",
    "buildroot/configs/veraos_x86_64_browser_defconfig",
    "buildroot/configs/veraos_x86_64_resident_browser_defconfig",
    "buildroot/BUILDROOT_VERSION",
)
PREVIOUSLY_PINNED = (
    "buildroot/board/veraos/x86_64/post-build.sh",
    "buildroot/board/veraos/patches/cog/0001-drm.patch",
    "buildroot/board/veraos/x86_64/rootfs-overlay/sbin/vera-init",
)


def checkout_test_repo(root: Path, attrs: str):
    def git(*args: str):
        result = subprocess.run(["git", *args], cwd=root, text=True,
                                capture_output=True, check=False)
        if result.returncode:
            raise AssertionError(f"git {args}: {result.stderr}")
        return result.stdout

    git("init", "-q")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "EOL Test")
    git("config", "core.autocrlf", "true")
    (root / ".gitattributes").write_text(attrs, encoding="utf-8")
    for path in (*PARSER_FILES, *PREVIOUSLY_PINNED):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = (b"name: VERAOS\ndesc: VeraOS research\n"
                   if path == "buildroot/external.desc"
                   else b"first-line\nsecond-line\n")
        target.write_bytes(payload)
    git("add", ".")
    git("commit", "-q", "-m", "synthetic parser fixtures")
    # Force a true index -> worktree checkout, not a recheck of already-LF
    # fixture files created before Git populated the index.
    for path in (*PARSER_FILES, *PREVIOUSLY_PINNED):
        (root / path).unlink()
    git("checkout-index", "-a", "-f")
    return git


class BuildrootEolTests(unittest.TestCase):
    def test_previous_attributes_reproduce_crlf_external_descriptor(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkout_test_repo(root, BASELINE)
            desc = (root / "buildroot/external.desc").read_bytes()
            self.assertIn(b"\r\n", desc)
            self.assertEqual(b"VERAOS\r", desc.split(b"\n", 1)[0].split(b": ", 1)[1])

    def test_candidate_attributes_force_lf_for_all_parser_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            git = checkout_test_repo(root, ATTRS)
            for path in (*PARSER_FILES, *PREVIOUSLY_PINNED):
                with self.subTest(path=path):
                    data = (root / path).read_bytes()
                    expected = (b"name: VERAOS\ndesc: VeraOS research\n"
                                if path == "buildroot/external.desc"
                                else b"first-line\nsecond-line\n")
                    self.assertEqual(expected, data)
                    self.assertNotIn(b"\r", data)
                    self.assertIn("w/lf", git("ls-files", "--eol", "--", path))


if __name__ == "__main__":
    unittest.main()
