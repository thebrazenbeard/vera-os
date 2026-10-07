from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


_SCHEMA = "VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class PortfolioImplementationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PortfolioImplementationError(message)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{name} must be an object")
    return value


def _records_by_repo(value: object, name: str) -> dict[str, Mapping[str, Any]]:
    _require(isinstance(value, list) and bool(value), f"{name} must be a non-empty list")
    records: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(value):
        row = _mapping(item, f"{name}[{index}]")
        repository = str(row.get("repository") or "").strip()
        _require(repository.count("/") == 1, f"invalid repository in {name}: {repository!r}")
        _require(repository not in records, f"duplicate repository in {name}: {repository}")
        records[repository] = row
    return records


def validate_implementation_plan(
    plan: Mapping[str, Any],
    capability_map: Mapping[str, Any],
    composition: Mapping[str, Any],
) -> None:
    data = _mapping(plan, "implementation plan")
    _require(data.get("schema") == _SCHEMA, "unexpected implementation plan schema")
    _require(
        data.get("visibility") == "PRIVATE_VERAOS_INTERNAL",
        "implementation plan must remain private VeraOS internal state",
    )

    plan_by_repo = _records_by_repo(data.get("repositories"), "implementation repositories")
    cap_by_repo = _records_by_repo(capability_map.get("repositories"), "capability repositories")
    composition_by_repo = _records_by_repo(
        composition.get("repositories"),
        "composition repositories",
    )

    _require(
        set(plan_by_repo) == set(cap_by_repo) == set(composition_by_repo),
        "implementation plan inventory must exactly match capability and composition inventories",
    )

    inventory = _mapping(data.get("inventory"), "inventory")
    _require(inventory.get("total") == len(plan_by_repo), "implementation total mismatch")
    archived_count = sum(bool(row.get("archived")) for row in plan_by_repo.values())
    _require(inventory.get("archived") == archived_count, "implementation archived count mismatch")
    _require(
        inventory.get("active_or_available") == len(plan_by_repo) - archived_count,
        "implementation active count mismatch",
    )

    policy = _mapping(data.get("policy"), "policy")
    _require(
        policy.get("all_owned_repositories_considered_exactly_once") is True,
        "every owned repository must be considered exactly once",
    )
    _require(
        policy.get("canonical_runtime_repository") == "thebrazenbeard/vera-mono",
        "Vera Mono must remain the canonical runtime source",
    )
    _require(
        policy.get("operating_environment_repository") == "thebrazenbeard/vera-os",
        "VeraOS must remain the operating environment source",
    )
    _require(
        policy.get("direct_sibling_runtime_dependencies_forbidden") is True,
        "sibling repositories cannot become direct runtime dependencies",
    )
    _require(
        policy.get("protected_effect_authority_source")
        == "PATRICK_EXPLICIT_EXACT_TARGET_EFFECT",
        "implementation plan cannot create ambient protected-effect authority",
    )

    lanes = _mapping(data.get("lanes"), "lanes")
    _require(bool(lanes), "implementation lanes must not be empty")

    for repository, row in plan_by_repo.items():
        cap_row = cap_by_repo[repository]
        composition_row = composition_by_repo[repository]

        exact_head = str(row.get("exact_head") or "")
        _require(_SHA40.fullmatch(exact_head) is not None, f"invalid exact head: {repository}")
        _require(
            exact_head == cap_row.get("exact_head") == composition_row.get("exact_head"),
            f"exact-head mismatch across portfolio bindings: {repository}",
        )
        _require(
            bool(row.get("archived")) == bool(cap_row.get("archived"))
            == bool(composition_row.get("archived")),
            f"archived-state mismatch across portfolio bindings: {repository}",
        )
        _require(
            row.get("direct_sibling_runtime_dependency") is False,
            f"direct sibling runtime dependency forbidden: {repository}",
        )
        path = str(row.get("implementation_path") or "")
        _require(path in lanes, f"unknown implementation lane for {repository}: {path}")
        _require(
            row.get("source_integration_mode") == composition_row.get("integration_mode"),
            f"source integration mode mismatch: {repository}",
        )
        _require(
            sorted(set(row.get("capabilities", [])))
            == sorted(set(cap_row.get("capabilities", []))),
            f"capability binding mismatch: {repository}",
        )
        _require(
            str(row.get("implementation_class") or "") not in {"", "UNCLASSIFIED"},
            f"repository remains unclassified: {repository}",
        )
        _require(
            str(row.get("decision") or "") not in {"", "HOLD"},
            f"repository implementation decision remains unresolved: {repository}",
        )

        if row.get("archived"):
            _require(
                row.get("implementation_class") == "ARCHIVED_PROVENANCE",
                f"archived repository must be provenance-only: {repository}",
            )
            _require(
                path == "PROVENANCE_RECORD_ONLY",
                f"archived repository cannot have active implementation path: {repository}",
            )
            _require(
                row.get("activation_policy") == "NEVER",
                f"archived repository cannot be activated: {repository}",
            )

    _require(
        plan_by_repo["thebrazenbeard/vera-os"].get("implementation_class")
        == "OPERATING_ENVIRONMENT",
        "VeraOS repository must own the operating-environment implementation class",
    )
    _require(
        plan_by_repo["thebrazenbeard/vera-mono"].get("implementation_class")
        == "CANONICAL_RUNTIME",
        "Vera Mono repository must own the canonical-runtime implementation class",
    )
    _require(
        plan_by_repo["thebrazenbeard/rezon"].get("implementation_path")
        == "VERA_MONO_ABSORBED_REASONING",
        "Rezon runtime use must flow through the absorbed Vera Mono reasoning package",
    )
    for repository in (
        "thebrazenbeard/mediaphile-client",
        "thebrazenbeard/mediaphile-server",
    ):
        _require(repository in plan_by_repo, f"current live portfolio repository missing: {repository}")
        _require(
            plan_by_repo[repository].get("source_maturity") == "PLAN_ONLY",
            f"plan-only Mediaphile split cannot be promoted to implemented runtime: {repository}",
        )
        _require(
            plan_by_repo[repository].get("activation_policy") == "ON_DEMAND",
            f"plan-only Mediaphile split cannot be boot-active: {repository}",
        )
