# VeraOS primary interface / P.O.R.T.A.L. / Vera model integration target

Status: **source-level interface contract candidate**, not a running interface, a trained model, or authority to activate a new route. This document implements the 2026-10-12 direction to make VeraOS the system-facing interface and a trained Vera neural model the preferred local cognition candidate.

## Component ownership

| Component | Responsibility | Not responsible for |
| --- | --- | --- |
| Vera neural model (producer: `vera_model_training`) | Standalone local cognition: interpretation, reasoning, planning and structured *proposals*. Exact weights/export and independent model evaluation required. | Identity continuity, permissions, memory writes, protected effects, deciding whether its own weights are qualified |
| Pre-Active active ModelTarget | Govern the exact current selected cognition target after separate admission, with model artifact, server and freshness binding. | Granting global action authority or accepting a model name as artifact proof |
| P.O.R.T.A.L. | Coordinate tasks, dispatch governed work, consume the selected cognition route, retain exact route/attempt/verification evidence. | Serving as Vera's identity root or assuming all available models are admitted |
| Vera Mono `vera_core.QualifiedVeraRuntime` | Hold persistent identity/runtime state, task and memory governance, and effect gates. | Mistaking generated model text for authorization or a verified external effect |
| **VeraOS** | **Primary human-facing system workspace and operating environment**, across desktop, terminal, voice, mobile/API clients where qualified. Presents Vera, tasks, workers, approvals, receipts, model status and degraded/offline state. | Inventing model selection, duplicating P.O.R.T.A.L.'s scheduler, minting permissions, or storing canonical runtime state in UI state |

The existing P.O.R.T.A.L. Desktop can operate as a **transitional or embedded VeraOS client**. It must not become a second identity root, permanent independent orchestrator, or silent replacement for the intended VeraOS workspace. The preferred OS implementation candidate (NixOS) remains undecided.

## Interface-to-cognition acceptance sequence

1. VeraOS identifies an authenticated session and submits a request over a versioned IPC/API boundary. The request binds a unique ID, actor/session context, intended purpose, permitted task scope and user-visible cancellation state.
2. The resident Vera host checks runtime currentness and chooses the admissible active ModelTarget, not a conveniently named Ollama tag. The target binds model artifact digest, adaptation/quantization metadata, provider/endpoint identity, route generation and freshness window.
3. P.O.R.T.A.L. records target/route selection for the **same** human or autonomous request, with no unapproved model fallback. A worker may use a different *explicitly scoped and qualified* specialist target; this is not identity replacement.
4. The inference provider returns output tagged to its exact request, route and artifact. The host treats this as cognition, not a permission, memory update or effect receipt.
5. The governed Vera runtime validates state/authority, records permitted output provenance and proposed actions, and passes an acceptance/rejection/degraded result back to the **same VeraOS session**.
6. VeraOS displays which model served the response, whether it was qualified, what was proposed versus verified, and which decisions require owner approval. It cannot declare an action completed from fluent output alone.

## Operational states VeraOS must render

| State | Display / behavior |
| --- | --- |
| `NO_MODEL_ADMITTED` | Workspace remains available for state/approvals/receipts; cognition unavailable; **no implicit fallback** |
| `PROVIDER_UNREACHABLE` | No fabricated answer; show stale target and retriable user intent without duplicating an ambiguous attempt |
| `MODEL_ROUTE_STALE` | Requalification required; deny new dispatch on the stale route |
| `MODEL_OUTPUT_UNVERIFIED` | Display as a model proposal, not a verified external action or self-attested qualification |
| `EFFECT_OUTCOME_UNKNOWN` | Surface reconciliation-required status; prevent hidden retry through another route |
| `MODEL_QUALIFIED_AND_CONSUMED` | Show exact artifact/route provenance and model response, without upgrading the response to effect authority |

The UI must not expose secrets, unscoped private project names, confidential chat transcripts, or raw private model traces in shared telemetry. A model switch must not erase or rewrite identity, memory, task lineage, or pending-effect status. Changes to selected production model targets and system activation remain separately authorized operations.

## Training-to-interface gates (in order)

1. **Artifact:** the training producer shows real neural weight mutation or adaptation, pinned base/recipe/dataset/adapter/GGUF digests and a reproducible candidate export. Public bootcamp capsules are *not* trained neural weights.
2. **Independent behavior:** an evaluator that does not control the candidate's training outputs tests unseen semantics/pragmatics, uncertainty, referent preservation, corrections, governed tool/delegation judgment, anti-servility and tool failure; thresholds frozen before reveal.
3. **Provider:** direct standalone KoboldCPP inference passes with exact GGUF/model provenance. A matching name, OpenAI-compatible HTTP endpoint, or Ollama tag alone is insufficient.
4. **Admission:** an authorized issuer binds the exact model candidate to Pre-Active's active ModelTarget, after live provider and artifact verification. No self-admission by the training producer or UI.
5. **Routing:** P.O.R.T.A.L. demonstrably selects that admitted exact target for an actual request and records its route/attempt/result, including fail-closed wrong-artifact and stale-route cases.
6. **Runtime:** `vera_core.QualifiedVeraRuntime` demonstrably consumes that exact response without treating it as permission, canonical memory or verified tool effect.
7. **Interface:** an observed VeraOS workspace request makes a complete UI → IPC → host/Portal → admitted Vera model → governed runtime → UI roundtrip, including offline/degraded and restart recovery.
8. **Release:** independently reviewed acceptance evidence, exact installation plan and separate authority precede switching the live model route or deploying VeraOS.

The existing Draft [training PR #92](https://github.com/thebrazenbeard/vera_model_training/pull/92) supplies a source-level *candidate* training/verification target. Its head and review state must be refreshed before any downstream release decision; its presence is not evidence of actual weights or runtime consumption.

## Hostile review

> **HOSTILE REVIEWER:** Why build a new VeraOS interface protocol if P.O.R.T.A.L. Desktop and the existing Vera IPC already expose a user interface?

**Partially accepted.** Reuse the existing qualified IPC and any valuable Desktop components. VeraOS should own the coherent system-facing workspace experience, **not** invent a second runtime, duplicate Portal's coordinator, or require a new transport merely to satisfy branding. The necessary addition is an acceptance boundary and observable end-to-end tests, not another scheduler.

> **HOSTILE REVIEWER:** Does preferring a Vera-trained model contradict the model-independent agent architecture or make an as-yet-untrained model an OS boot dependency?

**Rejected as a requirement, accepted as a risk.** 'Preferred' means *eligible after independent qualification and explicit selection*, never required to boot, never implicitly substituted, and never identical to Vera's governed identity. If the model is absent/unqualified, VeraOS stays operable in a truthfully degraded state.

## Claim ceiling

This document proves only an authored **source-level target**. It does not prove a Vera neural model exists at a qualified trained weight digest; that KoboldCPP currently serves it; that Pre-Active selected it; that P.O.R.T.A.L. or VeraOS consumed it; or that VeraOS has been built, booted, installed or deployed.
