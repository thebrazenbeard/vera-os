#!/usr/bin/env python3
"""Build a read-only offline portfolio ext4 filesystem *file*, never touch a disk.

Sensitive output: includes all private owned repository source bundles.
Requires previously verified 90-repository Git snapshot, mkfs.ext4 and debugfs.
The image is supplementary data, not an executable VeraOS installation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().with_name("Freeze-VeraPortfolio.py")
SPEC = importlib.util.spec_from_file_location("vera_offline_snapshot", SOURCE)
freeze = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(freeze)

MIB = 1024 * 1024
SEGMENT = 64 * MIB
LABEL = "VERAOFFLINE"


class VolumeError(ValueError):
    pass


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(MIB), b""):
            h.update(block)
    return h.hexdigest()


def _execute(*cmd: str, timeout: int = 360) -> None:
    try:
        result = subprocess.run(list(cmd), capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VolumeError(f"Image tool unavailable or timed out: {cmd[0]}") from exc
    if result.returncode:
        raise VolumeError(f"Image tool failed ({result.returncode}): {cmd[0]}")


def geometry(total_bytes: int) -> int:
    if type(total_bytes) is not int or total_bytes < 1:
        raise VolumeError("Invalid bundle byte total")
    return max(256 * MIB, math.ceil((total_bytes * 1.25 + 128 * MIB) / SEGMENT) * SEGMENT)


def _require_snapshot(source: Path, inventory: Path) -> tuple[dict, dict]:
    if source.is_symlink() or not source.is_dir():
        raise VolumeError("Offline bundle source must be a directory, not a symlink")
    index = freeze.census(inventory)
    outcome = freeze.run(inventory, source, verify_only=True)
    if outcome["status"] != "ALL_REPOSITORIES_BYTES_VERIFIED_SOURCE_ONLY":
        raise VolumeError("All 90 source bundles must verify before image build")
    summary_path = source / "portfolio-snapshot-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for key in ("schema", "status", "repo_total", "repo_verified", "private_verified",
                "archived_verified", "total_bundle_bytes"):
        if summary.get(key) != outcome.get(key):
            raise VolumeError("The final on-disk snapshot summary is stale")
    allowed = {"bundles", "receipts", "portfolio-snapshot-summary.json"}
    if {x.name for x in source.iterdir()} != allowed:
        raise VolumeError("Unexpected top-level files in the offline vault")
    expected_bundles = {x["bundle"] for x in (freeze._verify_one(source, row) for row in index["repositories"])}
    expected_receipts = {freeze._slug(row) + ".json" for row in index["repositories"]}
    if {x.name for x in (source / "bundles").iterdir()} != expected_bundles or \
       {x.name for x in (source / "receipts").iterdir()} != expected_receipts:
        raise VolumeError("Offline vault file census mismatch")
    if any(x.is_symlink() for x in source.rglob("*")):
        raise VolumeError("Offline vault contains a link")
    return outcome, index


def _verified_image_bundle(image: Path, virtual_path: str, expected: str, extracted: Path) -> bool:
    # Virtual names are solely derived from validated slug + pinned SHA.
    if not re.fullmatch(r"/bundles/[a-zA-Z0-9_.-]+\.bundle", virtual_path):
        raise VolumeError("Unsafe image path")
    _execute("debugfs", "-R", "dump " + virtual_path + " " + str(extracted), str(image), timeout=90)
    return extracted.is_file() and _digest(extracted) == expected


def package(vault: Path, inventory: Path, output: Path, *, verify_all_inside: bool = True) -> dict:
    vault = vault.resolve(strict=True)
    inventory = inventory.resolve(strict=True)
    output = output.absolute()
    if output.suffix != ".ext4":
        raise VolumeError("Output must have .ext4 suffix")
    if output.exists() or output.is_symlink() or output.with_suffix(".ext4.receipt.json").exists():
        raise FileExistsError("Refuse to overwrite existing volume or receipt")
    if output == vault or vault in output.parents or output == inventory or inventory in output.parents:
        raise VolumeError("Output must be outside input paths")
    for command in ("mkfs.ext4", "debugfs"):
        if shutil.which(command) is None:
            raise VolumeError("Missing required image tool: " + command)
    overview, index = _require_snapshot(vault, inventory)
    image_bytes = geometry(overview["total_bundle_bytes"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".vera-offline-vol-", dir=output.parent) as tmp:
        tmp_path = Path(tmp)
        staged = tmp_path / "staged"
        (staged / "bundles").mkdir(parents=True)
        (staged / "receipts").mkdir()
        shutil.copyfile(vault / "portfolio-snapshot-summary.json", staged / "portfolio-snapshot-summary.json")
        receipts = []
        for row in index["repositories"]:
            data = freeze._verify_one(vault, row)
            receipts.append(data)
            shutil.copyfile(vault / "bundles" / data["bundle"], staged / "bundles" / data["bundle"])
            shutil.copyfile(vault / "receipts" / (freeze._slug(row) + ".json"),
                            staged / "receipts" / (freeze._slug(row) + ".json"))
        # Recheck source during staged copy and the staged files independently
        # before invoking the image tool.
        _require_snapshot(vault, inventory)
        for receipt in receipts:
            if _digest(staged / "bundles" / receipt["bundle"]) != receipt["sha256"]:
                raise VolumeError("Staged bundle does not match its hash")
        raw = tmp_path / "offline-portfolio.ext4"
        with raw.open("wb") as stream:
            stream.truncate(image_bytes)
        _execute("mkfs.ext4", "-F", "-q", "-L", LABEL, "-m", "0",
                 "-d", str(staged), str(raw), timeout=600)
        with raw.open("rb") as stream:
            stream.seek(1080)
            if stream.read(2) != b"\x53\xef":
                raise VolumeError("Image tool did not produce ext-family superblock")
        checked = 0
        with tempfile.TemporaryDirectory(prefix="check-", dir=tmp_path) as check_dir:
            for data in receipts if verify_all_inside else (
                receipts[0], next(x for x in receipts if x["private"]), receipts[-1]
            ):
                target = Path(check_dir) / "verified.bundle"
                if target.exists():
                    target.unlink()
                if not _verified_image_bundle(raw, "/bundles/" + data["bundle"], data["sha256"], target):
                    raise VolumeError("Copied ext4 image does not contain matching bundle")
                checked += 1
        os.link(raw, output)  # same-file-system no-clobber final publication
    report = {
        "schema": "VERA_OS_OFFLINE_PORTFOLIO_EXT4_IMAGE_RECEIPT_V1",
        "status": "STATIC_EXT4_BUNDLES_VERIFIED_NOT_GUEST_MOUNT_QUALIFIED",
        "image": str(output),
        "label": LABEL,
        "sha256": _digest(output),
        "bytes": output.stat().st_size,
        "bundle_count": overview["repo_verified"],
        "private_repos_present": overview["private_verified"],
        "archived_repos_present": overview["archived_verified"],
        "bundle_bytes": overview["total_bundle_bytes"],
        "bundles_read_back_from_ext4": checked,
        "all_bundle_bytes_read_back": checked == overview["repo_verified"],
        "is_bootable": False,
        "guest_mount_qualified": False,
        "resident_runtime_qualified": False,
        "dependencies_and_model_weights_included": False,
        "private_data_do_not_publish": True,
        "protected_effect_authority": False,
    }
    receipt_path = output.with_suffix(".ext4.receipt.json")
    with receipt_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--inventory", type=Path, default=freeze.DEFAULT_INVENTORY)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sample-readback-only", action="store_true")
    args = parser.parse_args()
    result = package(args.vault, args.inventory, args.output,
                     verify_all_inside=not args.sample_readback_only)
    print(json.dumps(result, indent=2, sort_keys=True))
