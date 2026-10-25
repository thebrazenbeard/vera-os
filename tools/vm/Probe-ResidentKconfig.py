#!/usr/bin/env python3
"""Verify exact pinned VeraOS Buildroot external bytes and resolved Kconfig.

SOURCE+EFFECTIVE_KCONFIG evidence only. Never builds, imports target code,
installs, boots a guest, attests a provider, or grants effect permission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

class KconfigHold(ValueError):
    """Refuse promotion when even one source/config precondition is missing."""

_SYMBOL = re.compile(r"^(BR2_[A-Za-z0-9_]+)=(.*)$")
_NOT_SET = re.compile(r"^# (BR2_[A-Za-z0-9_]+) is not set$")
_SHA1 = re.compile(r"^[a-f0-9]{40}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_EXT_REF = "$(BR2_EXTERNAL_VERAOS_PATH)/"

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()

def _parse(path: Path) -> dict[str,str]:
    result = {}
    for index, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        s = _SYMBOL.fullmatch(raw)
        n = _NOT_SET.fullmatch(raw)
        if s:
            key, value = s.groups()
        elif n:
            key, value = n.group(1), "n"
        elif raw.startswith("BR2_"):
            raise KconfigHold(f"malformed Kconfig line {index}")
        else:
            continue
        if key in result:
            raise KconfigHold(f"duplicate Kconfig symbol {key} at line {index}")
        result[key] = value
    if not result:
        raise KconfigHold("empty Kconfig")
    return result

def _safe_external_file(root: Path, filename: str) -> Path:
    path = Path(filename)
    if path.is_absolute() or ".." in path.parts or "\\" in filename or not filename:
        raise KconfigHold("external source path traversal rejected")
    candidate = root/path
    if candidate.is_symlink() or not candidate.is_file():
        raise KconfigHold("missing or symlinked external Git source " + filename)
    if not candidate.resolve().is_relative_to(root):
        raise KconfigHold("external source escapes root")
    return candidate

def _external_reference(root: Path, effective: dict[str,str], key: str, kind: str) -> str:
    val = effective.get(key, "")
    if not val.startswith('"'+_EXT_REF) or not val.endswith('"'):
        raise KconfigHold(f"unbound external path {key}")
    relative = val[1:-1][len(_EXT_REF):]
    if not relative or relative.startswith("/") or "\\" in relative or ".." in relative.split("/"):
        raise KconfigHold(f"unsafe external path {key}")
    p = root/relative
    if p.is_symlink() or not p.resolve().is_relative_to(root):
        raise KconfigHold(f"external path escapes source {key}")
    if kind == "dir":
        if not p.is_dir():
            raise KconfigHold(f"external directory missing {key}")
    elif kind == "executable":
        if not p.is_file() or not os.access(p, os.X_OK):
            raise KconfigHold(f"external script not executable {key}")
    else:
        raise KconfigHold(f"unknown external path requirement {key}")
    return relative

def audit(manifest_path: Path, external_root: Path, effective_config: Path,
          upstream_archive: Path) -> dict:
    pins = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if pins.get("schema") != "VERAOS_BUILDROOT_KCONFIG_PINNED_INPUTS_V1":
        raise KconfigHold("unsupported Kconfig pinned input schema")
    root = Path(external_root).resolve(strict=True)
    if not root.is_dir():
        raise KconfigHold("missing BR2_EXTERNAL directory")
    source_sha = pins.get("upstream_archive_sha256", "")
    if not isinstance(source_sha, str) or not _SHA256.fullmatch(source_sha):
        raise KconfigHold("invalid upstream Buildroot archive digest")
    if _sha256_file(Path(upstream_archive)) != source_sha:
        raise KconfigHold("Buildroot archive SHA256 mismatch")
    blobs = pins.get("external_git_blob_sha1")
    if not isinstance(blobs, dict) or not blobs:
        raise KconfigHold("missing source Git blob manifest")
    for filename, want in sorted(blobs.items()):
        if not isinstance(want, str) or not _SHA1.fullmatch(want):
            raise KconfigHold("invalid Git blob reference")
        if _git_blob_sha1(_safe_external_file(root, filename)) != want:
            raise KconfigHold("Git blob mismatch " + filename)
    defconfig = pins.get("defconfig")
    if defconfig not in blobs:
        raise KconfigHold("unbound selected defconfig")
    requested = _parse(_safe_external_file(root, defconfig))
    resolved = _parse(Path(effective_config))
    for key, want in requested.items():
        got = resolved.get(key, "<missing>")
        if got != want:
            raise KconfigHold(f"requested Kconfig {key} expected {want} got {got}")
    required = pins.get("required_effective_symbols")
    if not isinstance(required, list) or not required:
        raise KconfigHold("missing mandatory Kconfig profile")
    for key in required:
        if not isinstance(key, str) or not key.startswith("BR2_") or resolved.get(key) != "y":
            raise KconfigHold(f"mandatory Kconfig {key} not selected")
    paths = pins.get("external_paths")
    if not isinstance(paths, dict) or not paths:
        raise KconfigHold("missing external source paths")
    referenced = {key: _external_reference(root, resolved, key, kind)
                  for key, kind in sorted(paths.items())}
    return {
        "schema":"VERAOS_PINNED_EFFECTIVE_KCONFIG_PROBE_V1",
        "status":"PINNED_KCONFIG_RESOLVED_SOURCE_ONLY",
        "source_head":pins["veraos_reviewed_source_head"],
        "buildroot_source_commit":pins["buildroot_source_commit"],
        "buildroot_archive_sha256":source_sha,
        "selected_defconfig_git_blob_sha1":blobs[defconfig],
        "effective_config_sha256":_sha256_file(Path(effective_config)),
        "external_file_git_blobs_verified":len(blobs),
        "requested_symbols_retained":len(requested),
        "required_selected_symbols":len(required),
        "external_path_members_verified":referenced,
        "target_toolchain_built":False,
        "target_python_import_executed":False,
        "target_elf_closure_executed":False,
        "rootfs_or_image_built":False,
        "image_built":False,
        "normal_cog_graphical_boot_observed":False,
        "two_cold_boots_observed":False,
        "model_provider_admitted":False,
        "protected_effect_authority":False,
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pinned-inputs",type=Path,required=True)
    parser.add_argument("--br2-external",type=Path,required=True)
    parser.add_argument("--effective-config",type=Path,required=True)
    parser.add_argument("--upstream-source-archive",type=Path,required=True)
    args=parser.parse_args()
    try:
        result=audit(args.pinned_inputs,args.br2_external,args.effective_config,
                     args.upstream_source_archive)
    except (KconfigHold,OSError,ValueError,KeyError,TypeError) as exc:
        print("VERAOS_EFFECTIVE_KCONFIG_HOLD: "+str(exc),file=sys.stderr)
        return 2
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
