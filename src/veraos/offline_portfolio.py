"""Read-only, provider-independent VeraOS interface to the local Git portfolio vault.

This library does not fetch GitHub, load unreviewed project code, start services,
admit cognition providers, mutate memory or authorize effects.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

_SHA = re.compile(r"^[0-9a-f]{64}$")
_HEAD = re.compile(r"^[0-9a-f]{40}$")
_BUNDLE = re.compile(r"^thebrazenbeard--[A-Za-z0-9_.-]+-[0-9a-f]{12}\.bundle$")
_OWNER = "thebrazenbeard"


class OfflinePortfolioError(ValueError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _read(path: Path) -> dict[str, Any]:
    try:
        item = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise OfflinePortfolioError("Missing or invalid local portfolio JSON") from exc
    if not isinstance(item, dict):
        raise OfflinePortfolioError("Portfolio record must be a JSON object")
    return item


def inspect_offline_portfolio(
    mount_root: Path,
    *,
    verify_bytes: bool = False,
) -> dict[str, Any]:
    """Return local project availability as data, not an executable/admitted route."""
    root = Path(mount_root).resolve(strict=True)
    if not root.is_dir() or Path(mount_root).is_symlink():
        raise OfflinePortfolioError("Offline portfolio root must be a real directory")
    receipts = root / "receipts"
    bundles = root / "bundles"
    if receipts.is_symlink() or bundles.is_symlink() or not receipts.is_dir() or not bundles.is_dir():
        raise OfflinePortfolioError("Offline portfolio receipts/bundles directories absent or linked")
    summary = _read(root / "portfolio-snapshot-summary.json")
    if summary.get("schema") != "VERA_OS_OFFLINE_GIT_PORTFOLIO_SNAPSHOT_V1" or \
       summary.get("status") != "ALL_REPOSITORIES_BYTES_VERIFIED_SOURCE_ONLY" or \
       summary.get("repo_total") != 90 or summary.get("repo_verified") != 90 or \
       summary.get("repo_missing") != []:
        raise OfflinePortfolioError("Snapshot is incomplete or wrong schema")
    files = list(receipts.iterdir())
    if len(files) != 90 or any(not f.is_file() or f.is_symlink() or f.suffix != ".json" for f in files):
        raise OfflinePortfolioError("Snapshot does not contain exactly 90 safe receipts")
    entries = []
    seen: set[str] = set()
    seen_bundles: set[str] = set()
    for receipt_file in sorted(files, key=lambda p: p.name.lower()):
        r = _read(receipt_file)
        repo = r.get("repo")
        if not isinstance(repo, str) or not repo.startswith(_OWNER + "/"):
            raise OfflinePortfolioError("Foreign repository in offline portfolio")
        name = repo.split("/", 1)[1]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise OfflinePortfolioError("Unsafe repository identifier")
        slug = _OWNER + "--" + name
        if receipt_file.name != slug + ".json" or repo.lower() in seen:
            raise OfflinePortfolioError("Duplicate or misplaced receipt")
        head = r.get("head")
        bundle_name = r.get("bundle")
        digest = r.get("sha256")
        if not isinstance(head, str) or not _HEAD.fullmatch(head) or \
           bundle_name != slug + "-" + head[:12] + ".bundle" or \
           not isinstance(bundle_name, str) or not _BUNDLE.fullmatch(bundle_name) or \
           not isinstance(digest, str) or not _SHA.fullmatch(digest):
            raise OfflinePortfolioError("Unbound or unsafe Git bundle")
        if r.get("schema") != "VERA_OS_GIT_BUNDLE_RECEIPT_V1" or \
           type(r.get("private")) is not bool or type(r.get("archived")) is not bool or \
           r.get("runtime_qualified") is not False:
            raise OfflinePortfolioError("Bundle receipt claims unqualified state incorrectly")
        bundle = bundles / bundle_name
        if bundle.is_symlink() or not bundle.is_file() or bundle.stat().st_size != r.get("bytes"):
            raise OfflinePortfolioError("Missing or changed Git bundle")
        if verify_bytes and _sha256(bundle) != digest:
            raise OfflinePortfolioError("Offline bundle failed SHA-256 verification")
        seen.add(repo.lower())
        seen_bundles.add(bundle_name)
        entries.append({
            "repository": repo,
            "default_head": head,
            "private": r["private"],
            "archived": r["archived"],
            "role": r.get("role"),
            "activation_policy": r.get("activation"),
            "bundle_file": bundle_name,
            "bundle_sha256": digest,
            "availability": "SOURCE_CACHED_OFFLINE",
            "execution": "NOT_QUALIFIED",
            "authority": False,
        })
    if {p.name for p in bundles.iterdir()} != seen_bundles:
        raise OfflinePortfolioError("Bundle set differs from captured receipts")
    if sum(x["private"] for x in entries) != summary.get("private_verified") or \
       sum(x["archived"] for x in entries) != summary.get("archived_verified"):
        raise OfflinePortfolioError("Portfolio privacy/archive census does not match summary")
    return {
        "schema": "VERA_OS_LOCAL_OFFLINE_PORTFOLIO_INTERFACE_V1",
        "state": "SOURCE_CACHED_OFFLINE_NOT_RUNNING",
        "network_requested": False,
        "total": len(entries),
        "private": summary["private_verified"],
        "archived": summary["archived_verified"],
        "all_archive_bytes_verified": verify_bytes,
        "repos": entries,
        "selected_model_qualified": False,
        "runtime_effect_authority": False,
        "fully_offline_application_operation_qualified": False,
    }


def lookup_repo(mount_root: Path, repository: str, *, verify_bytes: bool = True) -> dict[str, Any]:
    """Bounded metadata lookup; does not clone or execute source code."""
    snapshot = inspect_offline_portfolio(mount_root, verify_bytes=False)
    matches = [x for x in snapshot["repos"] if x["repository"].lower() == repository.lower()]
    if len(matches) != 1:
        raise OfflinePortfolioError("Repository is not in the mounted source snapshot")
    item = matches[0]
    if verify_bytes:
        bundle = Path(mount_root) / "bundles" / item["bundle_file"]
        if _sha256(bundle) != item["bundle_sha256"]:
            raise OfflinePortfolioError("Selected Git bundle hash differs from recorded bytes")
    return dict(item, bundle_path=str(Path(mount_root).resolve() / "bundles" / item["bundle_file"]))
