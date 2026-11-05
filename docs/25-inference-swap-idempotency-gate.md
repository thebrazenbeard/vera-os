# Local inference swap: request identity and output-provenance gate

**Status: SOURCE-FIXTURE / HOLD.** This change was developed against `vera-os` Draft #74 `fb14d5ce470abdc2f04bb21e5db7a7c7e3e69cd7`, accepted `main` `31b66b6ff317eb981c4bd8fcc4ae6e5db1d21adf`. No model, GPU, socket, user session, external identity issuer, Vera Mono runtime, or protected-effect broker ran in these tests. Authorized Windows root remains `D:\VERA`; `C:\VERA` is obsolete. No paid service or deployment is authorized.

## Falsifier demonstrated in the existing code

`execute_text_request` originally queued its durable event under `veraos-text:{request_id}` with only the requested task and an empty capability list. When an earlier request had completed on synthetic backend A, replaying its **same ID and task** under backend B returned A's stored text while reporting **B's** current `provider_id` and route metadata. No B generation occurred. This is a concrete **source API provenance mislabel**, not a live model attack or evidence of backend identity.

The minimal change binds `adapter_id`, `route_id`, `provider_id` and `model` into the event payload, alongside `task` and `capabilities=[]`. A strict deduplicating event store must reject the same idempotency key if any bound route field changes; a retry with the same route can reuse the run. The returned result now also carries the **declared** `model` identifier. A model alias is **not** a weight checksum.

New offline tests (`tests/test_inference_swap_source.py`) exercise the actual VeraOS `execute_text_request` function with an in-memory SQLite store/engine double and synthetic output only:

1. Independent mock backends produce separate synthetic text for distinct request IDs while the fake externally held identity/state object is unchanged.
2. Same task/request ID replayed under another provider is rejected before new mock execution.
3. Same provider rebound to a different model with the same request ID is likewise rejected.
4. Idempotent same-route retry returns the existing run with no second execution.
5. The durable task payload carries the route tuple and `capabilities=[]`.
6. Text claiming protected-effect authorization remains ordinary text, with no protected-effect invocation in the fixture.

These are **SOURCE TESTS**, not a real model swap or qualified memory/state readback. The fake store deliberately enforces payload equality the same way existing integrated native cognition tests expect the staged Pre-Active store to reject conflicting task payloads. Until the exact pinned Pre-Active closure is present, compatibility with its event parser and actual durable cross-process replay remains **HOLD**.

> **Hostile challenge — artifact alias substitution:** Binding a model *name* and route ID does not stop an operator or compromised provider from replacing the GGUF/model bytes behind that name. Real provenance requires an independently verified immutable artifact digest and a trusted host-owned admission binding. This patch must not be represented as cryptographic integrity.

> **Hostile challenge — storage collision:** If a different `Store.enqueue_event` implementation silently returns a previously created event for the same key **without comparing its payload**, the protection fails. The source fixture is not a substitute for an exact Pre-Active integration test and a restarting process on a qualified host. Reject/hold non-conforming stores; never silently relabel old output.

> **Hostile challenge — identity illusion:** The simulated unchanged `identity_id` is merely a held Python dict. It does not verify Windows token/SID ownership, consent, persistent Vera Mono identity, memory isolation, or any statement about nonbiological personhood.

## Release/host gates

- Run this test plus the existing `test_native_admitted_cognition.py` against the exact pinned `pre_active` and `portal` source closure and verify route replay rejection and old event migration behavior. Existing pre-change durable events may fail safe on retry because they lack `route_identity`; do not silently migrate/relabel them.
- Require signed/host-attested source for model artifact hash, exact backend binary, token-generation observation and authorized state projection before an **actual** model swap. Use new request IDs for intentionally new route executions; do not reuse IDs to force reexecution.
- Admit generated text only as `UNVERIFIED`, with no model-derived task, effect, identity or memory grant. Preserve `D:\VERA`, $0, no autostart, no model copy to Lappy, and explicit authorization before any physical host change.
