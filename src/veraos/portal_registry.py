from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .portfolio_awareness import validate_capability_map


_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class PortalRegistryError(ValueError):
    pass


def _identifier(value: object, *, fallback: str | None = None) -> str:
    text = str(value or fallback or "").strip().casefold()
    text = re.sub(r"[^a-z0-9._-]+", "-", text).strip("-.")
    if not text or _ID_RE.fullmatch(text) is None:
        raise PortalRegistryError(f"cannot derive Portal-safe identifier from {value!r}")
    return text


def _repository_project_id(repository: str) -> str:
    owner, separator, name = repository.partition("/")
    if not separator or not owner or not name:
        raise PortalRegistryError(f"repository must use owner/name: {repository!r}")
    return _identifier(name)


def build_portal_project_registry(
    capability_map: Mapping[str, Any],
) -> dict[str, object]:
    """Build a Project Runner-compatible private registry for P.O.R.T.A.L.

    This is an awareness bridge only. Non-archived projects are HELD rather
    than SCHEDULABLE so portfolio membership cannot silently become admission,
    routing, execution authority, or protected-effect authority.
    """
    validate_capability_map(capability_map)

    projects: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    records = sorted(
        capability_map["repositories"],
        key=lambda row: str(row["repository"]).casefold(),
    )

    for row in records:
        repository = str(row["repository"]).strip()
        project_id = _repository_project_id(repository)
        if project_id in seen_ids:
            raise PortalRegistryError(
                f"repository names collide after Portal-safe normalization: {project_id}"
            )
        seen_ids.add(project_id)

        raw_capabilities = row.get("capabilities")
        if not isinstance(raw_capabilities, list) or not raw_capabilities:
            raise PortalRegistryError(
                f"repository must expose semantic capabilities: {repository}"
            )
        capabilities = sorted(
            {str(value).strip() for value in raw_capabilities if str(value).strip()}
        )
        if not capabilities:
            raise PortalRegistryError(
                f"repository must expose semantic capabilities: {repository}"
            )

        archived = row.get("archived")
        private = row.get("private")
        if not isinstance(archived, bool) or not isinstance(private, bool):
            raise PortalRegistryError(
                f"repository archived/private flags must be boolean: {repository}"
            )

        raw_family = row.get("family_id")
        family_id = _identifier(raw_family, fallback=project_id)

        projects.append(
            {
                "id": project_id,
                "name": repository.split("/", 1)[1],
                "visibility": "private" if private else "public",
                "repositories": [repository],
                "capabilities": capabilities,
                "assignment_scope": "NONE",
                "review_scope": "NONE",
                "family_id": family_id,
                "scheduling_state": "ARCHIVED" if archived else "HELD",
                "scope_note": (
                    "VERAOS_PRIVATE_PORTFOLIO_AWARENESS_ONLY; "
                    "currentness, scheduling activation, route binding, and "
                    "effect authority require separate live evidence."
                ),
            }
        )

    return {"projects": projects}


def write_portal_project_registry(
    path: Path,
    capability_map: Mapping[str, Any],
) -> str:
    payload = build_portal_project_registry(capability_map)
    raw = (
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()
