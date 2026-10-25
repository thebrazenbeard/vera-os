#!/usr/bin/env python3
"""Observed fd-bound synthetic ext2 tool invocation, not a Buildroot image build.

Only an isolated tiny Linux fixture is constructed. It cannot authenticate
Buildroot's full toolchain, future execve, guest boot, QVR, or actual selected
O=/work/output/images; no general arbitrary-command interface is exposed.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


class PackerObservationHold(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LocalPackerFixtureObservation:
    tool_name: str
    tool_resolved_path: str
    measured_tool_sha256: str
    launched_descriptor_sha256: str
    child_pid: int
    child_exit_code: int
    output_relative_path: str
    output_bytes: int
    output_sha256: str
    packed_member_semantics_verified: bool = False
    buildroot_selected_source_consumption_verified: bool = False
    actual_buildroot_output_images_verified: bool = False
    transitive_toolchain_closure_verified: bool = False
    future_execve_identity_verified: bool = False
    bootloader_consumption_verified: bool = False
    guest_boot_verified: bool = False
    qualified_vera_runtime_consumed: bool = False
    authorization_effect: str = "NONE"
    status: str = "LOCAL_SYNTHETIC_PACKER_FD_LAUNCH_ONLY"


def _digest_fd(fd: int) -> str:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode):
        raise PackerObservationHold("expected a regular measured descriptor")
    h = hashlib.sha256()
    offset = 0
    while offset < before.st_size:
        block = os.pread(fd, min(1024 * 1024, before.st_size - offset), offset)
        if not block:
            raise PackerObservationHold("measured descriptor unexpectedly truncated")
        h.update(block)
        offset += len(block)
    after = os.fstat(fd)
    if ((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
            != (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)):
        raise PackerObservationHold("measured descriptor changed")
    return h.hexdigest()


def _source_bounds(root: Path) -> None:
    if not root.is_dir() or root.is_symlink():
        raise PackerObservationHold("source root must be a local real directory")
    count = total = 0
    for entry in root.rglob("*"):
        if entry.is_symlink():
            raise PackerObservationHold("fixture source contains symlink")
        if entry.is_file():
            count += 1
            total += entry.stat().st_size
        elif not entry.is_dir():
            raise PackerObservationHold("unsupported fixture member")
        if count > 64 or total > 1024 * 1024:
            raise PackerObservationHold("fixture source outside tiny bound")
    if not count:
        raise PackerObservationHold("fixture source empty")


def _tool_observer():
    path = Path(__file__).with_name("Inspect-VeraOSBuilderTools.py")
    spec = importlib.util.spec_from_file_location("veraos_frozen_tool_inventory", path)
    if spec is None or spec.loader is None:
        raise PackerObservationHold("frozen #45 tool inventory source not available")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def observe_synthetic_ext2_pack(
    source_root: Path,
    *,
    expected_packer_sha256: str,
    size_mib: int = 8,
):
    """Yield an actual packed fixture and LOCAL invocation receipt.

    The output exists only within the context's owned fresh scratch directory.
    Buildroot compilation, existing images, services and host files untouched.
    """
    if (os.name != "posix" or not hasattr(os, "O_NOFOLLOW")
            or not Path("/proc/self/fd").is_dir()):
        raise PackerObservationHold("Linux proc-fd execution required")
    if type(size_mib) is not int or size_mib < 4 or size_mib > 16:
        raise PackerObservationHold("synthetic image must be 4..16 MiB")
    supplied_root = Path(source_root)
    if supplied_root.is_symlink():
        raise PackerObservationHold("source root must be a local real directory")
    source_root = supplied_root.resolve(strict=True)
    _source_bounds(source_root)
    tools = _tool_observer()
    record = tools.measure_tool("mke2fs", expected_sha256=expected_packer_sha256)
    descriptor = os.open(record.resolved_path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        observed = _digest_fd(descriptor)
        if observed != record.sha256:
            raise PackerObservationHold("selected executable descriptor mismatched preflight")
        with tempfile.TemporaryDirectory(prefix="veraos-fd-packer-fixture-") as temp:
            output_dir = Path(temp) / "output" / "images"
            output_dir.mkdir(parents=True)
            image = output_dir / "rootfs.ext2"
            if image.exists():
                raise PackerObservationHold("output image already exists")
            command = ["mke2fs", "-q", "-F", "-t", "ext2", "-d",
                       str(source_root), str(image), f"{size_mib}M"]
            # Actual child exec resolves the *inherited selected inode*, not
            # a second path lookup of /usr/sbin/mke2fs.
            try:
                proc = subprocess.Popen(
                    command, executable=f"/proc/self/fd/{descriptor}",
                    pass_fds=(descriptor,), stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
                out, err = proc.communicate(timeout=25)
            except subprocess.TimeoutExpired as exc:
                proc.kill()
                proc.communicate()
                raise PackerObservationHold("synthetic packer exceeded execution limit") from exc
            except OSError as exc:
                raise PackerObservationHold("selected packer descriptor could not exec") from exc
            if proc.returncode != 0:
                raise PackerObservationHold(
                    "selected synthetic packer failed exit=" + str(proc.returncode)
                    + " stderr=" + err[:200].decode(errors="replace"))
            if not image.is_file() or image.is_symlink():
                raise PackerObservationHold("no regular synthetic output image produced")
            fd = os.open(image, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                bytes_seen = os.fstat(fd).st_size
                digest = _digest_fd(fd)
            finally:
                os.close(fd)
            if bytes_seen != size_mib * 1024 * 1024:
                raise PackerObservationHold("synthetic image size unexpectedly changed")
            if _digest_fd(descriptor) != record.sha256:
                raise PackerObservationHold("selected executable bytes changed after launch")
            receipt = LocalPackerFixtureObservation(
                tool_name="mke2fs", tool_resolved_path=record.resolved_path,
                measured_tool_sha256=record.sha256,
                launched_descriptor_sha256=observed,
                child_pid=proc.pid, child_exit_code=proc.returncode,
                output_relative_path="output/images/rootfs.ext2",
                output_bytes=bytes_seen, output_sha256=digest)
            yield image, receipt
    finally:
        os.close(descriptor)
