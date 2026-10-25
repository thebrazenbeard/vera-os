#!/usr/bin/env python3
"""Audit exact ext2 bytes through a kernel-sealed file descriptor.

Source-only bounded verification; no future boot/runtime/effect qualification.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

class ArtifactCustodyError(ValueError):
    pass

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as reader:
        while chunk := reader.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def _identity(st: os.stat_result) -> tuple[int, ...]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)

@contextmanager
def pinned_ext2_snapshot(image: Path, expected_sha256: str):
    """Yield private snapshot and digest; hold on source alias change during audit.

    This does NOT bind a later boot consumer. That consumer must separately
    select immutable verified bytes or independently reverify what it opens.
    """
    image = Path(os.path.abspath(image))
    if (os.name != "posix" or not hasattr(os, "O_NOFOLLOW")
            or len(expected_sha256) != 64
            or any(x not in "0123456789abcdef" for x in expected_sha256)):
        raise ArtifactCustodyError("Linux nofollow and exact lowercase SHA256 required")
    try:
        fd = os.open(image, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        raise ArtifactCustodyError("cannot open selected ext2 without following links") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ArtifactCustodyError("selected ext2 is not a regular file")
        with tempfile.TemporaryDirectory(prefix="veraos-pinned-ext2-") as workdir:
            snapshot = Path(workdir) / "selected.ext2"
            h = hashlib.sha256()
            with os.fdopen(os.dup(fd), "rb", closefd=True) as source, snapshot.open("xb") as output:
                while chunk := source.read(1024 * 1024):
                    h.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            copied = h.hexdigest()
            if (copied != expected_sha256 or _identity(os.fstat(fd)) != _identity(before)
                    or _sha256(snapshot) != copied):
                raise ArtifactCustodyError("selected ext2 changed or digest mismatch during capture")
            try:
                current = os.stat(image, follow_symlinks=False)
            except OSError as exc:
                raise ArtifactCustodyError("selected ext2 pathname disappeared") from exc
            if _identity(current) != _identity(before):
                raise ArtifactCustodyError("selected ext2 pathname changed during capture")
            try:
                yield snapshot, {"image_sha256": copied, "image_bytes": before.st_size}
            finally:
                try:
                    current = os.stat(image, follow_symlinks=False)
                    if (_identity(current) != _identity(before)
                            or _identity(os.fstat(fd)) != _identity(before)
                            or _sha256(snapshot) != copied):
                        raise ArtifactCustodyError("selected ext2 alias or snapshot changed during verification")
                except OSError as exc:
                    raise ArtifactCustodyError("selected ext2 disappeared during verification") from exc
    finally:
        os.close(fd)

MAX_SEALED_IMAGE_BYTES = 128 * 1024 * 1024

@contextmanager
def pinned_sealed_ext2(image: Path, expected_sha256: str):
    """Yield kernel-sealed exact bytes to existing debugfs reader via parent FD.

    Holds if more than 128MiB is required, never silently falls back to the
    mutable private path snapshot. This audits ONE captured image, not a later
    OS bootloader or continuously selected source pathname.
    """
    image = Path(os.path.abspath(image))
    if (os.name != "posix" or not hasattr(os, "memfd_create")
            or not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "MFD_ALLOW_SEALING")
            or len(expected_sha256) != 64
            or any(x not in "0123456789abcdef" for x in expected_sha256)):
        raise ArtifactCustodyError("Linux sealed memfd and lowercase SHA256 required")
    import fcntl  # Linux-only; module can still be imported on Windows for source inspection.
    required = (fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW |
                fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
    try:
        source_fd = os.open(image, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        raise ArtifactCustodyError("cannot open selected ext2 without following links") from exc
    try:
        before = os.fstat(source_fd)
        if not stat.S_ISREG(before.st_mode):
            raise ArtifactCustodyError("selected ext2 is not a regular file")
        if before.st_size <= 0 or before.st_size > MAX_SEALED_IMAGE_BYTES:
            raise ArtifactCustodyError("selected ext2 exceeds sealed image size limit")
        memfd = os.memfd_create("veraos-verified-ext2",
                               os.MFD_ALLOW_SEALING | getattr(os, "MFD_CLOEXEC", 0))
        try:
            h = hashlib.sha256()
            with os.fdopen(os.dup(source_fd), "rb", closefd=True) as source:
                while chunk := source.read(1024 * 1024):
                    h.update(chunk)
                    remaining = memoryview(chunk)
                    while remaining:
                        count = os.write(memfd, remaining)
                        if count <= 0:
                            raise ArtifactCustodyError("failed to copy ext2 into sealed descriptor")
                        remaining = remaining[count:]
            copied = h.hexdigest()
            if (copied != expected_sha256 or os.fstat(memfd).st_size != before.st_size
                    or _identity(os.fstat(source_fd)) != _identity(before)):
                raise ArtifactCustodyError("selected ext2 changed or digest mismatch during capture")
            try:
                current = os.stat(image, follow_symlinks=False)
            except OSError as exc:
                raise ArtifactCustodyError("selected ext2 pathname disappeared") from exc
            if _identity(current) != _identity(before):
                raise ArtifactCustodyError("selected ext2 alias changed during capture")
            fcntl.fcntl(memfd, fcntl.F_ADD_SEALS, required)
            if fcntl.fcntl(memfd, fcntl.F_GET_SEALS) != required:
                raise ArtifactCustodyError("ext2 descriptor missing kernel write seals")
            # Independent byte readback of the SEALED inode, not the original alias.
            check = hashlib.sha256()
            offset = 0
            while offset < before.st_size:
                block = os.pread(memfd, min(1024 * 1024, before.st_size-offset), offset)
                if not block:
                    raise ArtifactCustodyError("sealed ext2 unexpectedly truncated")
                check.update(block)
                offset += len(block)
            if check.hexdigest() != copied:
                raise ArtifactCustodyError("sealed ext2 byte readback differs from captured source")
            ref = Path(f"/proc/{os.getpid()}/fd/{memfd}")
            try:
                yield ref, {"image_sha256": copied, "image_bytes": before.st_size,
                            "seals_applied": True, "same_uid_pathname_immutable": False}
            finally:
                try:
                    current = os.stat(image, follow_symlinks=False)
                    if (_identity(current) != _identity(before)
                            or _identity(os.fstat(source_fd)) != _identity(before)
                            or fcntl.fcntl(memfd, fcntl.F_GET_SEALS) != required):
                        raise ArtifactCustodyError("selected ext2 alias or descriptor changed during audit")
                except OSError as exc:
                    raise ArtifactCustodyError("selected ext2 pathname unavailable after audit") from exc
        finally:
            os.close(memfd)
    finally:
        os.close(source_fd)

def verify_pinned(image: Path, stage: Path, source_root: Path, expected_sha256: str):
    """Invoke VeraOS #40 ext2 reader and full resident-stage verifier unchanged."""
    source_root = Path(source_root).resolve(strict=True)
    path = source_root / "tools/vm/Verify-VeraOSResidentFiles.py"
    spec = importlib.util.spec_from_file_location("veraos_resident_pinned", path)
    if spec is None or spec.loader is None:
        raise ArtifactCustodyError("resident verifier unavailable")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    with pinned_sealed_ext2(image, expected_sha256) as (sealed, identity):
        rootfs = verifier._rootfs("ext2", image, source_root)
        # Reuse the exact #40 parser; its debugfs calls now all reopen the
        # immutable kernel memfd inode, never a mutable copied pathname.
        rootfs.image = sealed
        result = verifier.verify_image(stage, source_root, rootfs)
    return {**result, **identity, "artifact_custody": "SEALED_MEMFD_FOR_THIS_AUDIT_ONLY",
            "selected_source_path_continuity_qualified": False,
            "later_boot_consumer_qualified": False}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ext2", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    report = verify_pinned(args.ext2, args.stage, args.repo_root, args.expected_sha256)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ArtifactCustodyError, OSError, ValueError) as exc:
        print("VERAOS_PINNED_EXT2_HOLD: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
