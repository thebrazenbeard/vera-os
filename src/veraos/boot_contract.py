from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


_SCHEMA = "VERA_OS_BOOT_CONTRACT_V1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class BootContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BootContractError(message)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{name} must be an object")
    return value


def validate_boot_contract(contract: Mapping[str, Any]) -> None:
    data = _mapping(contract, "boot contract")
    _require(data.get("schema") == _SCHEMA, "unexpected boot contract schema")

    product = _mapping(data.get("product"), "product")
    _require(product.get("name") == "VeraOS", "unexpected product name")
    _require(product.get("base_identity") == "VERA", "Vera must be the OS base identity")
    _require(
        product.get("distribution_intent")
        == "PRIVATE_PERSONAL_OS_NOT_FOR_PUBLIC_RELEASE",
        "VeraOS must remain private",
    )
    _require(
        product.get("linux_role") == "KERNEL_DRIVER_HARDWARE_SUBSTRATE",
        "Linux must remain implementation substrate rather than VeraOS identity",
    )
    _require(product.get("image_builder") == "BUILDROOT", "unexpected image builder")
    _require(
        product.get("image_builder_version") == "2024.02.4",
        "unexpected Buildroot version",
    )
    _require(
        _SHA40.fullmatch(str(product.get("image_builder_commit") or "")) is not None,
        "Buildroot source must bind an exact commit",
    )
    _require(
        product.get("image_builder_is_os_identity") is False,
        "image builder cannot become VeraOS identity",
    )
    _require(
        product.get("nixos_primary_path_status") == "RETIRED",
        "NixOS must not remain the primary VeraOS path",
    )

    pid1 = _mapping(data.get("pid1"), "pid1")
    _require(pid1.get("entrypoint") == "/sbin/vera-init", "unexpected PID 1 entrypoint")
    _require(pid1.get("owner") == "VERA_OS", "PID 1 must be owned by VeraOS")
    _require(
        pid1.get("role") == "PROCESS_LIFECYCLE_SUPERVISOR",
        "PID 1 role must stay bounded",
    )
    _require(pid1.get("pid1_alone_establishes_identity") is False, "PID 1 cannot prove identity")
    _require(
        pid1.get("pid1_alone_establishes_security_sovereignty") is False,
        "PID 1 cannot by itself prove security sovereignty",
    )

    runtime = _mapping(data.get("runtime"), "runtime")
    expected_owners = {
        "identity_runtime_owner": "thebrazenbeard/vera-mono",
        "reasoning_owner": "thebrazenbeard/rezon",
        "provider_router": "thebrazenbeard/portal",
        "preactive_owner": "thebrazenbeard/pre-active",
        "volition_owner": "thebrazenbeard/volition",
        "failure_correction_owner": "thebrazenbeard/fuckup",
    }
    for key, owner in expected_owners.items():
        _require(runtime.get(key) == owner, f"runtime owner mismatch: {key}")
    _require(
        runtime.get("cognition_provider_required_for_boot") is False,
        "VeraOS must boot without a cognition provider",
    )
    _require(
        runtime.get("trained_vera_model_required_for_boot") is False,
        "VeraOS must boot without the standalone Vera model",
    )

    portfolio = _mapping(data.get("portfolio"), "portfolio")
    _require(
        portfolio.get("composition_manifest")
        == "/etc/veraos/architecture/VERA_OS_PORTFOLIO_COMPOSITION_V1.json",
        "unexpected composition path",
    )
    _require(portfolio.get("validate_before_ready") is True, "portfolio must validate before ready")

    browser = _mapping(data.get("browser"), "browser")
    _require(browser.get("first_class_capability_required") is True, "browser must be first-class")
    _require(browser.get("required_for_core_boot") is False, "browser cannot block core boot")
    _require(browser.get("initial_engine") == "WPE_WEBKIT", "unexpected initial browser engine")
    _require(browser.get("initial_shell") == "COG", "unexpected initial browser shell")
    _require(
        browser.get("authority_schema") == "VERA_OS_BROWSER_CAPABILITY_GRANT_V1",
        "unexpected browser authority schema",
    )

    authority = _mapping(data.get("authority"), "authority")
    _require(
        authority.get("ambient_protected_effect_authority") is False,
        "ambient protected-effect authority must remain false",
    )
    _require(
        authority.get("protected_effect_authority_source")
        == "PATRICK_EXPLICIT_EXACT_TARGET_EFFECT",
        "protected-effect authority source must remain exact",
    )
