from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Iterable


_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+.-]*")


@dataclass(frozen=True)
class CapabilityHit:
    source_kind: str
    identifier: str
    score: int
    evidence: str


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(text.casefold()))


def _score(query_tokens: tuple[str, ...], haystack: str) -> int:
    lowered = haystack.casefold()
    score = 0
    for token in query_tokens:
        if token in lowered:
            score += 1
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            score += 2
    return score


class CapabilitySearch:
    def __init__(
        self,
        *,
        repository_catalog: Path | str,
        plugin_catalog: Path | str,
    ) -> None:
        self.repository_catalog_path = Path(repository_catalog)
        self.plugin_catalog_path = Path(plugin_catalog)
        self.repository_payload = json.loads(
            self.repository_catalog_path.read_text(encoding="utf-8")
        )
        self.plugin_payload = json.loads(
            self.plugin_catalog_path.read_text(encoding="utf-8")
        )
        if (
            self.repository_payload.get("schema")
            != "VERA_OS_PRIVATE_PORTFOLIO_CAPABILITY_MAP_V1"
        ):
            raise ValueError("unsupported private portfolio capability catalog")
        if (
            self.plugin_payload.get("schema")
            != "VERA_OS_CHATGPT_PLUGIN_CAPABILITY_INVENTORY_V1"
        ):
            raise ValueError("unsupported plugin capability inventory")
        if self.repository_payload.get("visibility") != "PRIVATE_VERAOS_INTERNAL":
            raise ValueError("repository capability catalog must remain private")
        if self.plugin_payload.get("visibility") != "PRIVATE_VERAOS_INTERNAL":
            raise ValueError("plugin capability inventory must remain private")

    def _repository_hits(
        self,
        query_tokens: tuple[str, ...],
    ) -> Iterable[CapabilityHit]:
        capabilities = self.repository_payload.get("capabilities", {})
        owner_roles: dict[str, list[str]] = {}
        for capability, metadata in capabilities.items():
            role = str(metadata.get("role") or "")
            for owner in metadata.get("owners", []):
                owner_roles.setdefault(str(owner), []).append(
                    f"owner:{capability} {role}"
                )
            for repo in metadata.get("supporting", []):
                owner_roles.setdefault(str(repo), []).append(
                    f"supporting:{capability} {role}"
                )

        for record in self.repository_payload.get("repositories", []):
            repository = str(record.get("repository") or "")
            parts = [
                repository,
                str(record.get("description") or ""),
                str(record.get("purpose") or ""),
                str(record.get("family_id") or ""),
                " ".join(str(x) for x in record.get("capabilities", [])),
                " ".join(str(x) for x in record.get("semantic_signals", [])),
                " ".join(owner_roles.get(repository, [])),
                str(record.get("chatgpt_repo_skill") or ""),
            ]
            evidence = " | ".join(x for x in parts if x)
            score = _score(query_tokens, evidence)
            if score:
                yield CapabilityHit(
                    source_kind="REPOSITORY",
                    identifier=repository,
                    score=score,
                    evidence=evidence,
                )

    def _plugin_hits(
        self,
        query_tokens: tuple[str, ...],
    ) -> Iterable[CapabilityHit]:
        for plugin in self.plugin_payload.get("skill_plugins", []):
            plugin_name = str(plugin.get("plugin") or "")
            for skill in plugin.get("skills", []):
                skill_name = str(skill.get("skill") or "")
                description = str(skill.get("description") or "")
                evidence = f"{plugin_name} {skill_name} {description}".strip()
                score = _score(query_tokens, evidence)
                if score:
                    yield CapabilityHit(
                        source_kind="PLUGIN_SKILL",
                        identifier=f"{plugin_name}/{skill_name}",
                        score=score,
                        evidence=evidence,
                    )

        for namespace in self.plugin_payload.get("tool_namespaces", []):
            namespace_name = str(namespace.get("namespace") or "")
            parts = [namespace_name]
            for action in namespace.get("representative_actions", []):
                parts.append(str(action.get("action") or ""))
                parts.append(str(action.get("description") or ""))
            evidence = " | ".join(x for x in parts if x)
            score = _score(query_tokens, evidence)
            if score:
                yield CapabilityHit(
                    source_kind="TOOL_NAMESPACE",
                    identifier=namespace_name,
                    score=score,
                    evidence=evidence,
                )

    def search(self, query: str, *, limit: int = 20) -> tuple[CapabilityHit, ...]:
        query_tokens = _tokens(str(query or ""))
        if not query_tokens:
            raise ValueError("capability search query is required")
        if type(limit) is not int or limit < 1:
            raise ValueError("capability search limit must be a positive integer")

        hits = [
            *self._repository_hits(query_tokens),
            *self._plugin_hits(query_tokens),
        ]
        hits.sort(
            key=lambda hit: (
                -hit.score,
                hit.source_kind,
                hit.identifier.casefold(),
            )
        )
        return tuple(hits[:limit])
