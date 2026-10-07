from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SCHEMA = "VERA_OS_PORTFOLIO_COMPOSITION_V1"


class CompositionError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CompositionError(message)


def _validate_repository_reference(
    *,
    role_name: str,
    repository: str,
    by_repo: Mapping[str, Mapping[str, Any]],
) -> None:
    _require(repository in by_repo, f"runtime role references unknown repo: {role_name}")
    _require(
        by_repo[repository].get("disposition") == "INTEGRATED",
        f"runtime role references excluded repo: {role_name}",
    )


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    _require(manifest.get("schema") == _SCHEMA, "unexpected composition schema")
    repositories = manifest.get("repositories")
    _require(isinstance(repositories, list), "repositories must be a list")
    _require(bool(repositories), "repositories must not be empty")

    seen: set[str] = set()
    by_repo: dict[str, Mapping[str, Any]] = {}
    for item in repositories:
        _require(isinstance(item, Mapping), "repository entry must be an object")
        repository = str(item.get("repository") or "")
        _require(repository.count("/") == 1, f"invalid repository: {repository!r}")
        _require(repository not in seen, f"duplicate repository: {repository}")
        seen.add(repository)
        by_repo[repository] = item

        head = str(item.get("exact_head") or "")
        _require(
            _SHA40.fullmatch(head) is not None,
            f"invalid exact head: {repository}",
        )
        archived = item.get("archived")
        _require(
            isinstance(archived, bool),
            f"archived must be boolean: {repository}",
        )
        disposition = item.get("disposition")
        if archived:
            _require(
                disposition == "EXCLUDED",
                f"archived repo must be excluded: {repository}",
            )
            _require(
                item.get("exclusion_reason") == "ARCHIVED",
                f"archived repo needs ARCHIVED reason: {repository}",
            )
            _require(
                item.get("integration_mode") == "EXCLUDED",
                f"archived repo integration mode must be EXCLUDED: {repository}",
            )
        else:
            _require(
                disposition == "INTEGRATED",
                f"live repo must be integrated: {repository}",
            )
            _require(
                item.get("exclusion_reason") in (None, ""),
                f"integrated repo cannot carry exclusion reason: {repository}",
            )
            _require(
                item.get("integration_mode") != "EXCLUDED",
                f"integrated repo cannot use EXCLUDED mode: {repository}",
            )

    counts = manifest.get("counts")
    _require(isinstance(counts, Mapping), "counts must be an object")
    archived_count = sum(bool(item.get("archived")) for item in repositories)
    integrated_count = sum(item.get("disposition") == "INTEGRATED" for item in repositories)
    excluded_count = sum(item.get("disposition") == "EXCLUDED" for item in repositories)
    _require(counts.get("total") == len(repositories), "composition total count mismatch")
    _require(counts.get("archived") == archived_count, "composition archived count mismatch")
    _require(counts.get("integrated") == integrated_count, "composition integrated count mismatch")
    _require(counts.get("excluded") == excluded_count, "composition excluded count mismatch")

    roles = manifest.get("runtime_roles")
    _require(isinstance(roles, Mapping), "runtime_roles must be an object")
    for role_name, role in roles.items():
        _require(
            isinstance(role, Mapping),
            f"runtime role must be object: {role_name}",
        )
        repository = role.get("repository")
        repositories_for_role = role.get("repositories")
        _require(
            repository is not None or repositories_for_role is not None,
            f"runtime role has no repository binding: {role_name}",
        )
        if repository is not None:
            _validate_repository_reference(
                role_name=role_name,
                repository=str(repository),
                by_repo=by_repo,
            )
        if repositories_for_role is not None:
            _require(
                isinstance(repositories_for_role, list)
                and bool(repositories_for_role),
                f"runtime role repositories must be non-empty list: {role_name}",
            )
            for repo in repositories_for_role:
                _validate_repository_reference(
                    role_name=role_name,
                    repository=str(repo),
                    by_repo=by_repo,
                )

    required_owners = {
        "identity_runtime": "thebrazenbeard/vera-mono",
        "portfolio_coordinator": "thebrazenbeard/portal",
        "portfolio_discovery": "thebrazenbeard/discovery",
        "reasoning_architecture": "thebrazenbeard/rezon",
        "model_composition": "thebrazenbeard/mosaic",
        "failure_correction": "thebrazenbeard/fuckup",
        "preactive_admission": "thebrazenbeard/pre-active",
        "volition": "thebrazenbeard/volition",
    }
    for role_name, repository in required_owners.items():
        role = roles.get(role_name)
        _require(
            isinstance(role, Mapping),
            f"required runtime role missing: {role_name}",
        )
        _require(
            role.get("repository") == repository,
            f"runtime role owner mismatch: {role_name}",
        )

    authority = manifest.get("authority")
    _require(isinstance(authority, Mapping), "authority must be an object")
    _require(
        authority.get("ambient_protected_effect_authority") is False,
        "ambient protected-effect authority must remain false",
    )
    _require(
        authority.get("protected_effect_authority_source")
        == "PATRICK_EXPLICIT_EXACT_TARGET_EFFECT",
        "protected-effect authority source is not exact",
    )

    effect_execution = roles.get("effect_execution")
    _require(
        isinstance(effect_execution, Mapping),
        "effect_execution role missing",
    )
    _require(
        effect_execution.get("protected_effect_authority") is False,
        "execution substrates cannot carry ambient protected-effect authority",
    )
    _require(
        effect_execution.get("authority_source")
        == "PATRICK_EXPLICIT_EXACT_TARGET_EFFECT",
        "effect execution authority source is not exact",
    )

    failure_correction = roles.get("failure_correction")
    _require(
        failure_correction.get("protected_effect_authority") is False,
        "F.U.C.K.U.P. correction layer cannot own protected-effect authority",
    )

    provider = roles.get("cognition_provider_router")
    _require(
        isinstance(provider, Mapping),
        "cognition_provider_router role missing",
    )
    _require(
        provider.get("provider_schema") == "VERA_OS_COGNITION_PROVIDER_V1",
        "unexpected cognition provider schema",
    )
    _require(
        provider.get("provider_required_for_boot") is False,
        "VeraOS must boot without a cognition provider",
    )
    _require(
        provider.get("reasoning_owner") == "thebrazenbeard/rezon",
        "Rezon must own reasoning architecture",
    )
    _require(
        provider.get("provider_authority_rule") == "COGNITION_ONLY",
        "cognition providers must remain cognition-only",
    )

    mosaic = roles.get("model_composition")
    _require(isinstance(mosaic, Mapping), "model_composition role missing")
    _require(
        mosaic.get("integration") == "OPTIONAL_COGNITION_COMPOSITION",
        "Mosaic must remain optional cognition composition",
    )
    _require(
        mosaic.get("provider_contract") == "VERA_OS_COGNITION_PROVIDER_V1",
        "Mosaic must enter through the cognition-provider contract",
    )
    _require(
        mosaic.get("canonical_runtime_owner") == "thebrazenbeard/vera-mono",
        "Mosaic cannot replace the Vera Mono runtime boundary",
    )
    _require(
        mosaic.get("reasoning_owner") == "thebrazenbeard/rezon",
        "Mosaic cannot replace Rezon reasoning ownership",
    )
    _require(
        mosaic.get("route_owner") == "thebrazenbeard/portal",
        "Mosaic cannot replace P.O.R.T.A.L. route ownership",
    )
    _require(
        mosaic.get("qualification_state") == "RESEARCH_ONLY_NOT_ROUTE_ELIGIBLE",
        "current Mosaic integration must remain research-only",
    )
    for authority_key in (
        "runtime_authority",
        "identity_authority",
        "canonical_memory_write_authority",
        "protected_effect_authority",
    ):
        _require(
            mosaic.get(authority_key) is False,
            f"Mosaic cannot hold {authority_key}",
        )

    model = roles.get("model_production")
    _require(isinstance(model, Mapping), "model_production role missing")
    _require(
        model.get("integration") == "OPTIONAL_LOCAL_PROVIDER",
        "trained Vera model must remain optional to VeraOS",
    )
    _require(
        model.get("is_identity_authority") is False,
        "model production must not be identity authority",
    )
    _require(
        model.get("route_authority") is False,
        "model production must not own route authority",
    )
    _require(
        model.get("protected_effect_authority") is False,
        "model production must not own protected-effect authority",
    )

    model_policy = manifest.get("model_policy")
    _require(
        isinstance(model_policy, Mapping),
        "model_policy must be an object",
    )
    _require(
        model_policy.get("candidate_schema")
        == "VERA_OS_LOCAL_MODEL_PROVIDER_CANDIDATE_V1",
        "unexpected optional local-model candidate schema",
    )
    _require(
        model_policy.get("producer_repository")
        == "thebrazenbeard/vera_model_training",
        "unexpected model producer repository",
    )
    _require(
        model_policy.get("veraos_requires_trained_vera_model") is False,
        "VeraOS must not require the trained Vera model",
    )
    _require(
        model_policy.get("route_class") == "COGNITION_ONLY",
        "local model provider route class must remain COGNITION_ONLY",
    )
    for authority_key in (
        "identity_authority",
        "canonical_memory_write_authority",
        "protected_effect_authority",
    ):
        _require(
            model_policy.get(authority_key) is False,
            f"model policy cannot grant {authority_key}",
        )
    _require(
        model_policy.get("final_qualification_issuer_must_differ_from_producer")
        is True,
        "model producer must not self-issue final route qualification",
    )
    _require(
        model_policy.get("qualification_must_bind_artifact_manifest") is True,
        "model qualification must bind the exact artifact manifest",
    )

    capability_awareness = manifest.get("capability_awareness")
    _require(
        isinstance(capability_awareness, Mapping),
        "capability_awareness must be an object",
    )
    _require(
        capability_awareness.get("discovery_owner")
        == "thebrazenbeard/discovery",
        "Discovery must own portfolio capability discovery",
    )
    _require(
        capability_awareness.get("coordinator_consumer")
        == "thebrazenbeard/portal",
        "P.O.R.T.A.L. must consume capability awareness",
    )
    _require(
        capability_awareness.get("assignment_rule")
        == "KNOWN_OWNERS_REQUIRE_EXPLICIT_DISPOSITION_BEFORE_NEW_ASSIGNMENT",
        "capability assignment gate is too weak",
    )
    _require(
        capability_awareness.get("unknown_capability_rule")
        == "SEND_TO_DISCOVERY_BEFORE_ASSIGNMENT",
        "unknown capabilities must return to Discovery",
    )
    _require(
        capability_awareness.get("private_catalog_may_name_private_repositories")
        is True,
        "private VeraOS catalog must preserve full repository identities",
    )

    privacy = manifest.get("privacy")
    _require(isinstance(privacy, Mapping), "privacy contract must be an object")
    _require(
        privacy.get("distribution_intent")
        == "PRIVATE_PERSONAL_OS_NOT_FOR_PUBLIC_RELEASE",
        "VeraOS distribution intent must remain private",
    )
    _require(
        privacy.get("full_repository_identity_map_allowed") is True,
        "private VeraOS must retain complete repository identity map",
    )
    _require(
        privacy.get(
            "public_subsystems_must_not_receive_private_catalog_contents_unless_explicitly_authorized"
        )
        is True,
        "private catalog must not leak into public subsystems",
    )
