"""Source-only resource observations never authorize WSL worker launch."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veraos.worker_resource_preflight import (
    ResourcePreflightIncomplete,
    classify_read_only_resource_observation,
    _relative_cgroup,
    main,
)


NATIVE_CGROUP2 = "35 24 0:30 / /sys/fs/cgroup rw,nosuid,nodev,noexec,relatime - cgroup2 cgroup rw\n"


def observe(**changes):
    args = dict(
        mountinfo=NATIVE_CGROUP2, cgroup_membership="0::/user.slice/user-1000.slice\n",
        controllers="cpu memory pids io cpuset", subtree_control="cpu memory pids io",
        writable_cgroup_directory=True, bwrap_system_owned=True,
    )
    args.update(changes)
    return classify_read_only_resource_observation(**args)


class ResourcePreflightSourceTests(unittest.TestCase):
    def test_perfectly_favorable_claims_still_hold(self):
        report = observe()
        self.assertEqual(report["dev_worker_launch"], "HOLD")
        self.assertEqual(report["production_resource_control"], "HOLD")
        self.assertIn("no_executed_denial_test", report["reasons"])

    def test_missing_controls_and_delegation_still_hold(self):
        report = observe(controllers="cpu pids", subtree_control="cpu",
                         writable_cgroup_directory=False, bwrap_system_owned=False)
        self.assertIn("required_controllers_unavailable", report["reasons"])
        self.assertIn("unprivileged_cgroup_delegation_not_observed", report["reasons"])
        self.assertIn("trusted_bwrap_not_observed", report["reasons"])

    def test_missing_cgroup_v2_mount_is_not_reported_as_ready(self):
        report = observe(mountinfo="35 24 0:30 / /sys/fs/cgroup rw - tmpfs tmpfs rw\n")
        self.assertEqual(report["cgroup_v2_mounts"], 0)
        self.assertIn("cgroup_v2_not_observed", report["reasons"])

    def test_forged_positive_boolean_is_not_authority(self):
        report = observe(mountinfo=NATIVE_CGROUP2, writable_cgroup_directory=True,
                         bwrap_system_owned=True)
        self.assertEqual(report["production_resource_control"], "HOLD")
        self.assertIn("host_owned_cgroup_not_proven", report["reasons"])

    def test_cli_favorable_observation_returns_hold_status(self):
        with patch("veraos.worker_resource_preflight.probe_current_process", return_value=observe()):
            with patch("builtins.print"):
                self.assertEqual(main(), 2)

    def test_traversal_or_missing_membership_rejected(self):
        for membership in ("0::/a/../b\n", "1:name=/foo\n", "0::not_absolute\n"):
            with self.subTest(membership=membership), self.assertRaises(ResourcePreflightIncomplete):
                _relative_cgroup(membership)

    def test_malformed_mountinfo_fails_closed(self):
        for value in ("", "not mountinfo\n", "8 1 0:1 / /sys/foo rw - \n"):
            with self.subTest(value=value), self.assertRaises(ResourcePreflightIncomplete):
                observe(mountinfo=value)


if __name__ == "__main__":
    unittest.main()
