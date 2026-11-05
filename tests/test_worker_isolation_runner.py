"""SOURCE tests for the disposable DEV worker planner; NOT host isolation."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from veraos.worker_isolation_runner import (
    DisposableIsolationHeld,
    plan_disposable_dev_worker,
    run_disposable_dev_worker,
)


class DisposableIsolationRunnerSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="veraos-iso-source-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.bundle = self.base / "bundle"
        self.bundle.mkdir()
        self.runner = self.bundle / "probe"
        self.runner.write_bytes(b"dev probe fixture; not a real binary\n")
        self.runner.chmod(0o700)
        self.bwrap = self.base / "bwrap"
        self.bwrap.write_bytes(b"dev fake bubblewrap fixture\n")
        self.bwrap.chmod(0o700)

    def plan(self, **overrides):
        args = {
            "bundle_dir": self.bundle,
            "runner_name": "probe",
            "bwrap_executable": self.bwrap,
        }
        args.update(overrides)
        return plan_disposable_dev_worker(**args)

    def test_closed_mount_network_user_and_env_plan(self):
        plan = self.plan()
        argv = plan.argv
        self.assertEqual(argv[0], str(self.bwrap))
        for switch in ("--unshare-all", "--die-with-parent", "--new-session",
                       "--clearenv", "--ro-bind", "--tmpfs", "--proc", "--dev"):
            self.assertIn(switch, argv)
        self.assertEqual(argv[-1], "/app/probe")
        self.assertEqual(argv[-2], "--")
        self.assertNotIn("/mnt/c", " ".join(argv))
        self.assertNotIn("--bind", argv)
        self.assertEqual(plan.production_worker_isolation, "HOLD")
        self.assertEqual(plan.protected_effects, "DENIED")
        self.assertEqual(len(plan.bundle_executable_sha256), 64)

    def test_missing_bubblewrap_has_no_fallback(self):
        with patch("veraos.worker_isolation_runner.shutil.which", return_value=None):
            with self.assertRaisesRegex(DisposableIsolationHeld, "unavailable"):
                self.plan(bwrap_executable=None)

    def test_protected_effects_and_malformed_scopes_are_held(self):
        for effects in (["git.merge"], ("host.service",), {}, None):
            with self.subTest(effects=effects):
                with self.assertRaises(DisposableIsolationHeld):
                    self.plan(requested_effects=effects)

    def test_path_traversal_and_arbitrary_command_are_held(self):
        for name in ("../probe", "/bin/sh", ".", "..", "-c", "probe;id", ""):
            with self.subTest(name=name):
                with self.assertRaises(DisposableIsolationHeld):
                    self.plan(runner_name=name)

    def test_symlinks_and_host_shared_roots_held(self):
        link = self.base / "bundle-link"
        link.symlink_to(self.bundle, target_is_directory=True)
        with self.assertRaisesRegex(DisposableIsolationHeld, "symlink"):
            self.plan(bundle_dir=link)
        link.unlink()
        self.runner.unlink()
        self.runner.symlink_to(self.bwrap)
        with self.assertRaisesRegex(DisposableIsolationHeld, "symlink"):
            self.plan()
        self.runner.unlink()
        self.runner.write_bytes(b"fixture")
        self.runner.chmod(0o700)
        for root in (Path("/"), Path("/proc")):
            with self.subTest(root=root):
                with self.assertRaises(DisposableIsolationHeld):
                    self.plan(bundle_dir=root)

    def test_windows_driven_mount_under_home_style_path_is_held(self):
        # Kernel mountpoint outranks a superficially safe POSIX-looking path.
        original = Path.read_text
        for mounted, fs_type in (
            (self.bundle, "9p"),
            (self.bundle / "nested-windows-data", "9p"),
            (self.bundle / "nested-unknown", "overlay"),
        ):
            synthetic_mount = (
                f"1 0 0:1 / / rw - ext4 /dev/sda rw\n"
                f"2 1 0:2 / {mounted} rw - {fs_type} fixture rw\n"
            )

            def read_fixture(path, *args, **kwargs):
                if str(path) == "/proc/self/mountinfo":
                    return synthetic_mount
                return original(path, *args, **kwargs)

            with self.subTest(mounted=mounted), patch.object(
                Path, "read_text", new=read_fixture,
            ):
                with self.assertRaisesRegex(DisposableIsolationHeld,
                                            "(host-shared mount input held|nested bundle mount held)"):
                    self.plan()

    def test_nonexecutable_and_world_writable_input_held(self):
        self.runner.chmod(0o600)
        with self.assertRaises(DisposableIsolationHeld):
            self.plan()
        self.runner.chmod(0o777)
        with self.assertRaisesRegex(DisposableIsolationHeld, "world-writable"):
            self.plan()

    def test_timeouts_must_be_short_and_finite(self):
        for timeout in (0, -1, 11, float("inf"), float("nan"), "5"):
            with self.subTest(timeout=timeout):
                with self.assertRaises(DisposableIsolationHeld):
                    self.plan(timeout_seconds=timeout)

    def test_even_valid_source_plan_never_launches_a_live_worker(self):
        with patch("veraos.worker_isolation_runner._trusted_system_bwrap",
                   return_value=self.bwrap), patch(
                   "subprocess.run") as run:
            with self.assertRaisesRegex(DisposableIsolationHeld, "resource controller"):
                run_disposable_dev_worker(
                    bundle_dir=self.bundle, runner_name="probe",
                )
            run.assert_not_called()

    def test_fake_bwrap_in_path_cannot_launch_an_unsandboxed_executable(self):
        # Hostile regression: a controlled PATH must not select /tmp/evil.
        with patch("veraos.worker_isolation_runner.shutil.which",
                   return_value=str(self.bwrap)), patch(
                   "subprocess.run") as run:
            with self.assertRaisesRegex(DisposableIsolationHeld, "system directory"):
                run_disposable_dev_worker(
                    bundle_dir=self.bundle, runner_name="probe",
                )
            run.assert_not_called()
        with self.assertRaises(TypeError):
            run_disposable_dev_worker(
                bundle_dir=self.bundle, runner_name="probe",
                bwrap_executable=self.bwrap,
            )


if __name__ == "__main__":
    unittest.main()
