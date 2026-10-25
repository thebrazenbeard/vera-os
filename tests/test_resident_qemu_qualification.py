"""Offline, synthetic contract tests. No QEMU, Docker, guest or host runtime invoked."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "tools/vm/Qualify-VeraOSResidentQemu.py"
SPEC = importlib.util.spec_from_file_location("veraos_resident_qemu_qualifier", SOURCE)
q = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(q)
HEAD = q.EXPECTED_SOURCE_HEAD


class ResidentQemuQualificationTests(unittest.TestCase):
    def test_command_binds_readonly_image_and_disables_both_network_layers(self):
        cmd = q.qemu_command("runner:local", "fresh-qualifier", Path("/tmp/image"),
                             Path("/tmp/log"), memory=3072)
        self.assertIn("--network", cmd)
        self.assertEqual(cmd[cmd.index("--network") + 1], "none")
        self.assertEqual(cmd[cmd.index("-nic") + 1], "none")
        self.assertIn("type=bind,source=/tmp/image,target=/artifacts,readonly", cmd)
        self.assertIn("type=bind,source=/tmp/log,target=/logs", cmd)
        self.assertIn("init=/sbin/vera-init", cmd[cmd.index("-append") + 1])
        self.assertEqual(cmd[cmd.index("--entrypoint") + 1], "/usr/bin/qemu-system-x86_64")
        self.assertEqual(cmd[cmd.index("-append") + 1], q.BOOT_CONSOLE)
        self.assertNotIn("--privileged", cmd)

    def test_overlay_command_uses_artifact_as_raw_readonly_backing(self):
        cmd = q.overlay_command("runner:local", Path("/tmp/image"), Path("/tmp/log"))
        self.assertIn("-F", cmd)
        self.assertEqual(cmd[cmd.index("-F") + 1], "raw")
        self.assertEqual(cmd[cmd.index("-b") + 1], "/artifacts/veraos-rootfs.ext2")
        self.assertEqual(cmd[cmd.index("--entrypoint") + 1], "/usr/bin/qemu-img")
        self.assertEqual(cmd[-1], "/logs/veraos-qualification-overlay.qcow2")

    def sample_log(self, number=1):
        boot = q.expected_boot_marker(self.create_composition())
        return boot, "\n".join(("Linux version 6.6", boot,
                                 q.expected_persistence(number), q.RESIDENT_MARKER)) + "\n"

    def create_composition(self):
        if not hasattr(self, "temp"):
            self.addCleanup(lambda: self.temp.cleanup())
            self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name) / "composition.json"
        path.write_text(json.dumps({"repositories": [{"disposition": "INTEGRATED"},
                                                      {"disposition": "EXCLUDED"}]}))
        return path

    def test_two_boot_markers_require_incrementing_persistence(self):
        boot, first = self.sample_log(1)
        q.assess_log(first, boot, 1)
        _, second = self.sample_log(2)
        q.assess_log(second, boot, 2)
        with self.assertRaisesRegex(q.QualificationError, "persistence"):
            q.assess_log(first, boot, 2)

    def test_boot_requires_real_resident_component_import_marker(self):
        boot, text = self.sample_log()
        with self.assertRaisesRegex(q.QualificationError, "resident component"):
            q.assess_log(text.replace(q.RESIDENT_MARKER, "resident start requested"), boot, 1)

    def test_boot_rejects_wrong_pid1_marker(self):
        boot, text = self.sample_log()
        with self.assertRaisesRegex(q.QualificationError, "boot marker"):
            q.assess_log(text.replace("pid=1", "pid=123"), boot, 1)

    def test_boot_rejects_duplicate_markers(self):
        boot, text = self.sample_log()
        with self.assertRaisesRegex(q.QualificationError, "repeated"):
            q.assess_log(text + boot + "\n", boot, 1)

    def test_boot_rejects_guest_panic_even_if_markers_emitted(self):
        boot, text = self.sample_log()
        with self.assertRaisesRegex(q.QualificationError, "panic"):
            q.assess_log(text + "Kernel panic - not syncing\n", boot, 1)

    def test_boot_rejects_authority_grant_and_model_claim(self):
        boot, text = self.sample_log()
        with self.assertRaisesRegex(q.QualificationError, "protected-effect"):
            q.assess_log(text + "ambient_protected_effect_authority=true", boot, 1)
        with self.assertRaisesRegex(q.QualificationError, "cognition route"):
            q.assess_log(text + "cognition_route_qualified=true", boot, 1)

    def create_build_fixture(self):
        if not hasattr(self, "temp"):
            self.addCleanup(lambda: self.temp.cleanup())
            self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        kernel = root / "veraos-bzImage"
        fs = root / "veraos-rootfs.ext2"
        kernel.write_bytes(b"K" * (1024 * 1024 + 1))
        fs.write_bytes(b"F" * (1024 * 1024 + 1))
        receipt = {"Schema": "VERA_OS_BUILDROOT_BUILD_RESULT_V1",
                   "SourceHead": HEAD, "SourceTreeClean": True,
                   "BuildrootVersion": "2025.02.18", "BuildrootCommit": q.BUILDROOT_COMMIT,
                   "BuildProfile": "RESIDENT_BROWSER",
                   "Defconfig": "veraos_x86_64_resident_browser_defconfig",
                   "BrowserPackaged": True, "ResidentCoreSourceStaged": True,
                   "ResidentCoreImportQualified": False, "ProtectedEffectAuthority": False,
                   "KernelSha256": q.sha256_file(kernel), "RootfsSha256": q.sha256_file(fs)}
        (root / "veraos-build-result.json").write_text(json.dumps(receipt))
        return root, receipt

    def test_valid_exact_receipt_and_artifacts(self):
        root, receipt = self.create_build_fixture()
        self.assertEqual(q.validate_build(root, HEAD), receipt)

    def test_build_receipt_rejects_wrong_source_or_builder(self):
        root, receipt = self.create_build_fixture()
        with self.assertRaisesRegex(q.QualificationError, "unreviewed image source HEAD"):
            q.validate_build(root, "b" * 40)
        receipt["BuildrootVersion"] = "2024.02.4"
        (root / "veraos-build-result.json").write_text(json.dumps(receipt))
        with self.assertRaisesRegex(q.QualificationError, "Buildroot version"):
            q.validate_build(root, HEAD)

    def test_build_receipt_rejects_premature_import_or_protected_authority(self):
        root, receipt = self.create_build_fixture()
        receipt["ResidentCoreImportQualified"] = True
        (root / "veraos-build-result.json").write_text(json.dumps(receipt))
        with self.assertRaisesRegex(q.QualificationError, "premature"):
            q.validate_build(root, HEAD)
        receipt["ResidentCoreImportQualified"] = False
        receipt["ProtectedEffectAuthority"] = True
        (root / "veraos-build-result.json").write_text(json.dumps(receipt))
        with self.assertRaisesRegex(q.QualificationError, "protected"):
            q.validate_build(root, HEAD)

    def test_build_receipt_rejects_changed_image_even_when_receipt_claims_correct_hash(self):
        root, _ = self.create_build_fixture()
        with (root / "veraos-rootfs.ext2").open("ab") as f:
            f.write(b"CHANGED")
        with self.assertRaisesRegex(q.QualificationError, "hash mismatch"):
            q.validate_build(root, HEAD)

    def test_source_stage_receipt_bound_to_build_result(self):
        root, receipt = self.create_build_fixture()
        stage = root / "stage"
        stage.mkdir()
        receipt_path = stage / "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json"
        receipt_path.write_text('{"schema":"VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1"}')
        receipt["ResidentCoreStageReceiptSha256"] = q.sha256_file(receipt_path)
        q.validate_resident_stage(stage, receipt)
        receipt_path.write_text(receipt_path.read_text() + " ")
        with self.assertRaisesRegex(q.QualificationError, "disagrees"):
            q.validate_resident_stage(stage, receipt)

    def test_existing_log_directory_refused_before_external_commands(self):
        root, _ = self.create_build_fixture()
        repo = root / "source"
        artifacts = root / "artifacts"
        repo.mkdir()
        artifacts.mkdir()
        logs = root / "existing-logs"
        logs.mkdir()
        sentinel = logs / "prior-qualification.json"
        sentinel.write_text('previous evidence must survive')
        with mock.patch.object(q.subprocess, "run", side_effect=AssertionError("external command executed")):
            with self.assertRaisesRegex(q.QualificationError, "already exists"):
                q.main(["--repo", str(repo), "--artifacts", str(artifacts),
                        "--resident-source-stage", str(root / "stage"),
                        "--logs", str(logs), "--source-head", HEAD,
                        "--expected-runner-image-id", "sha256:" + "f" * 64])
        self.assertEqual(sentinel.read_text(), 'previous evidence must survive')

    def test_run_boot_success_path_with_synthetic_qemu_serial_output(self):
        """A real success must reach the final log evaluation without timeout."""
        boot, serial_output = self.sample_log(number=1)
        if not hasattr(self, "temp"):
            self.addCleanup(lambda: self.temp.cleanup())
            self.temp = tempfile.TemporaryDirectory()
        logfile = Path(self.temp.name) / "single-pass.log"

        class FakeQemuProcess:
            def poll(self):
                return None

            def wait(self, timeout):
                return 143

        def fake_launch(command, *, stdout, stderr):
            self.assertEqual(command, ["synthetic-docker-qemu"])
            stdout.write(serial_output)
            stdout.flush()
            return FakeQemuProcess()

        with mock.patch.object(q.subprocess, "Popen", side_effect=fake_launch) as popen:
            with mock.patch.object(q.subprocess, "run",
                                   return_value=q.subprocess.CompletedProcess([], 0)) as stop:
                with mock.patch.object(q.time, "monotonic", side_effect=[0, 1, 1, 2, 8]):
                    with mock.patch.object(q.time, "sleep"):
                        q.run_boot(["synthetic-docker-qemu"], "unique-container-1",
                                   logfile, boot, 1, 30)
        popen.assert_called_once()
        stop.assert_called_once()
        self.assertEqual(stop.call_args.args[0],
                         ["docker", "stop", "-t", "1", "unique-container-1"])
        self.assertEqual(logfile.read_text(), serial_output)

    def test_marker_printing_process_that_exits_nonzero_is_rejected(self):
        boot, serial_output = self.sample_log()
        logfile = Path(self.temp.name) / "fake-exit.log"

        class FakeEarlyExit:
            returncode = 42

            def poll(self):
                return 42

        def fake_launch(command, *, stdout, stderr):
            stdout.write(serial_output)
            stdout.flush()
            return FakeEarlyExit()

        with mock.patch.object(q.subprocess, "Popen", side_effect=fake_launch):
            with mock.patch.object(q.subprocess, "run") as stop:
                with self.assertRaisesRegex(q.QualificationError, "exited before live dwell"):
                    q.run_boot(["synthetic-fake"], "never-stop", logfile, boot, 1, 30)
        stop.assert_not_called()

    def test_marker_printing_process_that_dies_during_dwell_is_rejected(self):
        boot, serial_output = self.sample_log()
        logfile = Path(self.temp.name) / "fake-late-exit.log"

        class FakeLateExit:
            returncode = 23

            def __init__(self):
                self.polls = 0

            def poll(self):
                self.polls += 1
                return None if self.polls <= 1 else 23

        def fake_launch(command, *, stdout, stderr):
            stdout.write(serial_output)
            stdout.flush()
            return FakeLateExit()

        with mock.patch.object(q.subprocess, "Popen", side_effect=fake_launch):
            with mock.patch.object(q.subprocess, "run") as stop:
                with mock.patch.object(q.time, "monotonic", side_effect=[0, 1, 1, 2]):
                    with mock.patch.object(q.time, "sleep"):
                        with self.assertRaisesRegex(q.QualificationError, "exited before live dwell"):
                            q.run_boot(["fake"], "never-stop", logfile, boot, 1, 30)
        stop.assert_not_called()

    def test_failed_docker_stop_does_not_become_qualification_pass(self):
        boot, serial_output = self.sample_log()
        logfile = Path(self.temp.name) / "fake-stop-fail.log"

        class FakeAlive:
            def poll(self):
                return None

            def wait(self, timeout):
                return 1

        def fake_launch(command, *, stdout, stderr):
            stdout.write(serial_output)
            stdout.flush()
            return FakeAlive()

        with mock.patch.object(q.subprocess, "Popen", side_effect=fake_launch):
            with mock.patch.object(q.subprocess, "run",
                                   return_value=q.subprocess.CompletedProcess([], 1)):
                with mock.patch.object(q.time, "monotonic", side_effect=[0, 1, 1, 2, 8]):
                    with mock.patch.object(q.time, "sleep"):
                        with self.assertRaisesRegex(q.QualificationError, "stopped unexpectedly"):
                            q.run_boot(["fake"], "stopping-failed", logfile, boot, 1, 30)

    def test_runner_tag_must_resolve_to_separately_pinned_sha256_id(self):
        good = "sha256:" + "f" * 64
        with mock.patch.object(q.subprocess, "run",
                               return_value=q.subprocess.CompletedProcess([], 0, stdout=good + "\n")) as inspect:
            self.assertEqual(q.pin_runner_image("reviewed:runner", good), good)
        self.assertIn("{{.Id}}", inspect.call_args.args[0])
        with mock.patch.object(q.subprocess, "run",
                               return_value=q.subprocess.CompletedProcess([], 0, stdout=good + "\n")):
            with self.assertRaisesRegex(q.QualificationError, "disagrees"):
                q.pin_runner_image("reviewed:runner", "sha256:" + "0" * 64)

    def test_wrong_verifier_blob_rejected_before_execution(self):
        artifacts, receipt = self.create_build_fixture()
        repo = artifacts / "repo"
        repo.mkdir()
        stage = artifacts / "stage"
        stage.mkdir()
        receipt_path = stage / "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json"
        receipt_path.write_text("{}")
        receipt["ResidentCoreStageReceiptSha256"] = q.sha256_file(receipt_path)
        (artifacts / "veraos-build-result.json").write_text(json.dumps(receipt))
        logs = artifacts.parent / "distinct-nonexistent-qualification-logs"

        def fake_git(cmd, *args, **kwargs):
            self.assertEqual(cmd[0], "git", "unreviewed verifier was executed")
            if "rev-parse" in cmd:
                return q.subprocess.CompletedProcess(cmd, 0, stdout=HEAD + "\n")
            if "status" in cmd:
                return q.subprocess.CompletedProcess(cmd, 0, stdout="")
            if "hash-object" in cmd:
                return q.subprocess.CompletedProcess(cmd, 0, stdout="0" * 40 + "\n")
            self.fail(f"unexpected external command {cmd}")

        with mock.patch.object(q.subprocess, "run", side_effect=fake_git):
            with self.assertRaisesRegex(q.QualificationError, "verifier differs"):
                q.main(["--repo", str(repo), "--artifacts", str(artifacts),
                        "--resident-source-stage", str(stage), "--logs", str(logs),
                        "--source-head", HEAD,
                        "--expected-runner-image-id", "sha256:" + "f" * 64])
        self.assertFalse(logs.exists())


if __name__ == "__main__":
    unittest.main()
