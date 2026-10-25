from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_MAP_SCHEMA = "VERA_OS_PRIVATE_PORTFOLIO_CAPABILITY_MAP_V1"
_PROPOSAL_SCHEMA = "VERA_OS_CAPABILITY_ASSIGNMENT_PROPOSAL_V1"
_ALLOWED_DISPOSITIONS = {"REUSE", "EXTEND", "SUPERSEDE", "REJECT"}


class PortfolioAwarenessError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PortfolioAwarenessError(message)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{name} must be an object")
    return value


def _text(value: object, name: str) -> str:
    text = str(value or "").strip()
    _require(bool(text), f"{name} is required")
    return text


def validate_capability_map(capability_map: Mapping[str, Any]) -> None:
    data = _mapping(capability_map, "capability map")
    _require(data.get("schema") == _MAP_SCHEMA, "unsupported capability map schema")
    _require(
        data.get("visibility") == "PRIVATE_VERAOS_INTERNAL",
        "full portfolio capability map must remain private VeraOS internal state",
    )

    inventory = _mapping(data.get("inventory"), "inventory")
    records = data.get("repositories")
    _require(isinstance(records, list), "repositories must be a list")
    _require(
        len(records) == inventory.get("total"),
        "repository count does not match inventory total",
    )
    _require(
        isinstance(inventory.get("total"), int) and inventory.get("total") > 0,
        "inventory total must be a positive integer",
    )

    names: set[str] = set()
    active_names: set[str] = set()
    archived_count = 0
    for index, record in enumerate(records):
        row = _mapping(record, f"repositories[{index}]")
        name = _text(row.get("repository"), f"repositories[{index}].repository")
        _require(name not in names, f"duplicate repository binding: {name}")
        names.add(name)
        _text(row.get("exact_head"), f"{name}.exact_head")
        _require(
            isinstance(row.get("private"), bool),
            f"{name}.private must be boolean",
        )
        _require(
            isinstance(row.get("archived"), bool),
            f"{name}.archived must be boolean",
        )
        caps = row.get("capabilities")
        _require(
            isinstance(caps, list) and bool(caps),
            f"{name} must have at least one semantic capability",
        )
        if row["archived"]:
            archived_count += 1
            _require(
                row.get("disposition") == "ARCHIVED_PROVENANCE",
                f"archived repository disposition invalid: {name}",
            )
        else:
            active_names.add(name)
            _require(
                row.get("disposition") == "ACTIVE_OR_AVAILABLE",
                f"active repository disposition invalid: {name}",
            )

    _require(
        archived_count == inventory.get("archived"),
        "archived repository count mismatch",
    )
    _require(
        len(active_names) == inventory.get("active_or_available"),
        "active repository count mismatch",
    )
    _require(
        archived_count + len(active_names) == len(records),
        "inventory active/archive partition mismatch",
    )

    capabilities = _mapping(data.get("capabilities"), "capabilities")
    _require(bool(capabilities), "capability ownership map must not be empty")
    for capability, metadata in capabilities.items():
        cap = _text(capability, "capability key")
        meta = _mapping(metadata, f"capabilities.{cap}")
        owners = meta.get("owners")
        _require(
            isinstance(owners, list) and bool(owners),
            f"{cap} must have at least one owner",
        )
        for owner in owners:
            owner_name = _text(owner, f"{cap}.owner")
            _require(
                owner_name in names,
                f"{cap} references unknown owner: {owner_name}",
            )
            _require(
                owner_name in active_names,
                f"{cap} cannot use archived active owner: {owner_name}",
            )

        supporting = meta.get("supporting", [])
        _require(isinstance(supporting, list), f"{cap}.supporting must be a list")
        for repo in supporting:
            repo_name = _text(repo, f"{cap}.supporting")
            _require(
                repo_name in names,
                f"{cap} references unknown supporting repository: {repo_name}",
            )

    currentness = _mapping(data.get("currentness"), "currentness")
    _require(
        currentness.get("rule")
        == "VERIFY_LIVE_INVENTORY_AND_RELEVANT_EXACT_HEADS_BEFORE_ARCHITECTURE_ASSIGNMENT",
        "capability map currentness rule is too weak",
    )
    _require(
        currentness.get("stale_behavior") == "HOLD_ASSIGNMENT_AND_REFRESH",
        "stale capability map must hold assignment and refresh",
    )
    _require(
        currentness.get("bound_repository_count") == len(records),
        "capability map currentness count mismatch",
    )

    policy = _mapping(data.get("policy"), "policy")
    _require(
        policy.get("new_capability_assignment_rule")
        == "KNOWN_OWNERS_REQUIRE_EXPLICIT_DISPOSITION_BEFORE_NEW_ASSIGNMENT",
        "capability assignment policy is too weak",
    )
    _require(
        set(policy.get("allowed_owner_dispositions", [])) == _ALLOWED_DISPOSITIONS,
        "owner disposition vocabulary mismatch",
    )
    _require(policy.get("evidence_required") is True, "owner disposition evidence required")


