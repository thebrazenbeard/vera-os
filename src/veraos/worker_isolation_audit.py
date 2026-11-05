"""Read-only Linux/WSL worker exposure inventory; NEVER an authority issuer.

This observes the *probing process*, not an independently authenticated
VeraOS worker. The result always holds production qualification, even when
individual kernel indicators look favorable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class IsolationProbeError(RuntimeError):
    """Incomplete kernel evidence must not be reported as safe."""


def _status_values(text: str) -> dict[str, str]:
    result = {}
    for row in text.splitlines():
        if ":" in row:
            key, value = row.split(":", 1)
            result[key] = value.strip().split()[0] if value.strip() else ""
    required = ("CapEff", "NoNewPrivs", "Seccomp")
    if any(not result.get(field) for field in required):
        raise IsolationProbeError("kernel status fields missing")
    try:
        int(result["CapEff"], 16)
        int(result["NoNewPrivs"], 10)
        int(result["Seccomp"], 10)
    except ValueError as exc:
        raise IsolationProbeError("kernel status fields malformed") from exc
    return result


def _shared_mount_count(text: str) -> int:
    count = 0
    rows = text.splitlines()
    if not rows:
        raise IsolationProbeError("mount inventory absent")
    for row in rows:
        if " - " not in row:
            raise IsolationProbeError("mount inventory malformed")
        after = row.split(" - ", 1)[1].split()
        if not after:
            raise IsolationProbeError("mount filesystem type missing")
        # Keep the read-only audit aligned with the disposable-runner mount
        # guard: WSL shared paths can also appear with the fuse.wsl type.
        if after[0].lower() in {"9p", "drvfs", "fuse.wsl"}:
            count += 1
    return count


def classify_observation(
    *, uid: int, parent_uid: int | None, mount_namespace: str,
    parent_mount_namespace: str | None, status_text: str, mountinfo_text: str,
    interop_environment_present: bool, interop_directory_traversable: bool,
    windows_executable_accessible: bool,
) -> dict[str, object]:
    """Summarize read-only observations without ever accepting worker authority."""
    fields = _status_values(status_text)
    shared_mounts = _shared_mount_count(mountinfo_text)
    if not mount_namespace or uid < 0:
        raise IsolationProbeError("process identity or namespace absent")
    reasons = [
        "foreign_uid_denial_not_probed",
        "host_owned_identity_not_probed",
        "protected_effect_broker_not_probed",
    ]
    if parent_uid is not None and uid == parent_uid:
        reasons.append("same_uid_as_parent")
    if parent_mount_namespace is not None and mount_namespace == parent_mount_namespace:
        reasons.append("same_mount_namespace_as_parent")
    if int(fields["CapEff"], 16):
        reasons.append("effective_linux_capabilities_present")
    if fields["NoNewPrivs"] != "1":
        reasons.append("no_new_privileges_not_set")
    if fields["Seccomp"] != "2":
        reasons.append("seccomp_filter_not_observed")
    if shared_mounts:
        reasons.append("host_shared_mount_visible")
    if interop_environment_present:
        reasons.append("wsl_interop_environment_present")
    if interop_directory_traversable:
        reasons.append("wsl_interop_directory_traversable")
    if windows_executable_accessible:
        reasons.append("windows_executable_accessible")
    return {
        "evidence": "READ_ONLY_PROCESS_OBSERVATION",
        "production_worker_isolation": "HOLD",
        "host_shared_mount_count": shared_mounts,
        "effective_uid": uid,
        "reasons": sorted(reasons),
    }


def probe_current_process() -> dict[str, object]:
    """Read Linux kernel metadata and access flags; perform zero host effects."""
    try:
        status = Path("/proc/self/status").read_text(encoding="ascii")
        mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
        own_ns = os.readlink("/proc/self/ns/mnt")
        parent_ns = os.readlink(f"/proc/{os.getppid()}/ns/mnt")
        parent_status = Path(f"/proc/{os.getppid()}/status").read_text(
            encoding="ascii")
        parent_uid = next(
            int(line.split()[1]) for line in parent_status.splitlines()
            if line.startswith("Uid:"))
        return classify_observation(
            uid=os.geteuid(), parent_uid=parent_uid,
            mount_namespace=own_ns, parent_mount_namespace=parent_ns,
            status_text=status, mountinfo_text=mountinfo,
            interop_environment_present=bool(os.environ.get("WSL_INTEROP")),
            interop_directory_traversable=os.access("/run/WSL", os.X_OK),
            windows_executable_accessible=os.access(
                "/mnt/c/Windows/System32/cmd.exe", os.X_OK),
        )
    except (OSError, StopIteration, ValueError) as exc:
        raise IsolationProbeError("live Linux process evidence incomplete") from exc


def main() -> int:
    try:
        result = probe_current_process()
    except IsolationProbeError:
        print(json.dumps({
            "evidence": "READ_ONLY_PROCESS_OBSERVATION",
            "production_worker_isolation": "HOLD",
            "reasons": ["kernel_evidence_incomplete"],
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
