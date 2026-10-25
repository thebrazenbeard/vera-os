"""Test-only deterministic Pre-Active model. NOT copied into VeraOS rootfs.

The production resident has no provider descriptor/endpoint or model-admission
callback. This fixture exercises the same Pre-Active Engine and PORTAL selector,
but its model.respond() is a pure function: no network, no Ollama, no tools.
"""
from __future__ import annotations
import time


def make_offline_fixture(response: str = "fixture-console-response"):
    calls: list[tuple[list[dict], list[dict]]] = []

    def execute(task: str, request_id: str, store: object) -> dict:
        import portal
        from pre_active.engine import Engine, ModelResponse
        from pre_active.tools import ToolRegistry
        from pre_active.context import ContextAssembler
        from veraos.native_cognition import AdmittedTextRoute, execute_text_request

        class PureModel:
            def respond(self, *, messages: list[dict], tools: list[dict]) -> ModelResponse:
                assert tools == []  # protected effects are not executable
                calls.append((messages, tools))
                return ModelResponse(final_text=response)

        advertisement = portal.PortalRouteAdvertisement(
            adapter_id="pre-active-offline-fixture",
            route_id="offline-fixture",
            node_id="veraos",
            target_kind="MODEL",
            target_id="offline-deterministic",
            capabilities=("text",),
            effect_capabilities=("COGNITION_TURN",),
            authorized_effects=("COGNITION_TURN",),
            available=True, attached=True, current=True,
        )
        request = portal.PortalRouteRequest(
            subject_kind="COGNITION_REQUEST",
            subject_id="resident-text",
            node_id="veraos",
            target_kind="MODEL",
            target_id="offline-deterministic",
            required_capabilities=("text",),
            required_effect="COGNITION_TURN",
        )
        binding = portal.resolve_portal_route(request, [advertisement])
        engine = Engine(
            store=store,
            model=PureModel(),
            tools=ToolRegistry(store),
            context=ContextAssembler(store, max_chars=4096),
            system_prompt="Deterministic source-only fixture. No network or tools.",
            worker_id="veraos-source-fixture",
            max_steps=2,
            max_autonomous_turns_per_run=0,
            max_consecutive_endogenous_turns=0,
        )
        return execute_text_request(
            AdmittedTextRoute(
                store=store, engine=engine, binding=binding,
                provider_id="offline-fixture", model="offline-deterministic",
            ), task=task, request_id=request_id, now=time.time(),
        )

    return execute, calls
