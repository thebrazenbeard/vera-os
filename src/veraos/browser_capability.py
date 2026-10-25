from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_SCHEMA = "VERA_OS_BROWSER_CAPABILITY_GRANT_V1"
_ALLOWED_MODES = {"INTERACTIVE", "AUTOMATION"}
_ALLOWED_NETWORK_SCOPES = {"OFFLINE", "ALLOWLIST", "GENERAL_WEB"}
_ALLOWED_SCHEMES = {"https", "http"}
_ALLOWED_PROFILE_PERSISTENCE = {"EPHEMERAL", "GOVERNED_PERSISTENT"}
_ALLOWED_DOWNLOAD_MODES = {"DISABLED", "GOVERNED_DIRECTORY"}


class BrowserCapabilityError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BrowserCapabilityError(message)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{name} must be an object")
    return value


def _text(value: object, name: str) -> str:
    text = str(value or "").strip()
    _require(bool(text), f"{name} is required")
    return text


def validate_browser_grant(grant: Mapping[str, Any]) -> None:
    data = _mapping(grant, "browser grant")
    _require(data.get("schema") == _SCHEMA, "unsupported browser grant schema")
    _text(data.get("grant_id"), "grant_id")
    _text(data.get("requester"), "requester")

    mode = _text(data.get("mode"), "mode")
    _require(mode in _ALLOWED_MODES, "unsupported browser mode")

    network = _mapping(data.get("network"), "network")
    scope = _text(network.get("scope"), "network.scope")
    _require(scope in _ALLOWED_NETWORK_SCOPES, "unsupported browser network scope")
    schemes = network.get("allowed_schemes")
    _require(isinstance(schemes, list), "network.allowed_schemes must be a list")
    for scheme in schemes:
        value = _text(scheme, "network scheme").lower()
        _require(value in _ALLOWED_SCHEMES, f"unsupported browser scheme: {value}")
    if scope == "OFFLINE":
        _require(not schemes, "offline browser grant cannot allow network schemes")
    else:
        _require("https" in schemes, "networked browser grant must allow https")

    profile = _mapping(data.get("profile"), "profile")
    persistence = _text(profile.get("persistence"), "profile.persistence")
    _require(
        persistence in _ALLOWED_PROFILE_PERSISTENCE,
        "unsupported browser profile persistence",
    )
    _require(
        profile.get("credential_access") is False,
        "browser grant cannot imply ambient credential access",
    )

    downloads = _mapping(data.get("downloads"), "downloads")
    download_mode = _text(downloads.get("mode"), "downloads.mode")
    _require(
        download_mode in _ALLOWED_DOWNLOAD_MODES,
        "unsupported browser download mode",
    )
    if download_mode == "GOVERNED_DIRECTORY":
        path = _text(downloads.get("path"), "downloads.path")
        _require(
            path.startswith("/var/lib/vera-browser/"),
            "browser downloads must stay inside governed browser state",
        )

    effects = _mapping(data.get("effects"), "effects")
    _require(
        effects.get("protected_effect_authority") is False,
        "browser grant cannot confer protected-effect authority",
    )
    _require(
        effects.get("credential_mutation_authority") is False,
        "browser grant cannot confer credential mutation authority",
    )
    _require(
        effects.get("protected_actions_require_effect_broker") is True,
        "protected browser actions must require the effect broker",
    )
