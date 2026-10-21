#!/usr/bin/env python3
"""Read-only Buildroot SOURCE INPUT preflight; never select a final OS image.

This does not attest host/container/toolchain closure, packer bytes, later
bootloader selection, guest boot, or QualifiedVeraRuntime consumption.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


class BuilderInputHold(ValueError):
    pass


def _git(root: Path, *args: str) -> str:
    run = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                         text=True, check=False, timeout=20)
    if run.returncode:
        raise BuilderInputHold("cannot verify pinned Buildroot Git source: " + " ".join(args))
    return run.stdout.strip()


@dataclass(frozen=True)
class BuilderInputSnapshot:
    source_git_head: str
    annotated_tag_object: str
    tag_peeled_commit: str
    defconfig_sha256: str
    python_version_source: str
    buildroot_source_clean: bool
    selected_stage_receipt_sha256: str
    output_images_present_unqualified: bool
    source_input_status: str = "SOURCE_INPUTS_MATCH_ONLY"
    host_toolchain_provenance_verified: bool = False
    rebuild_reproducible_verified: bool = False
    packed_source_bytes_verified: bool = False
    selected_final_image: bool = False
    bootloader_consumer_verified: bool = False
    booted_guest: bool = False
    qualified_vera_runtime_consumed: bool = False
    authorization_effect: str = "NONE"


def inspect_builder_inputs(
    buildroot_root: Path, veraos_root: Path,
    *, expected_defconfig_sha256: str,
) -> BuilderInputSnapshot:
    profile = json.loads(
        (veraos_root / "architecture/os/VERA_OS_RESIDENT_GUEST_PROFILE_V1.json").read_text())
    if profile.get("schema") != "VERA_OS_RESIDENT_GUEST_PROFILE_V1":
        raise BuilderInputHold("incorrect guest source profile")
    data = profile["builder"]
    if (data["version"] != "2025.02.18"
            or data["peeled_git_commit"] != "d030e36bbc9669230c015be971b14b6e062cfdde"
            or data["annotated_tag_sha"] != "b611e07ef088c70c1e21f77c30872bce97a1f1c2"):
        raise BuilderInputHold("unrecognized selected Buildroot source")
    root = buildroot_root.resolve(strict=True)
    head = _git(root, "rev-parse", "HEAD")
    tag = _git(root, "rev-parse", "refs/tags/2025.02.18^{tag}")
    peeled = _git(root, "rev-parse", "refs/tags/2025.02.18^{commit}")
    dirty = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    if dirty:
        raise BuilderInputHold("Buildroot source checkout is modified or has untracked files")
    if (head != data["peeled_git_commit"] or peeled != head
            or tag != data["annotated_tag_sha"]):
        raise BuilderInputHold("Buildroot source commit or annotated tag mismatch")
    rel = Path(data["source_defconfig"])
    if rel.is_absolute() or ".." in rel.parts:
        raise BuilderInputHold("unsafe defconfig path")
    config = (veraos_root / rel).read_bytes()
    digest = hashlib.sha256(config).hexdigest()
    if (len(expected_defconfig_sha256) != 64
            or digest != expected_defconfig_sha256):
        raise BuilderInputHold("VeraOS source defconfig digest changed")
    mk = (root / "package/python3/python3.mk").read_text()
    major = re.search(r"^PYTHON3_VERSION_MAJOR\s*=\s*([0-9.]+)\s*$", mk, re.M)
    patch = re.search(r"^PYTHON3_VERSION\s*=\s*\$\(PYTHON3_VERSION_MAJOR\)\.([0-9]+)\s*$", mk, re.M)
    if not major or not patch:
        raise BuilderInputHold("Buildroot target Python source version unavailable")
    version = major.group(1) + "." + patch.group(1)
    if version != profile["target_python"]["version"] or version != "3.12.14":
        raise BuilderInputHold("wrong selected Buildroot target Python version")
    receipt = profile["selected_stage"]["receipt_sha256"]
    if receipt != "6f0031c1fcbaed41e4e3f6947e90a92ed5656ac3e09329de7d8e0b0f8417eca5":
        raise BuilderInputHold("unrecognized selected source stage")
    return BuilderInputSnapshot(
        source_git_head=head, annotated_tag_object=tag,
        tag_peeled_commit=peeled, defconfig_sha256=digest,
        python_version_source=version, buildroot_source_clean=True,
        selected_stage_receipt_sha256=receipt,
        output_images_present_unqualified=(root / "output/images").exists(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--buildroot-root", type=Path, required=True)
    parser.add_argument("--veraos-root", type=Path, required=True)
    parser.add_argument("--expected-defconfig-sha256", required=True)
    args = parser.parse_args()
    receipt = inspect_builder_inputs(args.buildroot_root, args.veraos_root,
                                    expected_defconfig_sha256=args.expected_defconfig_sha256)
    print(json.dumps(asdict(receipt), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        import sys
        print("VERAOS_BUILDER_INPUT_HOLD: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
