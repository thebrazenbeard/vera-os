"""Exercise the Windows wrapper's literal POSIX build recipe in isolation."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "tools" / "vm" / "Build-VeraOSVm.ps1").read_text(encoding="utf-8")
RECIPE = SOURCE.split("$script = @'\n", 1)[1].split("\n'@", 1)[0]
HEAD = "10dfe758479573468b091cd260c57e8d65cc6942"


class FreshOutputTests(unittest.TestCase):
    def test_emitted_shell_recipe_has_valid_posix_syntax(self):
        result = subprocess.run(["sh", "-n"], input=RECIPE, text=True,
                                capture_output=True, check=False)
        self.assertEqual(0, result.returncode, result.stderr)

    def _run_output_gate(self, parent: Path, head: str) -> subprocess.CompletedProcess:
        # Extract the real guard rather than writing a mock implementation.
        begin = RECIPE.index('  case "${VERAOS_SOURCE_HEAD:-}" in')
        end = RECIPE.index('\nelse\n  output=/work/output', begin)
        fragment = RECIPE[begin:end]
        fragment = fragment.replace('/work/output-resident-', str(parent) + '/output-resident-')
        return subprocess.run(["sh", "-c", "set -eu\n" + fragment],
                              env={**os.environ, "VERAOS_SOURCE_HEAD": head},
                              text=True, capture_output=True, check=False)

    def test_fresh_source_output_is_created_exclusively(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            result = self._run_output_gate(path, HEAD)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((path / ("output-resident-" + HEAD)).is_dir())

    def test_same_exact_head_cannot_reuse_compiled_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            self.assertEqual(0, self._run_output_gate(path, HEAD).returncode)
            repeated = self._run_output_gate(path, HEAD)
            self.assertEqual(13, repeated.returncode)
            self.assertIn("Refusing to reuse", repeated.stderr)

    def test_older_output_cache_is_not_touched(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            old_cache = path / "output"
            old_cache.mkdir()
            sentinel = old_cache / "legacy-image.bin"
            sentinel.write_bytes(b"historic-build-evidence")
            self.assertEqual(0, self._run_output_gate(path, HEAD).returncode)
            self.assertEqual(b"historic-build-evidence", sentinel.read_bytes())

    def test_nonhex_or_short_head_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for malformed in ("", "abcdef", "g" + HEAD[1:], "A" + HEAD[1:]):
                self.assertEqual(13, self._run_output_gate(Path(folder), malformed).returncode)

    def test_buildroot_git_source_must_be_clean(self):
        self.assertIn('git -C /work/buildroot status --porcelain=v1', RECIPE)
        self.assertIn('VERAOS_SOURCE_HEAD=$sourceHead', SOURCE)
        self.assertIn('O="$output"', RECIPE)
        self.assertNotIn('O=/work/output ', RECIPE)


if __name__ == "__main__":
    unittest.main()
