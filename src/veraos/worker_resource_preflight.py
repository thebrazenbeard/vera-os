"""Read-only cgroup/bubblewrap preflight for disposable WSL development workers.

The preflight does not create a cgroup, install tools, spawn a child, or grant
worker authority. Its source-visible output is diagnostic evidence only.
Successful observation cannot qualify a resource controller or an OS sandbox.
"""

from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath


class ResourcePreflightIncomplete(RuntimeError):
    """A required Linux kernel observation was missing or malformed."""


_REQUIRED_CONTROLLERS = frozenset({"cpu", "memory", "pids", "io"})


def _mount_points(mountinfo: str) -> list[str]:
    points: list[str] = []
    if not mountinfo.strip():
        raise ResourcePreflightIncomplete("mountinfo missing")
    for line in mountinfo.splitlines():
        pieces = line.split(" - ", 1)
        if len(pieces) != 2:
            raise ResourcePreflightIncomplete("mountinfo malformed")
        front, back = pieces[0].split(), pieces[1].split()
        if len(front) < 5 or len(back) < 1:
            raise ResourcePreflightIncomplete("mountinfo fields missing")
        if back[0] == "cgroup2":
            points.append(front[4])
    return points


def _relative_cgroup(cgroup_text: str) -> str:
    lines = [line for line in cgroup_text.splitlines() if line]
    matches = [line[3:] for line in lines if line.startswith("0::")]
    if len(matches) != 1 or not matches[0].startswith("/"):
        raise ResourcePreflightIncomplete("unified cgroup membership missing")
    path = PurePosixPath(matches[0])
    if ".." in matches[0].split("/") or "\x00" in matches[0]:
        raise ResourcePreflightIncomplete("cgroup membership malformed")
    return str(path)


def classify_read_only_resource_observation(
    *, mountinfo: str, cgroup_membership: str, controllers: str,
    subtree_control: str, writable_cgroup_directory: bool,
    bwrap_system_owned: bool,
) -> dict[str, object]:
    """Classify kernel observations without ever returning executable authority.

    Booleans are caller-supplied observations, not trusted attestations.
    Even a completely favorable result MUST hold production and DEV launch.
    """
    mounts = _mount_points(mountinfo)
    membership = _relative_cgroup(cgroup_membership)
    available = set(controllers.split())
    enabled = {entry.lstrip("+") for entry in subtree_control.split()}
    if any(not entry.isidentifier() for entry in available | enabled):
        raise ResourcePreflightIncomplete("controller list malformed")
    reasons = {"no_executed_denial_test", "resource_limits_not_applied", "host_owned_cgroup_not_proven"}
    if not mounts:
        reasons.add("cgroup_v2_not_observed")
    if not _REQUIRED_CONTROLLERS <= available:
        reasons.add("required_controllers_unavailable")
    if not _REQUIRED_CONTROLLERS <= enabled:
        reasons.add("required_subtree_controllers_not_enabled")
    if not writable_cgroup_directory:
        reasons.add("unprivileged_cgroup_delegation_not_observed")
    if not bwrap_system_owned:
        reasons.add("trusted_bwrap_not_observed")
    return {
        "evidence": "READ_ONLY_CGROUP_PROCESS_OBSERVATION",
        "production_resource_control": "HOLD",
        "dev_worker_launch": "HOLD",
        "cgroup_v2_mounts": len(mounts),
        "cgroup_membership": membership,
        "available_controllers": sorted(available),
        "enabled_subtree_controllers": sorted(enabled),
        "reasons": sorted(reasons),
    }


def probe_current_process() -> dict[str, object]:
    """Observe own WSL/Linux process. Never mutate cgroups or run bwrap."""
    if os.name != "posix":
        raise ResourcePreflightIncomplete("Linux required")
    try:
        mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
        membership = Path("/proc/self/cgroup").read_text(encoding="ascii")
        cgroup_root = Path("/sys/fs/cgroup")
        # Root-level controllers describe the host's capabilities, not the
        # controls actually delegated to this ordinary WSL process. Observe
        # the process's own cgroup, which may be root-owned and empty.
        own_cgroup = cgroup_root / _relative_cgroup(membership).lstrip("/")
        if own_cgroup.is_symlink() or not own_cgroup.resolve().is_relative_to(cgroup_root.resolve()):
            raise ResourcePreflightIncomplete("cgroup path is not contained")
        controllers = (own_cgroup / "cgroup.controllers").read_text(encoding="ascii")
        subtree = (own_cgroup / "cgroup.subtree_control").read_text(encoding="ascii")
        # A process-local access check is informational, not evidence of real
        # delegation. Do not mkdir/write to prove it without fresh authority.
        writable = (
            os.access(own_cgroup, os.W_OK | os.X_OK)
            and os.access(own_cgroup / "cgroup.procs", os.W_OK)
            and os.access(own_cgroup / "cgroup.subtree_control", os.W_OK)
        )
        from .worker_isolation_runner import _trusted_system_bwrap, DisposableIsolationHeld

        try:
            _trusted_system_bwrap()
            bwrap_owned = True
        except (DisposableIsolationHeld, OSError):
            bwrap_owned = False
        return classify_read_only_resource_observation(
            mountinfo=mountinfo, cgroup_membership=membership,
            controllers=controllers, subtree_control=subtree,
            writable_cgroup_directory=writable, bwrap_system_owned=bwrap_owned,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise ResourcePreflightIncomplete("kernel resource evidence incomplete") from exc


def main() -> int:
    try:
        result = probe_current_process()
    except ResourcePreflightIncomplete:
        print(json.dumps({
            "evidence": "READ_ONLY_CGROUP_PROCESS_OBSERVATION",
            "production_resource_control": "HOLD",
            "dev_worker_launch": "HOLD",
            "reasons": ["kernel_resource_evidence_incomplete"],
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    # A successful read-only observation is not a release-gate success.
    # Return the reserved HOLD status so shell automation cannot accidentally
    # interpret this preflight as permission to launch a worker.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
