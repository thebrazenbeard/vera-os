#!/usr/bin/env python3
"""Fail closed if resolved Buildroot configuration drops required resident Python modules.

This checks .config text after olddefconfig. It does NOT attest the origin of
the file or qualify an image, guest import, or deployed runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = "VERA_OS_RESOLVED_PYTHON_STDLIB_FLAGS_V1"
SYMBOL = re.compile(r"BR2_[A-Z0-9_]+\Z")


def verify(config: Path, contract: Path) -> dict[str, object]:
    spec = json.loads(contract.read_text(encoding="utf-8"))
    flags = spec["requires"]["python_stdlib_flags"]
    if not isinstance(flags, list) or not flags or any(
        not isinstance(flag, str) or not SYMBOL.fullmatch(flag) for flag in flags
    ) or len(set(flags)) != len(flags):
        raise ValueError("Invalid resident Python stdlib symbol contract")
    essentials = {"BR2_PACKAGE_PYTHON3_SQLITE", "BR2_PACKAGE_PYTHON3_SSL"}
    if not essentials.issubset(flags):
        raise ValueError("Contract omits required resident Python modules")
    required = ["BR2_PACKAGE_PYTHON3", *flags]
    if len(set(required)) != len(required):
        raise ValueError("Duplicate base Python symbol in resident contract")
    raw = config.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    for flag in required:
        claims = [line for line in lines if (
            line.startswith(flag + "=") or line == f"# {flag} is not set"
        )]
        if claims != [flag + "=y"]:
            raise ValueError(f"Resolved Buildroot {flag} must appear exactly once as =y")
    return {
        "schema": SCHEMA,
        "status": "RESOLVED_STDLIB_CONFIG_READBACK_NOT_IMAGE_QUALIFICATION",
        "config_sha256": hashlib.sha256(raw).hexdigest(),
        "required_symbols": required,
        "image_built": False,
        "resident_runtime_qualified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.config, args.contract)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print("VERAOS_RESOLVED_CONFIG_HOLD: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
