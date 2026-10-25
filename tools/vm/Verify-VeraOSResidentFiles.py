#!/usr/bin/env python3
"""Verify every staged resident source byte inside an actual VeraOS rootfs.

This is read-only evidence about image contents, not Python import, resident
processes, model selection, external effects, or an installed operating system.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json"
ROOTFS_RECEIPT = "/etc/veraos/architecture/" + RECEIPT
EXPECTED_COMPONENTS = {
    "thebrazenbeard/vera-mono": "vera_mono",
    "thebrazenbeard/portal": "portal",
    "thebrazenbeard/pre-active": "pre_active",
    "thebrazenbeard/volition": "volition",
}
HEXDIGEST = re.compile(r"[0-9a-f]{64}\Z")


class ResidentIntegrityError(ValueError):
    pass


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ResidentIntegrityError("Cannot load repository-bound audit helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verify_stage(stage: Path, source_root: Path) -> None:
    verifier = _load(
        source_root / "tools/vm/Stage-VeraOSResidentSources.py",
        "veraos_exact_resident_stage",
    )
    verifier.verify_stage(stage, source_root)


def _rootfs(kind: str, path: Path, source_root: Path):
    audit = _load(source_root / "tools/vm/Audit-VeraOSImage.py", "veraos_exact_image_reader")
    return audit.ExtRootfs(path) if kind == "ext2" else audit.DirectoryRootfs(path)


def verify_image(stage: Path, source_root: Path, rootfs) -> dict[str, object]:
    """Require an independently verified source stage and byte-match every image file."""
    stage = Path(stage).resolve(strict=True)
    source_root = Path(source_root).resolve(strict=True)
    _verify_stage(stage, source_root)
    source_receipt = (stage / RECEIPT).read_bytes()
    embedded_receipt = rootfs.read(ROOTFS_RECEIPT)
    if embedded_receipt is None or source_receipt != embedded_receipt:
        raise ResidentIntegrityError("Embedded receipt differs from exact verified source stage")
    record = json.loads(source_receipt)
    rows = record.get("components", [])
    if not isinstance(rows, list) or len(rows) != 4:
        raise ResidentIntegrityError("Expected exactly four resident source component records")
    observed = set()
    expected_files: set[str] = set()
    total = 0
    for row in rows:
        if not isinstance(row, dict) or row.get("repository") not in EXPECTED_COMPONENTS:
            raise ResidentIntegrityError("Unrecognized resident component")
        repo = row["repository"]
        if repo in observed:
            raise ResidentIntegrityError("Duplicate resident repository receipt")
        observed.add(repo)
        prefix = "components/" + EXPECTED_COMPONENTS[repo] + "/"
        files = row.get("files")
        if not isinstance(files, list) or type(row.get("file_count")) is not int or len(files) != row["file_count"]:
            raise ResidentIntegrityError("Invalid resident file inventory count")
        listed = set()
        for item in files:
            if not isinstance(item, dict):
                raise ResidentIntegrityError("Malformed inventory entry")
            relative = item.get("path")
            expected_hash = item.get("sha256")
            if not isinstance(relative, str) or not relative.startswith(prefix) or \
               not re.fullmatch(r"[A-Za-z0-9_./-]+", relative) or ".." in relative.split("/") or \
               relative in listed or not isinstance(expected_hash, str) or not HEXDIGEST.fullmatch(expected_hash):
                raise ResidentIntegrityError("Unsafe or duplicate resident file inventory entry")
            listed.add(relative)
            expected_files.add(relative)
            actual = rootfs.read("/opt/veraos/" + relative)
            if actual is None or hashlib.sha256(actual).hexdigest() != expected_hash:
                raise ResidentIntegrityError("Resident image source byte mismatch: " + relative)
            total += 1
    if observed != set(EXPECTED_COMPONENTS):
        raise ResidentIntegrityError("Missing resident component")
    # Hashing the 431 expected files is insufficient: an ext2 image could
    # additionally contain an older import-shadowing module. Require a
    # complete enumerated component tree on BOTH directory and ext2 readers.
    enumerate_files = getattr(rootfs, "component_files", None)
    if not callable(enumerate_files):
        raise ResidentIntegrityError("Cannot enumerate image component files")
    try:
        actual_files = enumerate_files()
    except (OSError, ValueError) as exc:
        raise ResidentIntegrityError("Cannot enumerate image component files") from exc
    if actual_files != expected_files:
        raise ResidentIntegrityError(
            "Unexpected or missing files in copied resident component tree"
        )
    return {
        "schema": "VERA_OS_RESIDENT_IMAGE_ALL_FILE_AUDIT_V1",
        "status": "ALL_PINNED_SOURCE_FILES_IMAGE_BYTE_MATCH_NOT_RUNTIME_QUALIFIED",
        "resident_repository_count": len(observed),
        "resident_files_verified": total,
        "stage_receipt_sha256": hashlib.sha256(source_receipt).hexdigest(),
        "source_only": True,
        "guest_import_qualified": False,
        "resident_process_qualified": False,
        "offline_model_route_qualified": False,
        "graphical_desktop_qualified": False,
        "protected_effect_authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--ext2", type=Path)
    selector.add_argument("--rootfs-directory", type=Path)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args()
    kind = "ext2" if args.ext2 else "directory"
    reader = _rootfs(kind, args.ext2 or args.rootfs_directory, args.repo_root)
    report = verify_image(args.stage, args.repo_root, reader)
    encoded = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.write_report:
        with args.write_report.open("x", encoding="utf-8") as writer:
            writer.write(encoded)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResidentIntegrityError, OSError, ValueError) as exc:
        print("RESIDENT_IMAGE_AUDIT_HOLD: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
