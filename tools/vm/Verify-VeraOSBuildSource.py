#!/usr/bin/env python3
"""Bind the completed VeraOS image source separately from qualification tooling.

The immutable resident image was built at a prior exact Git head. A later
qualification branch may add test/audit code but cannot retroactively claim
its own commit was the builder input.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

IMAGE_HEAD = "a2a91017876df7ca1677ad4afefd7b45dd80165f"
ALLOWED_QUALIFICATION_FILES = frozenset({
    "tools/vm/Finalize-VeraOSResidentBuild.ps1",
    "tools/vm/Verify-VeraOSResidentFiles.py",
    "tools/vm/Verify-VeraOSBuildSource.py",
    "tools/vm/Test-VeraOSVm.ps1",
    "tests/test_resident_all_file_audit.py",
    "tests/test_resident_qualification_contract.py",
    "tests/test_veraos_image_source_binding.py",
    "tests/test_vm_contract.py",
})


class ImageSourceError(ValueError):
    pass


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=False, timeout=20,
    )
    if result.returncode:
        raise ImageSourceError(
            f"Git {' '.join(args)} failed: {result.stderr.strip()[:320]}"
        )
    return result.stdout.strip()


def validate_image_source(repo: Path, source_head: str = IMAGE_HEAD) -> dict:
    repo = Path(repo).resolve(strict=True)
    if source_head != IMAGE_HEAD:
        raise ImageSourceError("Unknown resident image build source head")
    head = git(repo, "rev-parse", "HEAD")
    if len(head) != 40:
        raise ImageSourceError("Invalid qualification Git revision")
    if git(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ImageSourceError("Qualification Git checkout is dirty")
    git(repo, "merge-base", "--is-ancestor", IMAGE_HEAD, head)
    delta = git(repo, "diff", "--no-renames", "--name-status", IMAGE_HEAD, head)
    changes = []
    for line in delta.splitlines():
        columns = line.split("\t")
        if len(columns) != 2:
            raise ImageSourceError("Unexpected Git delta record")
        action, path = columns
        if action not in {"A", "M"} or path not in ALLOWED_QUALIFICATION_FILES:
            raise ImageSourceError(
                "Qualification branch changed image build source: " + line
            )
        changes.append(path)
    if not changes:
        raise ImageSourceError("No independent qualification tooling present")
    if "tools/vm/Verify-VeraOSBuildSource.py" not in changes:
        raise ImageSourceError("Source-binding validator is not pinned")
    return {
        "schema": "VERA_OS_IMAGE_SOURCE_QUALIFICATION_BINDING_V1",
        "image_build_source_head": IMAGE_HEAD,
        "qualification_tool_head": head,
        "image_source_unchanged_since_build": True,
        "qualification_checkout_clean": True,
        "qualification_only_changed_paths": sorted(changes),
        "native_host_install_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--image-source-head", required=True)
    args = parser.parse_args()
    print(json.dumps(validate_image_source(
        args.repo_root, args.image_source_head,
    ), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ImageSourceError, OSError) as error:
        import sys
        print("VERAOS_SOURCE_BINDING_HOLD: " + str(error), file=sys.stderr)
        raise SystemExit(2)
