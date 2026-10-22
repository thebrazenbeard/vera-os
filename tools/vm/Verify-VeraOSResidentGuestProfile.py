#!/usr/bin/env python3
"""Validate the opt-in 2025 resident GUEST source profile; never select an OS image."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class ResidentGuestProfileError(ValueError):
    pass


def require(condition: bool, label: str) -> None:
    if not condition:
        raise ResidentGuestProfileError(label)


def validate_guest_profile(
    profile: dict, candidate: dict, legacy: dict, receipt_bytes: bytes
) -> dict[str, object]:
    require(profile.get("schema") == "VERA_OS_RESIDENT_GUEST_PROFILE_V1", "wrong profile schema")
    require(profile.get("scope") == "OPT_IN_BUILDROOT_RESIDENT_GUEST_NOT_PRIMARY_OS_HOST",
            "invalid guest-only scope")
    require(profile.get("status") == "SOURCE_PROFILE_ONLY_NOT_PACKED_OR_BOOTED",
            "unsupported profile readiness")
    builder = profile["builder"]
    choice = candidate["candidate"]
    require(choice["version"] == "2025.02.18"
            and choice["peeled_git_commit"] == "d030e36bbc9669230c015be971b14b6e062cfdde",
            "unrecognized selected Buildroot source")
    for k, v in (("version", "version"),
                 ("peeled_git_commit", "peeled_git_commit"),
                 ("annotated_tag_sha", "annotated_tag_object_sha"),
                 ("source_defconfig", "source_defconfig")):
        require(builder[k] == choice[v], "2025 builder source mismatch: " + k)
    require(builder["name"] == "Buildroot", "unsupported builder")
    require(profile["target_python"]["version"] == choice["target_python_expected"]
            and profile["target_python"]["abi"] == "python3.12"
            and profile["target_python"]["guest_imports_verified"] is False,
            "target Python profile mismatch")
    historical = legacy["product"]
    anchor = profile["historical_boot_contract"]
    require(historical["image_builder_version"] == "2024.02.4"
            and historical["image_builder_commit"] == "e0a2687421a4f93e65aa00a30bcb0b4817f7a195"
            and anchor["builder_version"] == historical["image_builder_version"]
            and anchor["builder_commit"] == historical["image_builder_commit"]
            and anchor["scope"] == "HISTORICAL_BASELINE_ONLY",
            "historical boot contract must stay historical")
    require(profile["product_primary_host"] ==
            {"nixos": "CANDIDATE_UNRESOLVED", "guest_profile_does_not_choose_host": True},
            "guest profile must not decide primary host")
    require(profile["proof"] == {
        "actual_buildroot_output_image_sha256": None,
        "actual_buildroot_output_bytes": None,
        "selected_final_image": False, "booted_guest": False,
        "qualified_vera_runtime_consumed": False,
        "external_effect_authority": False,
    }, "source profile cannot assert output/guest/runtime/effect proof")
    selected = profile["selected_stage"]
    actual_hash = hashlib.sha256(receipt_bytes).hexdigest()
    require(selected["schema"] == "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1"
            and selected["receipt_sha256"] ==
            "6f0031c1fcbaed41e4e3f6947e90a92ed5656ac3e09329de7d8e0b0f8417eca5"
            and actual_hash == selected["receipt_sha256"], "resident source receipt digest mismatch")
    receipt = json.loads(receipt_bytes)
    require(receipt["schema"] == selected["schema"] and receipt["authority"] is False,
            "resident stage has inappropriate authority")
    heads = {}
    paths = set()
    file_total = 0
    for row in receipt["components"]:
        name = row["repository"]
        require(name not in heads, "duplicate component")
        heads[name] = row["source_head"]
        require(row["file_count"] == len(row["files"]), "component count mismatch")
        for file in row["files"]:
            require(file["path"] not in paths, "duplicate resident source member")
            paths.add(file["path"])
            file_total += 1
    require(heads == {
        "thebrazenbeard/vera-mono": "89ba1d18da78e7e38f015cf8d8ef4f528aae9df8",
        "thebrazenbeard/portal": "36fa04da4e5eb383fecf463c72a43b94ca47d7e5",
        "thebrazenbeard/pre-active": "1f23a809d7274df506e03e2d9052525538c3bcf6",
        "thebrazenbeard/volition": "dbc628d376515a0a523b1eecdf62129cca5d6b08",
    } == selected["component_heads"], "frozen source heads mismatch")
    require(file_total == 431 == selected["file_count"], "wrong source member count")
    return {
        "status": "SOURCE_PROFILE_MATCH_ONLY", "builder": "2025.02.18",
        "receipt_sha256": actual_hash, "source_members": file_total,
        "selected_final_image": False, "booted_guest": False,
        "qualified_vera_runtime_consumed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.repo_root
    def read(path: str) -> dict:
        return json.loads((root / path).read_text(encoding="utf-8"))
    result = validate_guest_profile(
        read("architecture/os/VERA_OS_RESIDENT_GUEST_PROFILE_V1.json"),
        read("architecture/os/VERA_OS_RESIDENT_BUILDROOT_CANDIDATE_V1.json"),
        read("architecture/os/VERA_OS_BOOT_CONTRACT_V1.json"),
        (args.stage / "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json").read_bytes(),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResidentGuestProfileError, KeyError, ValueError, OSError) as error:
        import sys
        print("VERA_OS_RESIDENT_GUEST_PROFILE_HOLD: " + str(error), file=sys.stderr)
        raise SystemExit(2)
