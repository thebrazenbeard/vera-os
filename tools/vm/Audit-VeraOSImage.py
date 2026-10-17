#!/usr/bin/env python3
"""Read-only source-vs-rootfs audit; never confuse portfolio awareness with installed Vera runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
from veraos.composition import validate_manifest
from veraos.portfolio_awareness import validate_capability_map
from veraos.portfolio_implementation import validate_implementation_plan


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class AuditError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise AuditError(f"JSON must be an object: {path}")
    return obj


class DirectoryRootfs:
    def __init__(self, path: Path):
        self.root = path.resolve(strict=True)
        if not self.root.is_dir():
            raise AuditError("rootfs directory does not exist")

    def read(self, virtual_path: str) -> bytes | None:
        if not virtual_path.startswith("/") or ".." in virtual_path.split("/"):
            raise AuditError("invalid rootfs path")
        path = (self.root / virtual_path.lstrip("/")).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            return None
        return path.read_bytes()

    def symlink_target(self, virtual_path: str) -> str | None:
        path = self.root / virtual_path.lstrip("/")
        return path.readlink().as_posix() if path.is_symlink() else None

    def component_files(self) -> set[str]:
        base = self.root / "opt/veraos/components"
        if not base.is_dir() or base.is_symlink():
            raise AuditError("resident component directory missing or linked")
        found: set[str] = set()
        for file in base.rglob("*"):
            if file.is_symlink() or (not file.is_file() and not file.is_dir()):
                raise AuditError("unsupported or linked resident component path")
            if file.is_file():
                if not file.resolve().is_relative_to(base):
                    raise AuditError("resident source path escapes component tree")
                found.add("components/" + file.relative_to(base).as_posix())
        if not found:
            raise AuditError("resident component tree is empty")
        return found


class ExtRootfs:
    def __init__(self, path: Path):
        self.image = path.resolve(strict=True)
        if not self.image.is_file():
            raise AuditError("rootfs image does not exist")

    @staticmethod
    def _safe_path(virtual_path: str) -> None:
        if not re.fullmatch(r"/[A-Za-z0-9_./-]+", virtual_path) or ".." in virtual_path.split("/"):
            raise AuditError("invalid rootfs path")

    def _debugfs(self, command: str) -> tuple[bytes, bytes]:
        try:
            completed = subprocess.run(
                ["debugfs", "-R", command, str(self.image)],
                capture_output=True,
                timeout=25,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AuditError(f"debugfs unavailable or timed out: {exc}") from exc
        if completed.returncode != 0:
            raise AuditError(f"debugfs failed: {completed.stderr.decode(errors='replace')[:250]}")
        return completed.stdout, completed.stderr

    def read(self, virtual_path: str) -> bytes | None:
        self._safe_path(virtual_path)
        out, err = self._debugfs("cat " + virtual_path)
        if b"File not found" in err or b"File not found" in out or b"not found by ext2_lookup" in err:
            return None
        return out

    def component_files(self) -> set[str]:
        """Enumerate entire ext2 resident tree using bounded, parseable debugfs.

        Enumeration is necessary: matching expected hashes alone permits stale
        import-shadowing files. No unverified listing can qualify image closure.
        """
        base = "/opt/veraos/components"
        pending = [base]
        visited: set[str] = set()
        found: set[str] = set()
        while pending:
            directory = pending.pop()
            if directory in visited or len(visited) >= 2048:
                raise AuditError("repeated or excessive ext2 resident directories")
            visited.add(directory)
            self._safe_path(directory)
            out, err = self._debugfs("ls -p " + directory)
            if (not out or len(out) > 1024 * 1024
                    or b"File not found" in out + err
                    or b"not found by ext2_lookup" in out + err
                    or b"not a directory" in out.lower() + err.lower()):
                raise AuditError("missing or incomplete ext2 resident directory listing")
            names: set[str] = set()
            for raw in out.splitlines():
                fields = raw.split(b"/")
                if (len(fields) != 8 or fields[0] != b"" or fields[-1] != b""
                        or any(re.fullmatch(rb"[0-9]+", f) is None
                               for f in (fields[1], fields[3], fields[4], fields[6]))
                        or re.fullmatch(rb"[0-7]{5,6}", fields[2]) is None):
                    raise AuditError("malformed ext2 debugfs -p directory entry")
                try:
                    name = fields[5].decode("ascii")
                except UnicodeDecodeError as exc:
                    raise AuditError("unverifiable ext2 source entry name") from exc
                if name in (".", ".."):
                    continue
                if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
                    raise AuditError("unsafe ext2 resident component name")
                if name in names:
                    raise AuditError("duplicate ext2 resident component name")
                names.add(name)
                item = directory + "/" + name
                self._safe_path(item)
                mode = int(fields[2], 8) & 0o170000
                if mode == 0o040000:
                    pending.append(item)
                elif mode == 0o100000:
                    found.add("components/" + item[len(base) + 1:])
                else:
                    # Symlinks, devices and sockets can shadow expected code.
                    raise AuditError("unsupported ext2 resident component inode")
                if len(found) + len(pending) + len(visited) > 8192:
                    raise AuditError("ext2 resident tree exceeds source closure bound")
        if not found:
            raise AuditError("ext2 resident source enumeration empty")
        return found

    def symlink_target(self, virtual_path: str) -> str | None:
        self._safe_path(virtual_path)
        out, err = self._debugfs("stat " + virtual_path)
        if b"File not found" in out + err:
            return None
        match = re.search(rb'Fast link dest: "([^"]+)"', out)
        return match.group(1).decode("ascii") if match else None


def python_version(rootfs: DirectoryRootfs | ExtRootfs, marker: str) -> tuple[int, int] | None:
    link = rootfs.symlink_target(marker)
    if not link:
        return None
    match = re.search(r"python(\d+)\.(\d+)", link)
    return (int(match.group(1)), int(match.group(2))) if match else None


def audit(
    rootfs: DirectoryRootfs | ExtRootfs,
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    cpath = repo_root / "architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json"
    apath = repo_root / "architecture/capabilities/VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json"
    ppath = repo_root / "architecture/portfolio/VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json"
    rpath = repo_root / "architecture/os/VERA_OS_CORE_IMAGE_CONTENT_REQUIREMENTS_V1.json"

    composition = read_json(cpath)
    capability_map = read_json(apath)
    implementation = read_json(ppath)
    requirements = read_json(rpath)

    validate_manifest(composition)
    validate_capability_map(capability_map)
    validate_implementation_plan(implementation, capability_map, composition)
    if requirements.get("schema") != "VERA_OS_CORE_IMAGE_CONTENT_REQUIREMENTS_V1":
        raise AuditError("unexpected requirements schema")

    by_repo = {r["repository"]: r for r in composition["repositories"]}
    plan_by_repo = {r["repository"]: r for r in implementation["repositories"]}
    marker = requirements["python_runtime_marker"]
    interpreter = python_version(rootfs, marker)
    os_marker = requirements["native_os_marker"]
    os_present = rootfs.read(os_marker) is not None

    source_docs = {
        "composition": cpath,
        "capability_map": apath,
        "implementation": ppath,
    }
    embedded = {}
    for key, host_file in source_docs.items():
        entry = requirements["embedded_catalogs"][key]
        actual = rootfs.read(entry)
        expected = host_file.read_bytes()
        embedded[key] = {
            "present": actual is not None,
            "exact_bytes_match_source": actual == expected if actual is not None else False,
            "source_sha256": digest(expected),
            "image_sha256": digest(actual) if actual is not None else None,
        }

    candidates = []
    for core in requirements["required_components"]:
        repository = core["repository"]
        if repository not in by_repo or repository not in plan_by_repo:
            raise AuditError(f"required core repo missing from source catalog: {repository}")
        if by_repo[repository]["boot_policy"] != "CORE":
            raise AuditError(f"required core boot policy not CORE: {repository}")
        if plan_by_repo[repository]["activation_policy"] != "CORE":
            raise AuditError(f"required core implementation policy not CORE: {repository}")
        target_marker = core["package_marker"]
        exists = rootfs.read(target_marker) is not None
        minimum = tuple(map(int, core["minimum_python"].split(".")))
        abi_ok = interpreter is not None and interpreter >= minimum
        candidates.append({
            "repository": repository,
            "bound_source_head": by_repo[repository]["exact_head"],
            "expected_marker": target_marker,
            "source_file_packaged": exists,
            "python_minimum": core["minimum_python"],
            "image_python_compatible": abi_ok,
            "status": (
                "MISSING_FROM_IMAGE" if not exists else
                "SOURCE_PRESENT_PYTHON_ABI_HOLD" if not abi_ok else
                "SOURCE_PRESENT_RUNTIME_UNQUALIFIED"
            ),
            "resident_running_verified": False,
        })

    # Hash comparison of a real materialization receipt is a separate
    # future gate. Its absence must not be called success.
    receipt_path = "/etc/veraos/architecture/VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json"
    raw_receipt = rootfs.read(receipt_path)
    receipt_state = "ABSENT"
    if raw_receipt is not None:
        receipt_state = "INVALID"
        try:
            receipt = json.loads(raw_receipt)
            records = receipt.get("components")
            if (
                isinstance(receipt, dict)
                and receipt.get("schema") == "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1"
                and receipt.get("authority") is False
                and isinstance(records, list)
                and len(records) == len(candidates)
                and all(isinstance(row, dict) for row in records)
            ):
                by_receipt = {row.get("repository"): row for row in records}
                if len(by_receipt) == len(candidates) and all(
                    item["repository"] in by_receipt
                    and by_receipt[item["repository"]].get("source_head") == item["bound_source_head"]
                    and by_receipt[item["repository"]].get("marker_path") == item["expected_marker"]
                    and isinstance(by_receipt[item["repository"]].get("marker_sha256"), str)
                    and re.fullmatch(r"[0-9a-f]{64}", by_receipt[item["repository"]]["marker_sha256"])
                    and rootfs.read(item["expected_marker"]) is not None
                    and digest(rootfs.read(item["expected_marker"])) == by_receipt[item["repository"]]["marker_sha256"]
                    for item in candidates
                ):
                    receipt_state = "MARKER_HASHES_VALID_NOT_INDEPENDENTLY_ATTESTED"
        except (ValueError, AttributeError, TypeError):
            receipt_state = "INVALID"

    catalog_match = all(item["exact_bytes_match_source"] for item in embedded.values())
    core_source_present = all(item["source_file_packaged"] for item in candidates)
    core_abi = all(item["image_python_compatible"] for item in candidates)
    ready_for_guest_import_tests = (
        os_present and catalog_match and core_source_present and core_abi
        and receipt_state == "MARKER_HASHES_VALID_NOT_INDEPENDENTLY_ATTESTED"
    )
    return {
        "schema": "VERA_OS_IMAGE_MATERIALIZATION_AUDIT_V1",
        "audit_type": "READ_ONLY_STATIC_ROOTFS_EXAMINATION",
        "catalog_total": len(by_repo),
        "catalog_planned_integrated": composition["counts"]["integrated"],
        "catalog_excluded": composition["counts"]["excluded"],
        "catalog_is_implementation": False,
        "native_os_source_present": os_present,
        "embedded_catalogs": embedded,
        "python_version": ".".join(map(str, interpreter)) if interpreter else None,
        "core_components": candidates,
        "resident_receipt_state": receipt_state,
        "ready_for_guest_import_tests": ready_for_guest_import_tests,
        "resident_runtime_qualified": False,
        "p_o_r_t_a_l_route_qualified": False,
        "trained_model_consumption_qualified": False,
        "claim_ceiling": "SOURCE_IMAGE_CONTENT_ONLY_NOT_INSTALLED_RESIDENT_RUNTIME_OR_BEHAVIOR",
        "status": "READY_FOR_GUEST_IMPORT_PROBES_NOT_QUALIFIED" if ready_for_guest_import_tests else "HOLD_INCOMPLETE_IMAGE",
        "protected_effect_authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ext2", type=Path)
    group.add_argument("--rootfs-directory", type=Path)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write-report", type=Path, help="New report path (refuses overwrite)")
    args = parser.parse_args()
    rootfs = ExtRootfs(args.ext2) if args.ext2 else DirectoryRootfs(args.rootfs_directory)
    result = audit(rootfs, args.repo_root)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.write_report:
        with args.write_report.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    print(encoded)
    return 0 if result["ready_for_guest_import_tests"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
