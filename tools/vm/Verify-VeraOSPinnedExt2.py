#!/usr/bin/env python3
"""Audit a private exact-byte ext2 snapshot, not a mutable path alias.

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

def verify_pinned(image: Path, stage: Path, source_root: Path, expected_sha256: str):
    """Invoke VeraOS #40 ext2 reader and full resident-stage verifier unchanged."""
    source_root = Path(source_root).resolve(strict=True)
    path = source_root / "tools/vm/Verify-VeraOSResidentFiles.py"
    spec = importlib.util.spec_from_file_location("veraos_resident_pinned", path)
    if spec is None or spec.loader is None:
        raise ArtifactCustodyError("resident verifier unavailable")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    with pinned_ext2_snapshot(image, expected_sha256) as (snapshot, identity):
        rootfs = verifier._rootfs("ext2", snapshot, source_root)
        result = verifier.verify_image(stage, source_root, rootfs)
    return {**result, **identity, "artifact_custody": "PINNED_FOR_THIS_AUDIT_ONLY",
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
