#!/usr/bin/env python3
"""Read-only local build-tool byte inventory; never authenticates a Buildroot build.

A binary measurement is not a sandbox, transitive dependency closure, a
cryptographic binding to a later execve, or evidence of image construction.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys

TOOLS = ("make", "gcc", "mke2fs", "debugfs", "python3", "sha256sum", "git")
MAX_TOOL_SIZE_BYTES = 128 * 1024 * 1024


class BuilderToolHold(ValueError):
    pass


@dataclass(frozen=True)
class LocalToolMeasurement:
    name: str
    discovered_path: str
    resolved_path: str
    sha256: str
    bytes: int
    path_is_symlink: bool
    local_file_descriptor_measured: bool = True
    dependency_closure_verified: bool = False
    future_exec_identity_verified: bool = False


@dataclass(frozen=True)
class BuilderToolInventory:
    tools: tuple[LocalToolMeasurement, ...]
    platform: str
    process_pid: int
    status: str = "LOCAL_BUILDER_TOOL_BYTES_OBSERVED_ONLY"
    buildroot_source_binding_verified: bool = False
    container_image_rebuild_reproducible: bool = False
    transitive_dependencies_verified: bool = False
    subsequent_execve_binding_verified: bool = False
    final_output_images_verified: bool = False
    guest_boot_verified: bool = False
    qualified_runtime_consumed: bool = False
    authorization_effect: str = "NONE"


def _identity(s: os.stat_result) -> tuple[int, ...]:
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def measure_tool(name: str, *, expected_sha256: str | None = None) -> LocalToolMeasurement:
    if name not in TOOLS:
        raise BuilderToolHold("unsupported pinned build tool")
    found = shutil.which(name)
    if not found:
        raise BuilderToolHold("required build tool missing: " + name)
    alias = Path(found).absolute()
    try:
        before_alias = os.lstat(alias)
        resolved = alias.resolve(strict=True)
        fd = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise BuilderToolHold("unable to open local tool bytes: " + name) from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not os.access(resolved, os.X_OK):
            raise BuilderToolHold("build tool is not an executable regular file")
        if before.st_size <= 0 or before.st_size > MAX_TOOL_SIZE_BYTES:
            raise BuilderToolHold("build tool outside bounded byte-size range")
        h = hashlib.sha256()
        with os.fdopen(os.dup(fd), "rb", closefd=True) as stream:
            while data := stream.read(1024 * 1024):
                h.update(data)
        digest = h.hexdigest()
        # These checks catch ordinary persistent swaps, not transient same-user
        # path substitution or in-place restoration between samples.
        try:
            after_alias = os.lstat(alias)
            after = os.stat(resolved, follow_symlinks=False)
        except OSError as exc:
            raise BuilderToolHold("tool path disappeared while measured") from exc
        if (_identity(before) != _identity(os.fstat(fd))
                or _identity(before) != _identity(after)
                or _identity(before_alias) != _identity(after_alias)):
            raise BuilderToolHold("tool bytes/path changed during read")
        if expected_sha256 is not None:
            if (type(expected_sha256) is not str or len(expected_sha256) != 64
                    or any(x not in "0123456789abcdef" for x in expected_sha256)
                    or digest != expected_sha256):
                raise BuilderToolHold("observed tool digest differs from expected claim")
        return LocalToolMeasurement(
            name=name, discovered_path=str(alias), resolved_path=str(resolved),
            sha256=digest, bytes=before.st_size,
            path_is_symlink=stat.S_ISLNK(before_alias.st_mode),
        )
    finally:
        os.close(fd)


def inspect_builder_tools() -> BuilderToolInventory:
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise BuilderToolHold("native POSIX nofollow tool measurement required")
    records = tuple(measure_tool(name) for name in TOOLS)
    return BuilderToolInventory(tools=records,
                                platform=" ".join(os.uname()), process_pid=os.getpid())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-json", action="store_true", help="print local observation")
    parser.parse_args()
    print(json.dumps(asdict(inspect_builder_tools()), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, BuilderToolHold) as exc:
        print("VERAOS_BUILDER_TOOLS_HOLD: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
