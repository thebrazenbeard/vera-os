#!/usr/bin/env python3
"""Stage exact-pinned resident Vera source packages without training, installation or activation."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = {
    "vera_mono": ("thebrazenbeard/vera-mono", tuple(
        f"packages/{name}/src" for name in (
            "vera_core", "vera_ingest", "rezon", "portfolio_runtime", "vera_runtime",
            "vera_identity", "vera_coordination", "vera_memory", "vera_assurance",
            "vera_pc_connection", "vera_control", "vera_recovery",
        )
    )),
    "portal": ("thebrazenbeard/portal", ("portal", "runner")),
    "pre_active": ("thebrazenbeard/pre-active", ("src/pre_active",)),
    "volition": ("thebrazenbeard/volition", ("src/volition",)),
}
EXTENSIONS = frozenset({".py", ".json", ".yaml", ".yml", ".toml", ".md",
                        ".txt", ".csv", ".sql", ".ini", ".cfg", ".rst"})

# Static source package readiness only. These imports are used by the normal
# resident, not just optional development fixtures. Their path existence does
# not authenticate Python imports inside a Buildroot guest or admit a model.
REQUIRED_RESIDENT_FILES = frozenset({
    "components/vera_mono/packages/vera_core/src/vera_core/__init__.py",
    "components/vera_mono/packages/vera_core/src/vera_core/qualified_runtime.py",
    "components/vera_mono/packages/vera_core/src/vera_core/state.py",
    "components/vera_mono/packages/vera_core/src/vera_core/task_execution.py",
    "components/vera_mono/packages/vera_core/src/vera_core/local_conversation.py",
    "components/vera_mono/packages/vera_core/src/vera_core/portal_task_handoff.py",
    "components/portal/portal/__init__.py",
    "components/portal/portal/vera_task_handoff.py",
    "components/pre_active/src/pre_active/__init__.py",
    "components/volition/src/volition/__init__.py",
})


def _require_resident_source_closure(paths: set[str]) -> None:
    missing = sorted(REQUIRED_RESIDENT_FILES - paths)
    if missing:
        raise StageError("Missing resident source import module(s): " + ", ".join(missing))


class StageError(ValueError):
    pass


def _git(checkout: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(checkout), *args], stderr=subprocess.STDOUT, text=True).strip()
    except (subprocess.CalledProcessError, OSError) as exc:
        raise StageError(f"Git checkout unavailable: {checkout}") from exc


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_bindings(root: Path):
    c = json.loads((root/"architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json").read_text())
    p = json.loads((root/"architecture/portfolio/VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json").read_text())
    return {r["repository"]: r for r in c["repositories"]}, {r["repository"]: r for r in p["repositories"]}


def stage(
    checkout_root: Path,
    destination: Path,
    source_root: Path = ROOT,
) -> dict[str, object]:
    checkout_root = checkout_root.resolve(strict=True)
    destination = destination.absolute()
    source_root = source_root.resolve(strict=True)
    if not checkout_root.is_dir() or destination.exists() or destination.is_symlink():
        raise StageError("Checkout root must exist and staging destination must not exist")
    if destination == checkout_root or checkout_root in destination.parents or \
       destination == source_root or source_root in destination.parents:
        raise StageError("Staging output cannot be inside source or checkout tree")
    composition, plan = _load_bindings(source_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".veraos-resident-", dir=destination.parent) as tmp:
        tmp_path = Path(tmp)
        rows = []
        for name, (repo_name, source_subdirs) in COMPONENTS.items():
            checkpoint = checkout_root / name
            if not checkpoint.is_dir():
                raise StageError(f"Missing checkout: {name}")
            catalog = composition.get(repo_name)
            implementation = plan.get(repo_name)
            if not catalog or not implementation:
                raise StageError(f"Missing source/plan binding: {repo_name}")
            if catalog["boot_policy"] != "CORE" or implementation["activation_policy"] != "CORE":
                raise StageError(f"Not an admitted resident CORE: {repo_name}")
            exact = _git(checkpoint, "rev-parse", "HEAD")
            if exact != catalog["exact_head"] or exact != implementation["exact_head"]:
                raise StageError(f"Exact source head mismatch: {repo_name} ({exact})")
            # Archive exactly the pinned Git tree, not the mutable checkout bytes.
            # Git's CRLF/smudge filters and unrelated untracked files therefore
            # cannot silently change what is packaged.
            archive = subprocess.check_output(
                ["git", "-C", str(checkpoint), "archive", "--format=tar", "HEAD", *source_subdirs],
            )
            copied = {}
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as files:
                for member in files:
                    if member.isdir():
                        continue
                    if not member.isfile() or member.issym() or member.islnk():
                        raise StageError(f"Nonregular committed entry forbidden: {repo_name}/{member.name}")
                    parts = Path(member.name)
                    if parts.is_absolute() or ".." in parts.parts or not any(
                        parts == Path(parent) or Path(parent) in parts.parents
                        for parent in source_subdirs
                    ):
                        raise StageError(f"Archive path escapes allowlist: {repo_name}/{member.name}")
                    if parts.suffix not in EXTENSIONS:
                        continue
                    entry = files.extractfile(member)
                    if entry is None:
                        raise StageError(f"Cannot read committed file: {repo_name}/{member.name}")
                    raw = entry.read()
                    target = tmp_path / "components" / name / parts
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
                    copied[target.relative_to(tmp_path).as_posix()] = _digest(raw)
            if not copied:
                raise StageError(f"No source files staged: {repo_name}")
            marker = {
                "vera_mono": "components/vera_mono/packages/vera_core/src/vera_core/__init__.py",
                "portal": "components/portal/portal/__init__.py",
                "pre_active": "components/pre_active/src/pre_active/__init__.py",
                "volition": "components/volition/src/volition/__init__.py",
            }[name]
            if marker not in copied:
                raise StageError(f"Required source module not staged: {repo_name}")
            inventory = [{"path": p, "sha256": copied[p]} for p in sorted(copied)]
            packed_hash = _digest(json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode())
            rows.append({
                "repository": repo_name,
                "source_head": exact,
                "marker_path": "/opt/veraos/" + marker,
                "marker_sha256": copied[marker],
                "file_count": len(inventory),
                "file_manifest_sha256": packed_hash,
                "files": inventory,
            })
        _require_resident_source_closure({p for row in rows for p in (x["path"] for x in row["files"])})
        receipt = {
            "schema": "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1",
            "components": sorted(rows, key=lambda x: x["repository"]),
            "scope": "PINNED_COMMITTED_GIT_ARCHIVE_NOT_INSTALLED_OR_ACTIVATED",
            "authority": False,
        }
        encoded = json.dumps(receipt, sort_keys=True, indent=2) + "\n"
        # Stage has only source allowlisted files. No .git, tests, credentials or model weights.
        (tmp_path/"VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json").write_bytes(encoded.encode("utf-8"))
        tmp_path.rename(destination)
    return {
        "schema": "VERA_OS_RESIDENT_SOURCE_STAGING_RESULT_V1",
        "destination": str(destination),
        "components": [
            {"repository": row["repository"], "source_head": row["source_head"],
             "file_count": row["file_count"], "file_manifest_sha256": row["file_manifest_sha256"]}
            for row in rows
        ],
        "receipt_sha256": _digest(encoded.encode()),
        "source_material": "EXACT_COMMITTED_GIT_TREE_IGNORE_MUTABLE_WORKTREE",
        "installed": False,
        "runtime_qualified": False,
        "protected_effect_authority": False,
    }


def verify_stage(staging_root: Path, source_root: Path = ROOT) -> dict[str, object]:
    """Verify every allowlisted staged file against the exact pinned manifest.

    Required resident module files are checked, but this does not execute Python
    imports in a guest, verify installed native dependencies, a running service,
    an independent reviewer, or protected effects.
    """
    staging_root = staging_root.resolve(strict=True)
    source_root = source_root.resolve(strict=True)
    receipt_file = staging_root / "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json"
    receipt_raw = receipt_file.read_bytes()
    receipt = json.loads(receipt_raw)
    if not isinstance(receipt, dict) or receipt.get("schema") != "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1" or \
       receipt.get("authority") is not False or \
       receipt.get("scope") != "PINNED_COMMITTED_GIT_ARCHIVE_NOT_INSTALLED_OR_ACTIVATED":
        raise StageError("Resident stage receipt schema, scope, or authority mismatch")
    composition, plan = _load_bindings(source_root)
    records = receipt.get("components")
    if not isinstance(records, list) or len(records) != len(COMPONENTS):
        raise StageError("Resident stage must list exactly four core components")
    byrepo = {row.get("repository"): row for row in records if isinstance(row, dict)}
    if len(byrepo) != len(COMPONENTS):
        raise StageError("Duplicate or malformed resident component records")
    expected_files: set[str] = set()
    counts = {}
    for component, (repo, _) in COMPONENTS.items():
        if repo not in byrepo or repo not in composition or repo not in plan:
            raise StageError(f"Unbound resident component: {repo}")
        record = byrepo[repo]
        if record.get("source_head") != composition[repo]["exact_head"] or \
           record.get("source_head") != plan[repo]["exact_head"]:
            raise StageError(f"Resident source head mismatch: {repo}")
        marker_path = "/opt/veraos/components/" + component + "/" + (
            "packages/vera_core/src/vera_core/__init__.py" if component == "vera_mono" else
            "portal/__init__.py" if component == "portal" else
            "src/pre_active/__init__.py" if component == "pre_active" else
            "src/volition/__init__.py"
        )
        if record.get("marker_path") != marker_path:
            raise StageError(f"Resident marker path mismatch: {repo}")
        files = record.get("files")
        if not isinstance(files, list) or not files or record.get("file_count") != len(files):
            raise StageError(f"Missing staged file manifest: {repo}")
        canonical = []
        marker_hash = None
        for row in files:
            if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
                raise StageError("Malformed staged file entry")
            relative = row["path"]
            path = Path(relative)
            if not isinstance(relative, str) or path.is_absolute() or ".." in path.parts or \
               not relative.startswith("components/" + component + "/") or \
               "\\" in relative or relative in expected_files:
                raise StageError(f"Unsafe or duplicate staged file: {relative}")
            expected_files.add(relative)
            actual = staging_root / path
            if actual.is_symlink() or not actual.is_file() or not actual.resolve().is_relative_to(staging_root):
                raise StageError(f"Missing or linked staged source: {relative}")
            observed = _digest(actual.read_bytes())
            if observed != row["sha256"]:
                raise StageError(f"Staged file was modified: {relative}")
            canonical.append({"path": relative, "sha256": observed})
            if "/opt/veraos/" + relative == marker_path:
                marker_hash = observed
        if record.get("marker_sha256") != marker_hash or marker_hash is None:
            raise StageError(f"Component marker digest mismatch: {repo}")
        packed_hash = _digest(json.dumps(sorted(canonical, key=lambda x: x["path"]),
                               sort_keys=True, separators=(",", ":")).encode())
        if packed_hash != record.get("file_manifest_sha256"):
            raise StageError(f"Component manifest digest mismatch: {repo}")
        counts[repo] = len(files)
    observed_files = {
        path.relative_to(staging_root).as_posix()
        for path in (staging_root / "components").rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if expected_files != observed_files:
        raise StageError("Staged component file inventory mismatch")
    _require_resident_source_closure(expected_files)
    return {
        "schema": "VERA_OS_RESIDENT_STAGE_VERIFICATION_V1",
        "status": "PINNED_SOURCE_FILES_VERIFIED_NOT_INSTALLED",
        "component_count": len(records),
        "file_counts": counts,
        "receipt_sha256": _digest(receipt_raw),
        "guest_import_qualified": False,
        "activated": False,
        "protected_effect_authority": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--checkouts", type=Path)
    group.add_argument("--verify-stage", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.verify_stage:
        result = verify_stage(args.verify_stage, args.repo_root)
    else:
        if args.output is None:
            parser.error("--output is required with --checkouts")
        result = stage(args.checkouts,args.output,args.repo_root)
        verified = verify_stage(args.output, args.repo_root)
        if verified["status"] != "PINNED_SOURCE_FILES_VERIFIED_NOT_INSTALLED":
            raise StageError("Stage readback did not verify")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
