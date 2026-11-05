"""Disposable DEV worker launcher proposal; never a production authority issuer.

The boundary is a *closed* bubblewrap mount/user/network/PID namespace with
one read-only application bundle and private scratch. Only a fixed executable
basename inside that bundle can run. Neither the planner nor a zero exit code
can establish trustworthy OS isolation: the actual child must undergo hostile
denial probes on the exact host before any production gate may change.

This module does not install bubblewrap, create Linux accounts, change host
configuration, load models, or grant protected effects. Missing prerequisites
raise instead of falling back to a same-UID Python subprocess.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat

from .worker_execution_gate import (
    DEV_SUBPROCESS_FIXTURE,
    WorkerExecutionHeld,
    require_dev_fixture_execution,
)


class DisposableIsolationHeld(RuntimeError):
    """A development fixture could not be planned or executed fail-closed."""


@dataclass(frozen=True, slots=True)
class DisposableWorkerPlan:
    argv: tuple[str, ...]
    timeout_seconds: float
    bundle_executable_sha256: str
    production_worker_isolation: str = "HOLD"
    protected_effects: str = "DENIED"
    evidence: str = "SOURCE_LAUNCH_PLAN_ONLY"


def _native_linux_file(value: Path, *, directory: bool) -> Path:
    """Reject broad, symbolic or 9p/DrvFS inputs; NOT host custody."""
    if os.name != "posix" or not Path("/proc/self/status").exists():
        raise DisposableIsolationHeld("Linux kernel environment required")
    if not value.is_absolute():
        raise DisposableIsolationHeld("absolute native Linux path required")
    try:
        # Reject symlinks in every path segment; resolve alone hides them.
        for ancestor in (value, *value.parents):
            if ancestor.is_symlink():
                raise DisposableIsolationHeld("symlinked input path held")
        actual = value.resolve(strict=True)
        mode = actual.stat().st_mode
    except OSError as exc:
        raise DisposableIsolationHeld("input path unavailable") from exc
    if actual == Path("/") or actual.parts[:2] in (
        ("/", "mnt"), ("/", "proc"), ("/", "sys"), ("/", "dev"),
        ("/", "run"),
    ):
        raise DisposableIsolationHeld("broad or host-shared input held")
    if directory != stat.S_ISDIR(mode):
        raise DisposableIsolationHeld("incorrect input file type")
    if not directory and not stat.S_ISREG(mode):
        raise DisposableIsolationHeld("regular binary required")
    if mode & stat.S_IWOTH:
        raise DisposableIsolationHeld("world-writable launch input held")
    # WSL drives can be remounted under /home or /tmp: a lexical /mnt guard
    # alone is insufficient. Inspect the kernel mount backing this path.
    try:
        mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
        matching_mounts = 0
        for line in mountinfo.splitlines():
            fields = line.split(" - ", 1)
            if len(fields) != 2:
                raise DisposableIsolationHeld("mount inventory malformed")
            before, after = fields[0].split(), fields[1].split()
            if len(before) < 5 or not after:
                raise DisposableIsolationHeld("mount inventory malformed")
            mount_point = re.sub(
                r"\\([0-7]{3})",
                lambda item: chr(int(item.group(1), 8)), before[4],
            )
            mounted = Path(mount_point)
            if mounted == actual or mounted in actual.parents:
                matching_mounts += 1
            # A recursive --ro-bind could expose ANY nested submount inside
            # the bundle; deny unknown types as well as Windows mount types.
            if directory and actual in mounted.parents:
                raise DisposableIsolationHeld("nested bundle mount held")
            if after[0].lower() in ("9p", "drvfs", "fuse.wsl") and (
                mounted == actual or mounted in actual.parents
            ):
                raise DisposableIsolationHeld("host-shared mount input held")
        if not matching_mounts:
            raise DisposableIsolationHeld("no covering mount observed")
    except OSError as exc:
        raise DisposableIsolationHeld("mount inventory unavailable") from exc
    return actual


def _trusted_system_bwrap() -> Path:
    """Require root-owned system tool provenance before *any* execution.

    This proves neither correctness of bubblewrap nor OS confinement, but
    closes the obvious fake-bwrap-as-unsandboxed-executable attack. A caller
    can inject an executable path into the *planner*, never the launcher.
    """
    found = shutil.which("bwrap")
    if not found:
        raise DisposableIsolationHeld("bubblewrap unavailable; no fallback")
    tool = _native_linux_file(Path(found), directory=False)
    if tool.parent not in (Path("/usr/bin"), Path("/usr/local/bin"), Path("/bin")):
        raise DisposableIsolationHeld("bubblewrap is not in a system directory")
    for segment in (tool, *tool.parents):
        info = segment.stat()
        if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise DisposableIsolationHeld("bubblewrap path lacks root custody")
    if not os.access(tool, os.X_OK):
        raise DisposableIsolationHeld("bubblewrap not executable")
    return tool


def plan_disposable_dev_worker(
    *, bundle_dir: Path, runner_name: str,
    bwrap_executable: Path | None = None,
    timeout_seconds: float = 5.0,
    requested_effects: object = (),
) -> DisposableWorkerPlan:
    """Construct one no-network DEV bundle plan without running anything.

    The bundle must contain a self-contained executable; no host /usr, /lib,
    Windows drive, credentials or inherited environment are bind-mounted.
    A launcher plan is deliberately NOT evidence that bubblewrap is available
    on Lappy, or that a child has passed a live denial test.
    """
    try:
        require_dev_fixture_execution(
            operation=DEV_SUBPROCESS_FIXTURE,
            requested_effects=requested_effects,
        )
    except WorkerExecutionHeld as exc:
        raise DisposableIsolationHeld("protected effects not permitted") from exc
    if type(timeout_seconds) not in (float, int) or not 0 < timeout_seconds <= 10:
        raise DisposableIsolationHeld("bounded timeout required")
    if type(runner_name) is not str or not re.fullmatch(
        r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", runner_name,
    ) or runner_name in (".", ".."):
        raise DisposableIsolationHeld("fixed executable basename required")
    # Only a source-plan caller may provide a synthetic tool path; the actual
    # executor below always resolves and validates a system-owned binary.
    bwrap = (_trusted_system_bwrap() if bwrap_executable is None
             else _native_linux_file(bwrap_executable, directory=False))
    bundle = _native_linux_file(bundle_dir, directory=True)
    runner = _native_linux_file(bundle / runner_name, directory=False)
    if runner.parent != bundle or not os.access(runner, os.X_OK):
        raise DisposableIsolationHeld("runner absent or non-executable")
    if not os.access(bwrap, os.X_OK):
        raise DisposableIsolationHeld("bubblewrap not executable")

    # A digest is provenance *hint*, never an immutable descriptor or signer.
    with runner.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    argv = (
        str(bwrap), "--die-with-parent", "--new-session", "--unshare-all",
        "--clearenv", "--setenv", "HOME", "/tmp",
        "--setenv", "PATH", "/app",
        "--dir", "/app", "--tmpfs", "/tmp", "--proc", "/proc",
        "--dev", "/dev", "--ro-bind", str(bundle), "/app",
        "--chdir", "/tmp", "--", "/app/" + runner_name,
    )
    return DisposableWorkerPlan(
        argv=argv,
        timeout_seconds=float(timeout_seconds),
        bundle_executable_sha256=digest,
    )


def run_disposable_dev_worker(
    *, bundle_dir: Path, runner_name: str,
    timeout_seconds: float = 5.0,
    requested_effects: object = (),
) -> None:
    """Fail-closed live-launch stub pending a *real* resource controller.

    The generated argv is a source artifact for independent review. A timeout
    alone cannot cap aggregate RAM, forks, CPU or I/O; running the process now
    could jeopardize other work on Lappy. No caller flag may bypass this hold.
    """
    # Do not accept caller-manufactured argv/plan objects: they would allow a
    # same-UID caller to run an arbitrary unsandboxed executable via this API.
    plan_disposable_dev_worker(
        bundle_dir=bundle_dir, runner_name=runner_name,
        timeout_seconds=timeout_seconds,
        requested_effects=requested_effects,
    )
    raise DisposableIsolationHeld(
        "live launch held: bounded resource controller and host denial unqualified"
    )
