"""Classify bounded, non-authoritative observations of a local model host.

This module has no network, filesystem, process, or provider-admission effects.
An observation is caller-supplied evidence, not host identity or qualification.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from ipaddress import ip_address
import re
from typing import Any
from urllib.parse import urlsplit


_SCHEMA = "VERAOS_HOST_MODEL_OBSERVATION_V1"
_HOST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_RFC3339 = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})$")
_REQUIRED = {
    "schema", "host_id", "os", "backend", "endpoint", "model_id",
    "observed_at", "process_seen", "catalogued_models", "resident_models",
    "endpoint_health",
}


class HostModelObservationError(ValueError):
    """A supplied observation is malformed or claims authority it cannot hold."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HostModelObservationError(message)


def _model_id(value: object, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()) and value == value.strip(),
             f"{label} must be a nonempty exact string")
    _require(all(ord(char) >= 32 and ord(char) != 127 for char in value),
             f"{label} cannot contain control characters")
    return value


def _models(value: object, label: str) -> list[str]:
    _require(isinstance(value, list), f"{label} must be a list")
    for index, model in enumerate(value):
        _model_id(model, f"{label}[{index}]")
    return value


def _loopback_origin(value: object) -> str:
    _require(isinstance(value, str) and value == value.strip(),
             "endpoint must be an exact origin string")
    _require(all(32 < ord(char) < 127 for char in value),
             "endpoint cannot contain whitespace, controls, or non-ASCII ambiguity")
    _require("?" not in value and "#" not in value,
             "endpoint must have no query or fragment delimiters")
    try:
        uri = urlsplit(value)
        port = uri.port
    except ValueError as exc:
        raise HostModelObservationError("malformed endpoint origin") from exc
    _require(uri.scheme in {"http", "https"}, "endpoint scheme must be HTTP(S)")
    _require(uri.username is None and uri.password is None, "endpoint cannot include credentials")
    _require(not (uri.path or uri.query or uri.fragment), "endpoint must have no path/query/fragment")
    _require(uri.hostname is not None and port is not None and 0 < port <= 65535,
             "endpoint must have a host and explicit port")
    try:
        host = ip_address(uri.hostname)
    except ValueError as exc:
        raise HostModelObservationError("endpoint requires a numeric loopback address") from exc
    _require(host.is_loopback, "endpoint must be loopback on the named host")
    return value


def classify_host_model_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Return the strongest *observed* state; never qualify inference or effects.

    Exact health here means a caller observed a healthy endpoint *advertising*
    the requested model. It is not a successful inference or an authenticated
    model issuer receipt. Only the independently governed admission route may
    make those stronger claims.
    """
    _require(isinstance(observation, Mapping), "observation must be an object")
    _require(set(observation) == _REQUIRED, "observation fields do not match schema")
    _require(observation["schema"] == _SCHEMA, "unknown observation schema")
    host_id = observation["host_id"]
    _require(isinstance(host_id, str) and _HOST_ID.fullmatch(host_id) is not None,
             "host_id must be a bounded identifier")
    _require(isinstance(observation["os"], str) and observation["os"] in {"windows", "linux"},
             "unsupported host OS")
    _require(isinstance(observation["backend"], str) and observation["backend"] in {"ollama", "llama_cpp", "koboldcpp"},
             "unsupported backend")
    endpoint = _loopback_origin(observation["endpoint"])
    model_id = _model_id(observation["model_id"], "model_id")
    stamp = observation["observed_at"]
    _require(isinstance(stamp, str) and _RFC3339.fullmatch(stamp) is not None,
             "observed_at must be RFC3339 text with seconds and timezone")
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HostModelObservationError("invalid observed_at") from exc
    _require(parsed.tzinfo is not None, "observed_at requires a timezone")
    _require(type(observation["process_seen"]) is bool, "process_seen must be boolean")
    catalogued = _models(observation["catalogued_models"], "catalogued_models")
    resident = _models(observation["resident_models"], "resident_models")
    health = observation["endpoint_health"]
    _require(isinstance(health, Mapping) and set(health) == {"healthy", "model_id"},
             "endpoint_health fields do not match schema")
    _require(type(health["healthy"]) is bool, "endpoint health must be boolean")
    if health["model_id"] is not None:
        _model_id(health["model_id"], "endpoint_health.model_id")

    state = "UNOBSERVED"
    if observation["process_seen"]:
        state = "PROCESS_SEEN"
    if model_id in catalogued:
        state = "MODEL_CATALOGUED"
    if model_id in resident:
        state = "MODEL_RESIDENT"
    if health["healthy"] and health["model_id"] == model_id:
        state = "EXACT_MODEL_ENDPOINT_OBSERVED"

    return {
        "host_id": host_id,
        "os": observation["os"],
        "backend": observation["backend"],
        "endpoint": endpoint,
        "model_id": model_id,
        "observed_at": stamp,
        "observed_state": state,
        "inference_qualified": False,
        "route_eligible": False,
    }
