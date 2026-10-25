from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA = "VERA_OS_COGNITION_PROVIDER_V1"
_ALLOWED_KINDS = {
    "LOCAL_MODEL",
    "REMOTE_API",
    "HOSTED_SESSION",
    "LOCAL_SERVICE",
    "SPECIALIST",
}
_ALLOWED_TRANSPORTS = {
    "OPENAI_COMPATIBLE_HTTP",
    "HTTP_JSON",
    "CHAT_SESSION",
    "LOCAL_PROCESS",
    "PLUGIN",
    "INTERNAL",
}
_ALLOWED_QUALIFICATION = {"PASS", "HOLD", "FAIL"}
_ALLOWED_ADMISSION = {"VERAOS_ROUTE_ELIGIBLE", "HELD"}


class CognitionProviderError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CognitionProviderError(message)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{name} must be an object")
    return value


def _text(value: object, name: str) -> str:
    text = str(value or "").strip()
    _require(bool(text), f"{name} is required")
    return text


def _sha256(value: object, name: str) -> str:
    text = _text(value, name)
    _require(
        _SHA256_RE.fullmatch(text) is not None,
        f"{name} must be an exact lowercase sha256",
    )
    return text


def validate_provider(provider: Mapping[str, Any]) -> None:
    data = _mapping(provider, "provider")
    _require(data.get("schema") == _SCHEMA, "unsupported cognition provider schema")
    _text(data.get("provider_id"), "provider_id")

    kind = _text(data.get("provider_kind"), "provider_kind")
    _require(kind in _ALLOWED_KINDS, "unsupported cognition provider kind")

    capabilities = data.get("capabilities")
    _require(
        isinstance(capabilities, list) and bool(capabilities),
        "capabilities must contain at least one capability",
    )
    for index, capability in enumerate(capabilities):
        _text(capability, f"capabilities[{index}]")

    transport = _mapping(data.get("transport"), "transport")
    transport_kind = _text(transport.get("kind"), "transport.kind")
    _require(
        transport_kind in _ALLOWED_TRANSPORTS,
        "unsupported cognition provider transport",
    )
    _text(transport.get("attachment"), "transport.attachment")

    qualification = _mapping(data.get("qualification"), "qualification")
    status = _text(qualification.get("status"), "qualification.status")
    _require(
        status in _ALLOWED_QUALIFICATION,
        "qualification.status must be PASS, HOLD, or FAIL",
    )
    _require(
        qualification.get("issuer") == "thebrazenbeard/vera-os",
        "cognition provider qualification issuer must be VeraOS",
    )
    _sha256(
        qualification.get("subject_sha256"),
        "qualification.subject_sha256",
    )
    _sha256(
        qualification.get("suite_sha256"),
        "qualification.suite_sha256",
    )

    authority = _mapping(data.get("authority"), "authority")
    for key, label in (
        ("identity_authority", "identity authority"),
        ("canonical_memory_write_authority", "canonical-memory write authority"),
        ("protected_effect_authority", "protected-effect authority"),
        ("browser_authority", "browser authority"),
    ):
        _require(
            authority.get(key) is False,
            f"cognition provider cannot hold {label}",
        )

    admission = _mapping(data.get("admission"), "admission")
    admission_status = _text(admission.get("status"), "admission.status")
    _require(
        admission_status in _ALLOWED_ADMISSION,
        "unsupported cognition provider admission status",
    )
    _require(
        admission.get("route_class") == "COGNITION_ONLY",
        "cognition provider route class must be COGNITION_ONLY",
    )
    _require(
        admission.get("selector_owner") == "thebrazenbeard/portal",
        "P.O.R.T.A.L. must own cognition route selection",
    )

    expected = "VERAOS_ROUTE_ELIGIBLE" if status == "PASS" else "HELD"
    _require(
        admission_status == expected,
        "provider admission status does not match qualification status",
    )


def provider_route_eligible(provider: Mapping[str, Any]) -> bool:
    validate_provider(provider)
    return (
        provider["qualification"]["status"] == "PASS"
        and provider["admission"]["status"] == "VERAOS_ROUTE_ELIGIBLE"
    )
