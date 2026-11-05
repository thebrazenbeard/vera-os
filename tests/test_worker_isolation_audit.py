"""Non-privileged observation inventory and irreversible production HOLD."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from veraos.worker_isolation_audit import (
    IsolationProbeError, classify_observation,
)


STATUS = "CapEff:\t0000000000000000\nNoNewPrivs:\t1\nSeccomp:\t2\n"
NATIVE_MOUNT = "10 2 8:1 / / rw - ext4 /dev/sda rw\n"


class WorkerIsolationAuditTests(unittest.TestCase):
    def test_safe_looking_observation_still_holds_without_verified_denials(self):
        result = classify_observation(
            uid=2001, parent_uid=1000, mount_namespace="mnt:[2]",
            parent_mount_namespace="mnt:[1]", status_text=STATUS,
            mountinfo_text=NATIVE_MOUNT, interop_environment_present=False,
            interop_directory_traversable=False,
            windows_executable_accessible=False)
        self.assertEqual(result["production_worker_isolation"], "HOLD")
        self.assertEqual(result["reasons"], [
            "foreign_uid_denial_not_probed", "host_owned_identity_not_probed",
            "protected_effect_broker_not_probed"])

    def test_same_uid_shared_mount_and_windows_host_exposure_hold(self):
        result = classify_observation(
            uid=1000, parent_uid=1000, mount_namespace="mnt:[1]",
            parent_mount_namespace="mnt:[1]",
            status_text="CapEff:\t0\nNoNewPrivs:\t0\nSeccomp:\t0\n",
            mountinfo_text=NATIVE_MOUNT + "11 2 0:2 / /mnt/c rw - 9p drvfs rw\n",
            interop_environment_present=False,
            interop_directory_traversable=True,
            windows_executable_accessible=True)
        self.assertEqual(result["production_worker_isolation"], "HOLD")
        self.assertIn("same_uid_as_parent", result["reasons"])
        self.assertIn("host_shared_mount_visible", result["reasons"])
        self.assertIn("windows_executable_accessible", result["reasons"])
        self.assertIn("no_new_privileges_not_set", result["reasons"])
        self.assertIn("seccomp_filter_not_observed", result["reasons"])
        self.assertEqual(result["host_shared_mount_count"], 1)

    def test_fuse_wsl_shared_mount_is_counted_and_never_qualifies(self):
        # A host-shared WSL mount can be identified as fuse.wsl, including
        # when its mountpoint is not the obvious /mnt/c or /mnt/d location.
        # Treating it as native would under-report hostile child exposure.
        result = classify_observation(
            uid=2001, parent_uid=1000, mount_namespace="mnt:[2]",
            parent_mount_namespace="mnt:[1]", status_text=STATUS,
            mountinfo_text=(NATIVE_MOUNT +
                            "11 2 0:99 / /home/vera/host-share rw - fuse.wsl host rw\n"),
            interop_environment_present=False,
            interop_directory_traversable=False,
            windows_executable_accessible=False,
        )
        self.assertEqual(result["host_shared_mount_count"], 1)
        self.assertIn("host_shared_mount_visible", result["reasons"])
        self.assertEqual(result["production_worker_isolation"], "HOLD")

    def test_malformed_status_or_mountinfo_fails_closed(self):
        shared = dict(
            uid=1000, parent_uid=1000, mount_namespace="mnt:[1]",
            parent_mount_namespace="mnt:[1]",
            interop_environment_present=False,
            interop_directory_traversable=False,
            windows_executable_accessible=False)
        with self.assertRaises(IsolationProbeError):
            classify_observation(**shared, status_text="CapEff:\t0\n",
                                 mountinfo_text=NATIVE_MOUNT)
        with self.assertRaises(IsolationProbeError):
            classify_observation(**shared, status_text=STATUS,
                                 mountinfo_text="unparseable mountinfo")

    @unittest.skipUnless(os.name == "posix" and Path("/proc/self/status").exists(),
                         "requires real Linux procfs")
    def test_actual_empty_environment_child_reports_hold_without_side_effects(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "veraos"
                  / "worker_isolation_audit.py")
        child = subprocess.run(
            [sys.executable, "-I", "-B", str(source)],
            env={}, cwd=source.parent, capture_output=True, text=True,
            check=False, timeout=5)
        # Some managed containers deliberately hide the parent process's
        # namespace metadata. That is an evidence HOLD, never a clean pass.
        self.assertIn(child.returncode, (0, 2), child.stderr)
        report = json.loads(child.stdout)
        self.assertEqual(report["production_worker_isolation"], "HOLD")
        self.assertEqual(report["evidence"], "READ_ONLY_PROCESS_OBSERVATION")
        if child.returncode == 0:
            self.assertIn("same_uid_as_parent", report["reasons"])
            self.assertIn("same_mount_namespace_as_parent", report["reasons"])
        else:
            self.assertEqual(report["reasons"], ["kernel_evidence_incomplete"])
        self.assertNotIn("WSL_INTEROP", child.stdout)


if __name__ == "__main__":
    unittest.main()
