#!/usr/bin/env python3
"""Statically check the minimal Vera Mono/PORTAL resident import contract.

This checker reads source only. It never imports or executes staged packages,
grants a model/provider permission, or qualifies an installed guest image.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


MAX_SOURCE_BYTES = 1_048_576
CONTRACT = {
    "vera_mono/packages/vera_core/src/vera_core/__init__.py": (
        "QualifiedVeraRuntime", "VeraStateDirectory",
    ),
    "vera_mono/packages/vera_core/src/vera_core/qualified_runtime.py": (
        "QualifiedVeraRuntime",
    ),
    "vera_mono/packages/vera_core/src/vera_core/local_conversation.py": (
        "ConversationError", "SourceObservationConflict", "open_message",
        "recover_message", "reserve_source_trial", "seal_source_observation",
        "recover_conversation",
    ),
    "vera_mono/packages/vera_core/src/vera_core/portal_task_handoff.py": (
        "export_portal_route_request",
    ),
    "portal/portal/__init__.py": (
        "PortalRouteAdvertisement", "resolve_portal_route",
    ),
    "portal/portal/vera_task_handoff.py": ("assess_vera_task_route",),
}


def _defined_names(source: bytes, label: str) -> set[str]:
    parsed = ast.parse(source, filename=label)
    names: set[str] = set()
    for item in parsed.body:
        if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(item.name)
        elif isinstance(item, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in item.names)
        elif isinstance(item, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in item.names)
    return names


def verify(components_root: Path) -> dict:
    """Return deterministic, non-executing source readiness with fail-closed errors."""
    root = components_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("components_root must be a directory")
    defects = []
    for relative, expected in CONTRACT.items():
        entry = root.joinpath(*relative.split("/"))
        # Do not follow an untrusted link at any intermediate component.
        chain = root
        linked = False
        for name in relative.split("/"):
            chain /= name
            if chain.is_symlink():
                linked = True
                break
        if linked:
            defects.append(f"{relative}: symlink not allowed")
            continue
        if not entry.is_file():
            defects.append(f"{relative}: required source missing")
            continue
        if entry.stat().st_size > MAX_SOURCE_BYTES:
            defects.append(f"{relative}: source exceeds 1 MiB")
            continue
        try:
            found = _defined_names(entry.read_bytes(), relative)
        except (SyntaxError, UnicodeError, ValueError) as exc:
            defects.append(f"{relative}: unparseable Python ({type(exc).__name__})")
            continue
        for symbol in expected:
            if symbol not in found:
                defects.append(f"{relative}: missing exported or defined {symbol}")
    return {
        "schema": "VERAOS_RESIDENT_DEPENDENCY_SOURCE_GATE_V1",
        "status": "SOURCE_CONTRACT_CANDIDATE" if not defects else "HELD_SOURCE_CONTRACT",
        "source_only": True,
        "guest_import_qualified": False,
        "installed": False,
        "model_admitted": False,
        "authority_granted": False,
        "required_files": len(CONTRACT),
        "defects": defects,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--components-root", type=Path, required=True)
    options = parser.parse_args(argv)
    try:
        result = verify(options.components_root)
    except (OSError, ValueError) as exc:
        result = {
            "schema": "VERAOS_RESIDENT_DEPENDENCY_SOURCE_GATE_V1",
            "status": "HELD_SOURCE_CONTRACT",
            "source_only": True,
            "guest_import_qualified": False,
            "installed": False,
            "model_admitted": False,
            "authority_granted": False,
            "required_files": len(CONTRACT),
            "defects": [f"invalid components_root or filesystem: {type(exc).__name__}"],
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "SOURCE_CONTRACT_CANDIDATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
