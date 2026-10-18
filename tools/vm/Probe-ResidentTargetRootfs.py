"""Fail-closed static TARGET rootfs prerequisite audit, not a guest import or GUI test.

Called only by the opt-in resident Buildroot post-build step, after the
independent full 431-source-file receipt audit. Never executes guest programs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "VERA_OS_RESIDENT_TARGET_ROOTFS_PREFLIGHT_V1"


class TargetPrerequisiteError(ValueError):
    pass


def audit(rootfs: Path, repo: Path = ROOT) -> dict[str, object]:
    rootfs = rootfs.resolve(strict=True)
    if not rootfs.is_dir():
        raise TargetPrerequisiteError("target rootfs is not a directory")

    def guest_path(guest: str, *, follow_final: bool = False) -> Path:
        """Walk Linux guest symlinks component-wise without visiting host targets.

        Even directory symlinks with absolute targets belong to the *guest*
        namespace. Host Path.resolve() would instead follow /usr/lib -> /lib
        on the workstation and falsely use (or reject) workstation bytes.
        """
        if (not isinstance(guest, str) or not guest.startswith("/")
                or guest.startswith("//") or "\\" in guest or "\0" in guest
                or ".." in guest.split("/")):
            raise TargetPrerequisiteError("target file escapes rootfs: " + str(guest))
        pending = [part for part in guest.split("/") if part and part != "."]
        parts: list[str] = []
        links = 0
        while pending:
            part = pending.pop(0)
            if part == ".":
                continue
            if part == "..":
                if not parts:
                    raise TargetPrerequisiteError("target file escapes rootfs: " + guest)
                parts.pop()
                continue
            # Reject Windows absolute/reparse input even on a Linux builder.
            if ":" in part or "\\" in part:
                raise TargetPrerequisiteError("target file escapes rootfs: " + guest)
            path = rootfs.joinpath(*parts, part)
            if path.is_symlink() and (pending or follow_final):
                links += 1
                if links > 20:
                    raise TargetPrerequisiteError("target symlink chain too long: " + guest)
                target = path.readlink().as_posix()
                if (not target or target.startswith("//") or "\\" in target
                        or "\0" in target):
                    raise TargetPrerequisiteError("target file escapes rootfs: " + guest)
                if target.startswith("/"):
                    parts = []
                pending = [*target.split("/"), *pending]
                continue
            parts.append(part)
        return rootfs.joinpath(*parts)

    def file(guest: str) -> Path:
        # Keep the final link unresolved where its literal target is audited.
        return guest_path(guest)

    def safe_file(guest: str) -> Path | None:
        path = guest_path(guest, follow_final=True)
        return path if path.is_file() else None

    missing: list[str] = []
    def require(guest: str) -> None:
        if safe_file(guest) is None:
            missing.append(guest)

    # Exact selected 2025.02.18 Buildroot Python 3.12.14 major/minor.
    py = file("/usr/bin/python3")
    if not py.is_symlink() or not re.fullmatch(
        r"(?:/usr/bin/)?python3\.12", py.readlink().as_posix()
    ):
        missing.append("/usr/bin/python3 -> python3.12")
    require("/usr/bin/python3.12")
    for name in ("sqlite3/__init__.py", "ssl.py", "json/__init__.py",
                 "http/server.py", "socket.py"):
        require("/usr/lib/python3.12/" + name)
    dyn = guest_path("/usr/lib/python3.12/lib-dynload", follow_final=True)
    for name in ("_sqlite3", "_ssl"):
        found = sorted(dyn.glob(name + "*.so")) if dyn.is_dir() else []
        if not any(safe_file("/" + p.relative_to(rootfs).as_posix())
                   for p in found):
            missing.append("python3.12 extension " + name)
    # Known direct runtime linker inputs for the selected Buildroot profile.
    # This is only a SONAME-presence guard. It does not inspect DT_NEEDED,
    # resolve ABI/transitive dependencies or execute the target extensions.
    for soname in ("libsqlite3.so.0", "libssl.so.3", "libcrypto.so.3"):
        require("/usr/lib/" + soname)
    site = guest_path("/usr/lib/python3.12/site-packages", follow_final=True)
    for package in ("jsonschema", "cryptography", "yaml"):
        if safe_file("/usr/lib/python3.12/site-packages/" +
                     package + "/__init__.py") is None:
            missing.append("python3.12 import " + package)

    require("/usr/bin/cog")
    fonts = guest_path("/usr/share/fonts", follow_final=True)
    matches = sorted(fonts.rglob("DejaVuSans.ttf")) if fonts.is_dir() else []
    if not any(safe_file("/" + p.relative_to(rootfs).as_posix())
               for p in matches):
        missing.append("Cog font asset DejaVuSans.ttf")
    for name in ("pid1.py", "resident.py", "desktop.py"):
        guest = "/opt/veraos/src/veraos/" + name
        require(guest)
        packed = safe_file(guest)
        source = repo / "src/veraos" / name
        if packed is not None and packed.read_bytes() != source.read_bytes():
            missing.append("source mismatch " + guest)
    launch = "/sbin/vera-init"
    require(launch)
    packed = safe_file(launch)
    source = repo / "buildroot/board/veraos/x86_64/rootfs-overlay/sbin/vera-init"
    if packed is not None:
        entry = packed.read_bytes()
        if entry != source.read_bytes() or not (
            entry.startswith(b"#!/usr/bin/python3\n")
            and b"from veraos.pid1 import main" in entry
            and b"raise SystemExit(main())" in entry
        ):
            missing.append("invalid PID1 /sbin/vera-init")
    # Import and window graphics must be witnessed in the guest. Presence only.
    return {
        "schema": SOURCE,
        "status": "TARGET_ROOTFS_STATIC_PRESENT_GUEST_UNQUALIFIED" if not missing
                  else "NOT_READY_MISSING_TARGET_PREREQUISITES",
        "missing": missing,
        "target_python_expected": "3.12.14",
        "target_import_executed": False,
        "pid1_executed": False,
        "cog_rendered": False,
        "image_built_by_this_probe": False,
        "model_activated": False,
        "canonical_memory_mutated": False,
        "protected_effect_authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rootfs-directory", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = audit(args.rootfs_directory, args.repo_root)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if not result["missing"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print("TARGET_ROOTFS_PREFLIGHT_HOLD: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
