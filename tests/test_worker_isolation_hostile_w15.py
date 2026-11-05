"""Hostile source fixtures; these are NOT OS confinement or host denial tests.

The security property under test is narrow: no arrangement of caller-supplied
Linux process observations may authorize a production worker or protected
effect. The tests intentionally exercise observations that might look secure.
"""

from __future__ import annotations

import contextlib
import io
import itertools
import json
import unittest
from unittest.mock import patch

from veraos.worker_execution_gate import (
    DEV_SUBPROCESS_FIXTURE,
    WorkerExecutionHeld,
    assess_worker_execution,
    require_dev_fixture_execution,
)
from veraos.worker_isolation_audit import (
    IsolationProbeError,
    classify_observation,
    main as audit_main,
)


_EXT4 = "10 2 8:1 / / rw - ext4 /dev/sda rw\n"
_WINDOWS_9P = "11 2 0:2 / /mnt/c rw - 9p drvfs rw\n"
_MOUNT_OBSCURED = "11 2 0:2 / /work/host rw - fuse.sshfs host rw\n"


def _status(*, caps: str, nnp: int, seccomp: int) -> str:
    return f"CapEff:\t{caps}\nNoNewPrivs:\t{nnp}\nSeccomp:\t{seccomp}\n"


def _observation(**overrides: object) -> dict[str, object]:
    options: dict[str, object] = {
        "uid": 2001,
        "parent_uid": 1000,
        "mount_namespace": "mnt:[2001]",
        "parent_mount_namespace": "mnt:[1000]",
        "status_text": _status(caps="0", nnp=1, seccomp=2),
        "mountinfo_text": _EXT4,
        "interop_environment_present": False,
        "interop_directory_traversable": False,
        "windows_executable_accessible": False,
    }
    options.update(overrides)
    return options


class HostileWorkerIsolationSourceTests(unittest.TestCase):
    def test_every_apparently_favorable_kernel_snapshot_still_holds(self):
        """UID separation, seccomp and a private mount NS are not access denial."""
        cases = itertools.product(
            ((1000, 1000), (2001, 1000), (2001, None)),
            (("mnt:[1]", "mnt:[1]"), ("mnt:[2]", "mnt:[1]")),
            ("0", "0000000000000001"),
            (0, 1),
            (0, 2),
            (False, True),
        )
        observed = 0
        for (uid, parent_uid), (ns, parent_ns), caps, nnp, seccomp, exposed in cases:
            with self.subTest(uid=uid, ns=ns, caps=caps, nnp=nnp,
                              seccomp=seccomp, exposed=exposed):
                result = classify_observation(**_observation(
                    uid=uid, parent_uid=parent_uid,
                    mount_namespace=ns, parent_mount_namespace=parent_ns,
                    status_text=_status(caps=caps, nnp=nnp, seccomp=seccomp),
                    interop_environment_present=exposed,
                    interop_directory_traversable=exposed,
                    windows_executable_accessible=exposed,
                ))
                self.assertEqual(result["production_worker_isolation"], "HOLD")
                self.assertIn("foreign_uid_denial_not_probed", result["reasons"])
                self.assertIn("protected_effect_broker_not_probed", result["reasons"])
                observed += 1
        self.assertEqual(observed, 96)

    def test_obscured_foreign_mount_can_evade_simple_fstype_counter(self):
        """A zero drvfs/9p count cannot establish absence of host data."""
        result = classify_observation(**_observation(
            mountinfo_text=_EXT4 + _MOUNT_OBSCURED,
        ))
        self.assertEqual(result["host_shared_mount_count"], 0)
        self.assertEqual(result["production_worker_isolation"], "HOLD")
        self.assertIn("foreign_uid_denial_not_probed", result["reasons"])

    def test_mount_exposure_detected_even_after_wsl_environment_cleared(self):
        result = classify_observation(**_observation(
            mountinfo_text=_EXT4 + _WINDOWS_9P,
            interop_environment_present=False,
            interop_directory_traversable=False,
            windows_executable_accessible=False,
        ))
        self.assertIn("host_shared_mount_visible", result["reasons"])
        self.assertEqual(result["host_shared_mount_count"], 1)

    def test_caller_supplied_production_grade_report_never_unlocks_broker(self):
        report = classify_observation(**_observation())
        report.update({"production_worker_isolation": "QUALIFIED",
                       "authority": "Patrick", "signed_grant": True,
                       "protected_effects": "AUTHORIZED"})
        prod = assess_worker_execution(
            operation="production-worker", claimed_isolation_evidence=report)
        self.assertFalse(prod.dev_fixture_allowed)
        self.assertEqual(prod.production_worker_isolation, "HOLD")
        self.assertEqual(prod.protected_effects, "DENIED")
        dev = assess_worker_execution(
            operation=DEV_SUBPROCESS_FIXTURE,
            claimed_isolation_evidence=report)
        self.assertTrue(dev.dev_fixture_allowed)
        self.assertEqual(dev.protected_effects, "DENIED")
        with self.assertRaises(WorkerExecutionHeld):
            require_dev_fixture_execution(
                operation=DEV_SUBPROCESS_FIXTURE,
                requested_effects=("filesystem-write",),
                claimed_isolation_evidence=report,
            )

    def test_status_or_mount_metadata_gap_is_an_explicit_hold(self):
        for change in ({"status_text": "CapEff: 0\nNoNewPrivs: 1\n"},
                       {"status_text": "CapEff: unknown\nNoNewPrivs: 1\nSeccomp: 2\n"},
                       {"mountinfo_text": ""},
                       {"mountinfo_text": "11 2 0:2 / /mnt/c rw"}):
            with self.subTest(change=change):
                with self.assertRaises(IsolationProbeError):
                    classify_observation(**_observation(**change))

    def test_missing_kernel_evidence_exit_is_hold_not_success(self):
        with patch("veraos.worker_isolation_audit.probe_current_process",
                   side_effect=IsolationProbeError("foreign proc unavailable")):
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                status = audit_main()
        self.assertEqual(status, 2)
        result = json.loads(capture.getvalue())
        self.assertEqual(result["production_worker_isolation"], "HOLD")
        self.assertEqual(result["reasons"], ["kernel_evidence_incomplete"])


if __name__ == "__main__":
    unittest.main()
