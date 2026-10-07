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
        _require(_SHA40.fullmatch(head) is not None, f"invalid exact head: {repository}")
        archived = item.get("archived")
        _require(isinstance(archived, bool), f"archived must be boolean: {repository}")
        disposition = item.get("disposition")
        if archived:
            _require(disposition == "EXCLUDED", f"archived repo must be excluded: {repository}")
            _require(item.get("exclusion_reason") == "ARCHIVED", f"archived repo needs ARCHIVED reason: {repository}")
            _require(item.get("integration_mode") == "EXCLUDED", f"archived repo integration mode must be EXCLUDED: {repository}")
        else:
            _require(disposition == "INTEGRATED", f"live repo must be integrated: {repository}")
            _require(item.get("exclusion_reason") in (None, ""), f"integrated repo cannot carry exclusion reason: {repository}")
            _require(item.get("integration_mode") != "EXCLUDED", f"integrated repo cannot use EXCLUDED mode: {repository}")

    roles = manifest.get("runtime_roles")
    _require(isinstance(roles, Mapping), "runtime_roles must be an object")
    for role_name, role in roles.items():
        _require(isinstance(role, Mapping), f"runtime role must be object: {role_name}")
        repository = str(role.get("repository") or "")
        _require(repository in by_repo, f"runtime role references unknown repo: {role_name}")
        _require(by_repo[repository].get("disposition") == "INTEGRATED", f"runtime role references excluded repo: {role_name}")

    authority = manifest.get("authority")
    _require(isinstance(authority, Mapping), "authority must be an object")
    _require(authority.get("ambient_protected_effect_authority") is False, "ambient protected-effect authority must remain false")
    _require(authority.get("protected_effect_authority_source") == "PATRICK_EXPLICIT_EXACT_TARGET_EFFECT", "protected-effect authority source is not exact")

    inference = roles.get("inference_router")
    _require(isinstance(inference, Mapping), "inference_router role missing")
    _require(
        inference.get("model_identity_rule") == "MODEL_PROVENANCE_IS_NOT_VERA_IDENTITY",
        "model provenance must not become Vera identity",
    )
    model = roles.get("model_production")
    _require(isinstance(model, Mapping), "model_production role missing")
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
    _require(isinstance(model_policy, Mapping), "model_policy must be an object")
    _require(
        model_policy.get("candidate_schema")
        == "VERA_OS_COGNITION_ENGINE_CANDIDATE_V1",
        "unexpected model candidate schema",
    )
    _require(
        model_policy.get("producer_repository")
        == "thebrazenbeard/vera_model_training",
        "unexpected model producer repository",
    )
    _require(
        model_policy.get("trained_model_role") == "COGNITION_ENGINE",
        "trained model role must remain cognition engine",
    )
    _require(
        model_policy.get("route_class") == "COGNITION_ONLY",
        "trained model route class must remain COGNITION_ONLY",
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
    _require(
        inference.get("candidate_schema") == model_policy.get("candidate_schema"),
        "inference router and model policy candidate schemas diverge",
    )
    _require(
        inference.get("qualification_binding_rule")
        == "EXACT_ARTIFACT_MANIFEST_AND_SEPARATE_ISSUER",
        "inference router qualification binding rule is too weak",
    )
