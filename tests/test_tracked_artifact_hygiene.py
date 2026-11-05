"""Guard against accidentally committing local credentials or runtime artifacts.

This is a source-index check, not a secret scanner or an OS access control.
In particular, it does not inspect untracked files, Git history, file contents,
remote storage, or the operator's Windows/WSL home directories.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SENSITIVE_SUFFIXES = (
    ".gguf", ".safetensors", ".ckpt", ".pt", ".pth",
    ".sqlite", ".sqlite3", ".sqlite-wal", ".sqlite-shm",
    ".sqlite3-wal", ".sqlite3-shm", ".db", ".db-wal", ".db-shm",
    ".vhdx", ".qcow2", ".vdi", ".vmdk", ".ext2", ".iso",
)


def sensitive_artifact_kind(path: str) -> str | None:
    """Classify only known dangerous artifact *names*, not their contents."""
    if not path or "\0" in path:
        return "invalid_path"
    name = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if name == ".env" or name.startswith(".env."):
        if (name.endswith(".example") or name.endswith(".sample")
                or name in (".env.example", ".env.sample")):
            return None
        return "operator_env"
    if name.endswith(SENSITIVE_SUFFIXES):
        return "local_state_or_model"
    return None


class TrackedArtifactHygieneTests(unittest.TestCase):
    def test_known_private_artifacts_are_classified(self):
        for path in (
            ".env", ".env.production", "deploy/.env.dev", "model.gguf",
            "weights.safetensors", "local.sqlite3-wal", "state.db-shm",
            "disk.vhdx", "vm/image.qcow2", "resident.iso",
        ):
            with self.subTest(path=path):
                self.assertIsNotNone(sensitive_artifact_kind(path))

    def test_source_and_operator_templates_are_not_false_positives(self):
        for path in (
            "README.md", "src/veraos/wsl_pilot.py", "tests/test_model_admission.py",
            ".env.example", ".env.sample", "env/.env.dev.example",
            "docs/00-vision-and-scope.md", "artifacts/sha256-manifest.json",
        ):
            with self.subTest(path=path):
                self.assertIsNone(sensitive_artifact_kind(path))

    def test_git_index_has_no_local_artifacts_or_environment_credentials(self):
        result = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            self.skipTest("Git index unavailable; source archive cannot qualify index hygiene")
        entries = [n.decode("utf-8", errors="surrogateescape")
                   for n in result.stdout.split(b"\0") if n]
        violations = [(name, sensitive_artifact_kind(name)) for name in entries
                      if sensitive_artifact_kind(name) is not None]
        self.assertEqual(violations, [], "tracked local artifacts must be removed by reviewed change")

    def test_gitignore_excludes_local_artifacts_but_keeps_templates(self):
        for path in ("test.gguf", "runtime/test.sqlite3", "vm/disk.vhdx", ".env.local"):
            result = subprocess.run(["git", "check-ignore", "--no-index", "-q", path],
                                    cwd=ROOT, check=False, capture_output=True)
            with self.subTest(ignored=path):
                self.assertEqual(result.returncode, 0)
        for path in (".env.example", ".env.dev.sample", "src/veraos/new_module.py"):
            result = subprocess.run(["git", "check-ignore", "--no-index", "-q", path],
                                    cwd=ROOT, check=False, capture_output=True)
            with self.subTest(trackable=path):
                self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
