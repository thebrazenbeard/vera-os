#!/usr/bin/env python3
"""Freeze all Vera GitHub portfolio repos into verifiable local Git bundles.

Online capture is a preparation step; verify and offline-clone need no network.
This does not install repositories, resolve runtime dependencies or activate Vera.
Private repository contents must never be published with the VeraOS source.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

DEFAULT_INVENTORY = Path(__file__).resolve().parents[2] / "architecture/offline/VERA_OS_OWNED_OFFLINE_PORTFOLIO_CENSUS_20261012.json"
NAME = re.compile(r"^[a-zA-Z0-9_.-]+$")
HEAD = re.compile(r"^[0-9a-f]{40}$")


class MirrorError(ValueError):
    pass


def _command(*args: str, timeout: int = 1200) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    try:
        proc = subprocess.run(list(args), capture_output=True, text=True,
                              env=env, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MirrorError(f"Git operation unavailable or timed out: {args[0:2]}") from exc
    if proc.returncode:
        # Do not include stderr: credential helpers and remote paths may expose secrets.
        raise MirrorError(f"Git command failed (exit {proc.returncode}): {args[:2]}")
    return proc.stdout.strip()


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for data in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(data)
    return hasher.hexdigest()


def census(path: Path) -> dict:
    index = json.loads(path.read_text(encoding="utf-8"))
    if index.get("schema") != "VERA_OS_OWNED_OFFLINE_PORTFOLIO_CENSUS_V1":
        raise MirrorError("Unexpected portfolio census schema")
    repos = index.get("repositories")
    if not isinstance(repos, list) or len(repos) != index.get("repo_count") or not repos:
        raise MirrorError("Census has inconsistent repository count")
    if index["repo_count"] != 90:
        raise MirrorError("This capture profile requires exactly the 90-repository observed census")
    seen = set()
    for row in repos:
        if not isinstance(row, dict) or not isinstance(row.get("repo"), str):
            raise MirrorError("Malformed repository record")
        owner, sep, name = row["repo"].partition("/")
        if not sep or owner != index["owner"] or not NAME.fullmatch(name) or row["repo"].lower() in seen:
            raise MirrorError("Unsafe or duplicate repository name")
        branch = row.get("default_branch")
        if not isinstance(branch, str) or not NAME.fullmatch(branch):
            raise MirrorError("Unsupported default branch name")
        if type(row.get("private")) is not bool or type(row.get("archived")) is not bool:
            raise MirrorError("Private/archived flags must be explicit booleans")
        seen.add(row["repo"].lower())
    if sum(row["private"] for row in repos) != index["private_count"]:
        raise MirrorError("Private repo count mismatch")
    if sum(row["archived"] for row in repos) != index["archived_count"]:
        raise MirrorError("Archived repo count mismatch")
    return index


def _slug(row: dict) -> str:
    return row["repo"].replace("/", "--")


def _bundle_head(path: Path, branch: str) -> str:
    lines = _command("git", "bundle", "list-heads", str(path)).splitlines()
    matches = [s.split()[0] for s in lines if len(s.split()) == 2 and s.split()[1] == "refs/heads/" + branch]
    if len(matches) != 1 or not HEAD.fullmatch(matches[0]):
        raise MirrorError("Default branch is missing from offline bundle")
    return matches[0]


def _verify_one(output: Path, row: dict) -> dict:
    slug = _slug(row)
    receipt_file = output / "receipts" / (slug + ".json")
    data = json.loads(receipt_file.read_text(encoding="utf-8"))
    if data.get("schema") != "VERA_OS_GIT_BUNDLE_RECEIPT_V1" or data.get("repo") != row["repo"] or \
       data.get("private") is not row["private"] or data.get("archived") is not row["archived"] or \
       data.get("default_branch") != row["default_branch"]:
        raise MirrorError(f"Receipt provenance mismatch: {slug}")
    head = data.get("head")
    digest = data.get("sha256")
    if not isinstance(head, str) or not HEAD.fullmatch(head) or not isinstance(digest, str) or \
       not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise MirrorError("Missing valid commit or archive digest")
    bundle_name = data.get("bundle")
    expected_name = slug + "-" + head[:12] + ".bundle"
    if bundle_name != expected_name:
        raise MirrorError("Receipt has an unsafe bundle name")
    bundle = output / "bundles" / bundle_name
    if bundle.is_symlink() or not bundle.is_file() or bundle.stat().st_size != data["bytes"] or \
       _digest(bundle) != digest or _bundle_head(bundle, row["default_branch"]) != head:
        raise MirrorError(f"Bundle bytes/heads mismatch: {slug}")
    return data


def capture_one(output: Path, row: dict) -> dict:
    slug = _slug(row)
    receipt = output / "receipts" / (slug + ".json")
    if receipt.exists() or receipt.is_symlink():
        return _verify_one(output, row)
    with tempfile.TemporaryDirectory(prefix=".capture-", dir=output) as tmp:
        repo = Path(tmp) / "mirror.git"
        remote = "https://github.com/" + row["repo"] + ".git"
        _command("git", "clone", "--mirror", "--quiet", remote, str(repo))
        head = _command("git", "--git-dir=" + str(repo), "rev-parse", "refs/heads/" + row["default_branch"])
        if not HEAD.fullmatch(head):
            raise MirrorError("Invalid branch source HEAD")
        local = Path(tmp) / (slug + "-" + head[:12] + ".bundle")
        _command("git", "--git-dir=" + str(repo), "bundle", "create", str(local), "--all")
        if not local.is_file() or local.stat().st_size < 100 or _bundle_head(local, row["default_branch"]) != head:
            raise MirrorError("Bundle did not preserve the expected default branch")
        _command("git", "--git-dir=" + str(repo), "bundle", "verify", str(local))
        output_bundle = output / "bundles" / local.name
        os.link(local, output_bundle)  # atomic create, no overwrite
        data = {
            "schema": "VERA_OS_GIT_BUNDLE_RECEIPT_V1",
            "repo": row["repo"],
            "private": row["private"],
            "archived": row["archived"],
            "role": row.get("role"),
            "activation": row.get("activation"),
            "default_branch": row["default_branch"],
            "head": head,
            "previous_plan_head": row.get("previous_plan_head"),
            "bundle": local.name,
            "sha256": _digest(output_bundle),
            "bytes": output_bundle.stat().st_size,
            "capture_time_utc": datetime.now(timezone.utc).isoformat(),
            "runtime_qualified": False,
        }
        # The bundle remains if receipt creation fails. Reconcile rather than
        # overwriting an ambiguous write on the next attempt.
        with receipt.open("x", encoding="utf-8") as file:
            json.dump(data, file, indent=2, sort_keys=True)
            file.write("\n")
    return _verify_one(output, row)


def run(inventory: Path, output: Path, limit: int | None = None, verify_only: bool = False) -> dict:
    idx = census(inventory)
    selected = idx["repositories"][:limit] if limit else idx["repositories"]
    if not verify_only:
        output.mkdir(parents=True, exist_ok=True)
        (output / "bundles").mkdir(exist_ok=True)
        (output / "receipts").mkdir(exist_ok=True)
        for i, row in enumerate(selected, 1):
            data = capture_one(output, row)
            print(f"CAPTURED {i}/{len(selected)} {row['repo']} {data['head'][:12]} {data['bytes']} bytes", flush=True)
    completed = []
    missing = []
    for row in idx["repositories"]:
        path = output / "receipts" / (_slug(row) + ".json")
        if path.is_file():
            completed.append(_verify_one(output, row))
        else:
            missing.append(row["repo"])
    result = {
        "schema": "VERA_OS_OFFLINE_GIT_PORTFOLIO_SNAPSHOT_V1",
        "status": "ALL_REPOSITORIES_BYTES_VERIFIED_SOURCE_ONLY" if not missing else "INCOMPLETE_SOURCE_MIRROR",
        "census_date": idx["observed_date"],
        "repo_total": idx["repo_count"],
        "repo_verified": len(completed),
        "repo_missing": missing,
        "private_verified": sum(x["private"] for x in completed),
        "archived_verified": sum(x["archived"] for x in completed),
        "total_bundle_bytes": sum(x["bytes"] for x in completed),
        "source_only": True,
        "runtime_dependencies_cached": False,
        "local_model_weights_qualified": False,
        "offline_executable_capabilities_qualified": False,
        "guest_runtime_installed": False,
        "protected_effect_authority": False,
    }
    report = output / "portfolio-snapshot-summary.json"
    if not verify_only and not missing and not report.exists():
        with report.open("x", encoding="utf-8") as file:
            json.dump(result, file, indent=2, sort_keys=True)
            file.write("\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    result = run(args.inventory, args.output, args.limit, args.verify_only)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ALL_REPOSITORIES_BYTES_VERIFIED_SOURCE_ONLY" else 3


if __name__ == "__main__":
    raise SystemExit(main())
