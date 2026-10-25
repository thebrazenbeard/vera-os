"""Optional manual-admission, cognition-only native Pre-Active route.

The default VeraOS resident never loads this module or grants a provider.
Only an already-verified explicit VeraOS descriptor and an exact healthy
loopback target can construct this service. No tools or effect transports.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import re
from typing import Any

from .cognition_provider import provider_route_eligible, validate_provider


_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")


@dataclass
class AdmittedTextRoute:
    store: Any
    engine: Any
    binding: Any
    provider_id: str
    model: str


def admit_local_text_route(
    *,
    store: Any,
    portal: Any,
    provider: dict,
    base_url: str,
    model: str,
    timeout_seconds: float = 10,
) -> AdmittedTextRoute:
    """Validate policy, probe exact model and invoke actual P.O.R.T.A.L. selector.

    Caller is responsible for authenticating the signed/qualified source
    of provider data. This method validates shape and local technical
    readiness only, it does not independently establish qualification.
    """
    validate_provider(provider)
    if not provider_route_eligible(provider):
        raise RuntimeError("unqualified cognition provider remains HELD")
    if provider["provider_kind"] not in {"LOCAL_MODEL", "LOCAL_SERVICE"}:
        raise ValueError("only locally bound model/service routes can be admitted")
    transport = provider["transport"]
    if transport["kind"] != "OPENAI_COMPATIBLE_HTTP":
        raise ValueError("only locally bound OpenAI-compatible transport is supported")
    if "text" not in provider["capabilities"]:
        raise ValueError("text capability is required")
    if not (0 < timeout_seconds <= 120):
        raise ValueError("bounded model timeout must be positive and <=120s")

    targets = importlib.import_module("pre_active.model_targets")
    target = targets.ModelTarget(
        name=provider["provider_id"], provider="openai-compatible",
        base_url=base_url, model=model, api_key_env=None,
    )
    if transport["attachment"] != target.base_url:
        raise ValueError("provider's exact endpoint differs from the admitted target")
    health = targets.probe_model_target(
        target, env={}, timeout_seconds=min(timeout_seconds, 5),
    )
    if health.get("ready") is not True:
        raise RuntimeError("requested exact local model was not ready")

    adv = portal.PortalRouteAdvertisement(
        adapter_id="pre-active-openai-compatible",
        route_id=provider["provider_id"],
        node_id="veraos",
        target_kind="MODEL",
        target_id=target.model,
        capabilities=("text",),
        effect_capabilities=("COGNITION_TURN",),
        authorized_effects=("COGNITION_TURN",),
        available=True,
        attached=True,
        current=True,
    )
    req = portal.PortalRouteRequest(
        subject_kind="COGNITION_REQUEST",
        subject_id="resident-text",
        node_id="veraos",
        target_kind="MODEL",
        target_id=target.model,
        required_capabilities=("text",),
        required_effect="COGNITION_TURN",
    )
    binding = portal.resolve_portal_route(req, [adv])

    engine_module = importlib.import_module("pre_active.engine")
    context_module = importlib.import_module("pre_active.context")
    tools_module = importlib.import_module("pre_active.tools")
    adapter_module = importlib.import_module("pre_active.providers.openai_compatible")
    model_adapter = adapter_module.OpenAICompatibleAdapter(
        base_url=target.base_url, model=target.model,
        api_key=None, timeout_seconds=timeout_seconds,
    )
    engine = engine_module.Engine(
        store=store,
        model=model_adapter,
        tools=tools_module.ToolRegistry(store),  # Empty: no protected tools.
        context=context_module.ContextAssembler(store, max_chars=4096),
        system_prompt=(
            "You are a local text inference component within VeraOS, "
            "not Vera's identity or canonical state authority. "
            "Answer the request with plain text. No tools or external actions."
        ),
        worker_id="veraos-local-text",
        max_steps=2,
        max_autonomous_turns_per_run=0,
        max_consecutive_endogenous_turns=0,
    )
    return AdmittedTextRoute(store, engine, binding, provider["provider_id"], target.model)


def execute_text_request(
    admitted: AdmittedTextRoute,
    *,
    task: str,
    request_id: str,
    now: float,
) -> dict[str, Any]:
    """Durably queue, execute bounded steps; never fake successful cognition."""
    if not isinstance(task, str) or not task.strip() or len(task) > 2048:
        raise ValueError("task must be nonempty text no longer than 2048 characters")
    if not isinstance(request_id, str) or _REQUEST_ID.fullmatch(request_id) is None:
        raise ValueError("request_id must be a stable bounded token")

    store = admitted.store
    event_id = store.enqueue_event(
        kind="task.requested",
        payload={"task": task.strip(), "capabilities": []},
        priority=0,
        dedup_key=f"veraos-text:{request_id}",
        now=now,
    )
    # Idempotent retry: a completed event binds to the same durable run.
    row = store.connection.execute(
        "SELECT id FROM runs WHERE source_event_id=?", (event_id,),
    ).fetchone()
    if row is None:
        store.append_journal(
            event_type="VERAOS_COGNITION_ROUTE_SELECTED",
            subject_id=event_id,
            payload={
                "adapter_id": admitted.binding.adapter_id,
                "route_id": admitted.binding.route_id,
                "provider_id": admitted.provider_id,
                "model": admitted.model,
                "effect_class": "COGNITION_ONLY",
            },
            now=now,
        )

    run_id = str(row["id"]) if row else None
    for index in range(4):
        if run_id is not None:
            run = store.get_run(run_id)
            if run["status"] in {"COMPLETED", "FAILED", "BLOCKED", "CANCELLED"}:
                break
        admitted.engine.run_once(now=now + index * 0.02)
        if run_id is None:
            row = store.connection.execute(
                "SELECT id FROM runs WHERE source_event_id=?", (event_id,),
            ).fetchone()
            if row is not None:
                run_id = str(row["id"])
    if run_id is None:
        return {
            "status": "PENDING", "run_id": None, "final_text": None,
            "event_id": event_id, "route_id": admitted.binding.route_id,
            "provider_id": admitted.provider_id,
        }
    run = store.get_run(run_id)
    return {
        "status": run["status"],
        "run_id": run_id,
        "event_id": event_id,
        "final_text": run["final_text"] if run["status"] == "COMPLETED" else None,
        "route_id": admitted.binding.route_id,
        "provider_id": admitted.provider_id,
    }