def require_current_catalog(
    capability_map: Mapping[str, Any],
    live_inventory: list[Mapping[str, Any]],
) -> None:
    validate_capability_map(capability_map)
    expected = {
        str(row["repository"]): str(row["exact_head"])
        for row in capability_map["repositories"]
    }
    observed: dict[str, str] = {}
    for index, row in enumerate(live_inventory):
        item = _mapping(row, f"live_inventory[{index}]")
        repository = _text(
            item.get("repository"),
            f"live_inventory[{index}].repository",
        )
        exact_head = _text(
            item.get("exact_head"),
            f"live_inventory[{index}].exact_head",
        )
        _require(
            repository not in observed,
            f"duplicate live repository: {repository}",
        )
        observed[repository] = exact_head

    missing = sorted(set(expected) - set(observed))
    added = sorted(set(observed) - set(expected))
    _require(
        not missing and not added,
        "capability catalog inventory changed; hold assignment and refresh"
        + (f"; missing={','.join(missing)}" if missing else "")
        + (f"; added={','.join(added)}" if added else ""),
    )

    changed = sorted(
        repo
        for repo, head in expected.items()
        if observed.get(repo) != head
    )
    _require(
        not changed,
        "capability catalog exact heads changed; hold assignment and refresh: "
        + ", ".join(changed),
    )


def require_capability_dispositions(
    capability_map: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> None:
    validate_capability_map(capability_map)
    data = _mapping(proposal, "proposal")
    _require(data.get("schema") == _PROPOSAL_SCHEMA, "unsupported proposal schema")
    _text(data.get("proposal_id"), "proposal_id")
    capability = _text(data.get("capability"), "capability")
    _text(data.get("proposed_owner"), "proposed_owner")

    capabilities = _mapping(capability_map.get("capabilities"), "capabilities")
    _require(
        capability in capabilities,
        f"unknown capability requires Discovery classification first: {capability}",
    )
    metadata = _mapping(capabilities[capability], f"capabilities.{capability}")
    owners = set(metadata.get("owners", []))

    dispositions = data.get("existing_owner_dispositions")
    _require(
        isinstance(dispositions, list),
        "existing_owner_dispositions must be a list",
    )
    by_repo: dict[str, Mapping[str, Any]] = {}
    for index, disposition in enumerate(dispositions):
        row = _mapping(disposition, f"existing_owner_dispositions[{index}]")
        repo = _text(row.get("repository"), f"existing_owner_dispositions[{index}].repository")
        _require(repo not in by_repo, f"duplicate owner disposition: {repo}")
        action = _text(row.get("disposition"), f"{repo}.disposition")
        _require(
            action in _ALLOWED_DISPOSITIONS,
            f"unsupported owner disposition for {repo}: {action}",
        )
        evidence = _text(row.get("evidence"), f"{repo}.evidence")
        _require(bool(evidence), f"evidence is required for owner disposition: {repo}")
        by_repo[repo] = row

    missing = sorted(owners - set(by_repo))
    _require(
        not missing,
        "known capability owner lacks explicit disposition: " + ", ".join(missing),
    )

    extras = sorted(set(by_repo) - owners)
    _require(
        not extras,
        "owner disposition references non-owner repository: " + ", ".join(extras),
    )
