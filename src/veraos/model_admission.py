from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA = "VERA_OS_LOCAL_MODEL_PROVIDER_CANDIDATE_V1"


class ModelAdmissionError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ModelAdmissionError(message)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{name} must be an object")
    return value


def _text(value: object, name: str) -> str:
    text = str(value or "").strip()
    _require(bool(text), f"{name} is required")
    return text


def _sha40(value: object, name: str) -> str:
    text = _text(value, name)
    _require(
        _GIT_SHA_RE.fullmatch(text) is not None,
        f"{name} must be an exact lowercase Git SHA",
    )
    return text


def _sha256(value: object, name: str) -> str:
    text = _text(value, name)
    _require(
        _SHA256_RE.fullmatch(text) is not None,
        f"{name} must be an exact lowercase sha256",
    )
    return text


def validate_local_model_provider_candidate(
    candidate: Mapping[str, Any],
) -> None:
    data = _mapping(candidate, "candidate")
    _require(data.get("schema") == _SCHEMA, "unsupported local-model provider schema")
    _text(data.get("artifact_id"), "artifact_id")

    producer = _mapping(data.get("producer"), "producer")
    _require(
        producer.get("repository") == "thebrazenbeard/vera_model_training",
        "unexpected model producer",
    )
    _text(producer.get("source_branch"), "producer.source_branch")
    _sha40(producer.get("source_commit"), "producer.source_commit")

    base = _mapping(data.get("base"), "base")
    _text(base.get("repository"), "base.repository")
    _sha40(base.get("revision"), "base.revision")
    _text(base.get("format"), "base.format")

    artifacts = data.get("artifacts")
    _require(
        isinstance(artifacts, list) and bool(artifacts),
        "artifacts must contain at least one exact artifact",
    )
    for index, artifact in enumerate(artifacts):
        row = _mapping(artifact, f"artifacts[{index}]")
        _text(row.get("path"), f"artifacts[{index}].path")
        _sha256(row.get("sha256"), f"artifacts[{index}].sha256")

    training = _mapping(data.get("training"), "training")
    training_manifest = _sha256(
        training.get("artifact_manifest_sha256"),
        "training.artifact_manifest_sha256",
    )
    _text(training.get("training_corpus_id"), "training.training_corpus_id")
    _sha256(training.get("train_sha256"), "training.train_sha256")
    _sha256(training.get("receipt_sha256"), "training.receipt_sha256")
    _sha256(
        training.get("runtime_binding_sha256"),
        "training.runtime_binding_sha256",
    )

    qualification = _mapping(data.get("qualification"), "qualification")
    status = _text(qualification.get("status"), "qualification.status")
    _require(status in {"PASS", "HOLD", "FAIL"}, "unsupported qualification status")

    issuer = _text(
        qualification.get("issuer_repository"),
        "qualification.issuer_repository",
    )
    _require(
        issuer != producer.get("repository"),
        "qualification issuer must be separate from model producer",
    )

    qualified_manifest = _sha256(
        qualification.get("artifact_manifest_sha256"),
        "qualification.artifact_manifest_sha256",
    )
    _require(
        qualified_manifest == training_manifest,
        "qualification does not bind the exact training artifact manifest",
    )
    _sha256(
        qualification.get("suite_sha256"),
        "qualification.suite_sha256",
    )
    _sha256(
        qualification.get("runtime_binding_sha256"),
        "qualification.runtime_binding_sha256",
    )

    authority = _mapping(data.get("authority"), "authority")
    _require(
        authority.get("identity_authority") is False,
        "local model provider cannot hold identity authority",
    )
    _require(
        authority.get("canonical_memory_write_authority") is False,
        "local model provider cannot hold canonical-memory write authority",
    )
    _require(
        authority.get("protected_effect_authority") is False,
        "local model provider cannot hold protected-effect authority",
    )
    _require(
        authority.get("browser_authority") is False,
        "local model provider cannot hold browser authority",
    )

    admission = _mapping(data.get("admission"), "admission")
    admission_status = _text(admission.get("status"), "admission.status")
    _require(
        admission.get("route_class") == "COGNITION_ONLY",
        "local model provider route class must be COGNITION_ONLY",
    )
    _require(
        admission.get("selector_owner") == "thebrazenbeard/portal",
        "P.O.R.T.A.L. must own cognition route selection",
    )
    _require(
        admission.get("identity_runtime_owner") == "thebrazenbeard/vera-mono",
        "Vera Mono must own the identity/runtime boundary",
    )
    _require(
        admission.get("integration") == "OPTIONAL_PROVIDER",
        "trained Vera model must remain an optional provider",
    )

    expected = "VERAOS_ROUTE_ELIGIBLE" if status == "PASS" else "HELD"
    _require(
        admission_status == expected,
        "local-model admission state does not match qualification state",
    )


def local_model_route_eligible(candidate: Mapping[str, Any]) -> bool:
    validate_local_model_provider_candidate(candidate)
    return (
        candidate["qualification"]["status"] == "PASS"
        and candidate["admission"]["status"] == "VERAOS_ROUTE_ELIGIBLE"
    )


validate_cognition_engine_candidate = validate_local_model_provider_candidate
candidate_route_eligible = local_model_route_eligible
