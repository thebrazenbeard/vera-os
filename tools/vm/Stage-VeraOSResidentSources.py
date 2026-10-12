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
        receipt = {
            "schema": "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1",
            "components": sorted(rows, key=lambda x: x["repository"]),
            "scope": "PINNED_COMMITTED_GIT_ARCHIVE_NOT_INSTALLED_OR_ACTIVATED",
            "authority": False,
        }
        encoded = json.dumps(receipt, sort_keys=True, indent=2) + "\n"
        # Stage has only source allowlisted files. No .git, tests, credentials or model weights.
        (tmp_path/"VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json").write_text(encoded, encoding="utf-8")
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkouts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(stage(args.checkouts,args.output,args.repo_root),indent=2))


if __name__ == "__main__":
    main()
