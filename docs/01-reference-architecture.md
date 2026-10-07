# Reference Architecture

## Conceptual stack

```text
Patrick / authorized interfaces
        |
        +-- VeraOS Desktop
        +-- browser UI
        +-- terminal
        +-- voice
        +-- mobile client
        +-- API / automation
        |
        v
+--------------------------------------------------+
|                     VeraOS                       |
| private persistent governed operating substrate |
|                                                  |
| Vera Mono identity/runtime boundary              |
| durable state + memory governance                |
| portfolio capability awareness                   |
| permissions and authority                        |
| Pre-Active admission + Volition                  |
| effect governance + recovery                     |
+-------------------------+------------------------+
                          |
             cognition request exists
                          |
                          v
                +-------------------+
                |       Rezon       |
                | reasoning methods |
                | evidence / replay |
                +---------+---------+
                          |
                          v
                +-------------------+
                |    P.O.R.T.A.L.   |
                | provider discovery|
                | exact route bind  |
                +---------+---------+
                          |
        +-----------------+------------------+
        |                 |                  |
        v                 v                  v
 hosted/session      local model        specialist/API
   provider            provider             provider
        |                 |                  |
        +-----------------+------------------+
                          |
                          v
                 reasoning result
                          |
                          v
               governed state integration

Separate execution/tool plane:
 filesystem / Git / shell / DB
 browser / network / services
 workstation bridges / containers
 schedulers / devices / nodes
                          |
                          v
                 protected-effect gate
                          |
                          v
                        NixOS
                          |
                       hardware
```

VeraOS must boot and restore state with **no cognition provider attached**. A missing provider is a degraded cognition state, not an OS boot failure.

## Portfolio awareness before architecture

VeraOS does not treat repository names as an inventory only.

Before assigning a new capability:

1. search the private VeraOS portfolio capability map;
2. search available plugin/tool capabilities;
3. identify known capability owners;
4. explicitly REUSE, EXTEND, SUPERSEDE, or REJECT every known owner with evidence;
5. send unknown capabilities through Discovery before assigning them.

Discovery owns portfolio capability discovery.

Semantic Atlas may support semantic relationship representation.

P.O.R.T.A.L. consumes the resulting catalog for coordination.

This rule exists to prevent new architecture from being invented merely because an existing portfolio capability was not salient in the current conversation.

## Reasoning architecture

Rezon owns the reasoning architecture.

Its role is to coordinate heterogeneous methods and evidence rather than to stand for one specific neural model.

Reasoning may involve:

- deduction;
- induction;
- abduction;
- causal reasoning;
- counterfactual reasoning;
- planning;
- analogy;
- probabilistic inference;
- semantic reasoning;
- adversarial challenge;
- replay and assurance.

A cognition provider supplies compute/language/inference to that process when needed.

## Cognition-provider layer

P.O.R.T.A.L. owns qualified provider discovery and exact route binding.

The generic provider contract is:

VERA_OS_COGNITION_PROVIDER_V1

Potential providers include:

- hosted ChatGPT/session routes;
- API-backed models;
- local models;
- the standalone Vera model through KoboldCPP;
- local services;
- specialist providers.

Provider selection does not grant identity, memory-write, browser, or protected-effect authority.

## Standalone Vera model

The trained Vera neural model remains independent from VeraOS.

It may be used directly through KoboldCPP without VeraOS.

If VeraOS uses it, the model enters through the optional local-provider contract:

VERA_OS_LOCAL_MODEL_PROVIDER_CANDIDATE_V1

That is an integration adapter, not an OS dependency.

## Browser and network

Browser capability is a first-class execution/tool surface.

Interactive or automated browsing requires an explicit VeraOS browser grant.

A cognition provider may request browsing, but cannot inherit browser authority from provider selection.

The browser boundary separately governs:

- network scope;
- schemes;
- profiles;
- credentials;
- downloads;
- protected actions.

Current NixOS source provisions Chromium and Firefox plus a dedicated `vera-browser` system identity.

## Runtime identity

The architectural referent is Vera, not a model file, chat session, process ID, or boot instance.

Vera Mono is the preferred governed identity/runtime boundary.

A process such as `verad` may coordinate local services, but process survival alone does not establish identity or currentness. Durable state must be reloaded and validated after restart.

## Core service ownership

Current source-level ownership is:

- Vera Mono — identity/runtime boundary.
- Discovery — portfolio capability discovery.
- Rezon — reasoning architecture.
- P.O.R.T.A.L. — portfolio coordination and cognition-provider routing.
- Pre-Active — proactive cognition admission.
- Volition — endogenous drive/want/goal state.
- F.U.C.K.U.P. — correction and prevention.
- Project Runner / Executor / WorkBridgeMCP — bounded execution mechanisms.
- Deep Memory Storage / Lantern / Roots / Temporal / Ingest — distinct durable evidence/provenance/time/intake mechanisms.
- Vera Control Plane — administration and control-plane custody.
- Vera Mesh — node/transport architecture.

No one role receives ambient protected-effect authority from ownership.

## Protected effects

Protected-effect authority remains:

PATRICK_EXPLICIT_EXACT_TARGET_EFFECT

Planning, reasoning, routing, correction, provider selection, or tool availability does not constitute effect authority.

Actual effects must be bound to the exact target and mechanism and externally verified where applicable.

## Sessions

A conversation is a session surface, not where Vera exists.

Desktop, browser, coding, voice, mobile, and other sessions can attach to the same governed runtime while retaining scoped context and permissions.

## Multi-worker execution

Delegation is a bounded runtime primitive.

A task may be divided into read-only analysis, implementation, review, and verification workers, but workers do not inherit Vera-wide permissions.

P.O.R.T.A.L. and Project Runner coordinate work; capability ownership still comes from the portfolio catalog rather than worker improvisation.

## Failure correction

When a failure reveals a reusable prevention rule, F.U.C.K.U.P. should capture that rule.

The specific class addressed by the current portfolio-awareness work is:

> existing capability was present in the portfolio but was bypassed because it was not semantically surfaced during architecture design.

The prevention is the explicit capability-owner disposition gate.

## Persistence and restart

A reboot is runtime interruption followed by recovery from durable state.

A safe recovery path should:

1. stop new protected effects;
2. checkpoint durable task/effect state;
3. terminate services;
4. restart the OS/runtime;
5. validate the private capability catalog and composition lock;
6. reload durable state;
7. reconcile incomplete work and ambiguous effects;
8. restore available cognition/browser/tool capabilities;
9. resume only work whose target and authority remain current.

This establishes continuity of governed system state without treating process continuity as proof of uninterrupted private experience.
