"""Classify *reported* worker denial tests without granting runtime authority.

This is a source-level evidence triage contract for a future disposable worker
qualification harness. The caller controls every byte of ``report``; even a
perfect-looking matrix cannot establish a Windows owner, protected capability,
kernel confinement, or host-owned attestation. No effect broker imports this as
an authorization primitive.
"""

from __future__ import annotations

from dataclasses import dataclass


SCHEMA = "veraos.worker-isolation-denial.v1"
ROLES = frozenset({"inspect", "digest"})
REQUIRED_PROBES = frozenset({
    "state_read_denied",
    "state_write_denied",
    "foreign_worktree_read_denied",
    "windows_host_mount_absent",
    "windows_interop_absent",
    "windows_executable_unreachable",
    "ambient_capabilities_zero",
    "no_new_privileges_set",
    "protected_broker_denied",
    "scoped_fixture_completed",
})
_FIELDS = frozenset({"schema", "worker_role", "worker_uid", "coordinator_uid", "probes"})


@dataclass(frozen=True, slots=True)
class IsolationDenialVerdict:
    """Source report completeness is orthogonal to production qualification."""

    report_complete: bool
    reported_probe_failures: tuple[str, ...]
    evidence: str
    production_worker_isolation: str
    protected_effects: str
    reasons: tuple[str, ...]


def assess_reported_denials(report: object) -> IsolationDenialVerdict:
    """Require a strict, complete source report while ALWAYS holding authority.

    Exact built-in types reject bool-as-int, truthy strings, mapping subclasses,
    and objects whose getter may execute code. This validates data shape, not
    whether tests ran or whether their outcomes are truthful.
    """
    reasons = ["caller_supplied_report_not_host_attestation",
               "independent_os_denial_not_verified",
               "trusted_windows_owner_and_broker_not_implemented"]
    failures: list[str] = []
    shape_ok = True
    if type(report) is not dict:
        reasons.append("report_not_exact_dict")
        shape_ok = False
    elif report.keys() != _FIELDS:
        reasons.append("report_field_set_mismatch")
        shape_ok = False

    if shape_ok:
        assert type(report) is dict
        if type(report["schema"]) is not str or report["schema"] != SCHEMA:
            reasons.append("unsupported_report_schema")
            shape_ok = False
        if type(report["worker_role"]) is not str or report["worker_role"] not in ROLES:
            reasons.append("unsupported_worker_role")
            shape_ok = False
        uid = report["worker_uid"]
        coordinator_uid = report["coordinator_uid"]
        if (type(uid) is not int or type(coordinator_uid) is not int or
                uid <= 0 or coordinator_uid < 0 or uid == coordinator_uid):
            reasons.append("distinct_nonroot_principals_not_reported")
            shape_ok = False
        probes = report["probes"]
        if type(probes) is not dict:
            reasons.append("probes_not_exact_dict")
            shape_ok = False
        elif probes.keys() != REQUIRED_PROBES:
            reasons.append("probe_set_mismatch")
            shape_ok = False
        else:
            for name in sorted(REQUIRED_PROBES):
                value = probes[name]
                if type(value) is not bool:
                    failures.append(name)
                    reasons.append("probe_not_boolean:" + name)
                elif not value:
                    failures.append(name)
                    reasons.append("probe_failed:" + name)

    complete = shape_ok and not failures
    if complete:
        reasons.append("reported_denials_complete_but_untrusted")
    else:
        reasons.append("reported_denials_incomplete_or_failed")
    return IsolationDenialVerdict(
        report_complete=complete,
        reported_probe_failures=tuple(failures),
        evidence="CALLER_SUPPLIED_SOURCE_REPORT",
        production_worker_isolation="HOLD",
        protected_effects="DENIED",
        reasons=tuple(reasons),
    )
