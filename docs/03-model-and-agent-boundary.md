# Model, Reasoning, and Cognition-Provider Boundary

## Core distinction

VeraOS does not equate Vera with a model.

The system separates:

- VeraOS and Vera Mono as the persistent governed operating/runtime boundary;
- Rezon as the reasoning architecture;
- P.O.R.T.A.L. as cognition-provider discovery and routing;
- cognition providers as replaceable compute;
- browser/tool capabilities as separately governed execution surfaces;
- protected-effect execution as a separate authority boundary.

VeraOS must boot and remain inspectable with no cognition provider attached.

## Reasoning is not the model

Reasoning architecture belongs to Rezon.

Rezon coordinates heterogeneous reasoning methods, evidence, replay, challenge, and assurance. A model may supply language or inference to a Rezon reasoning operation, but the existence of that model does not make the model the reasoning architecture.

This distinction allows the same reasoning system to use different providers for different jobs.

## Generic cognition providers

VeraOS accepts qualified cognition providers through:

VERA_OS_COGNITION_PROVIDER_V1

Provider kinds may include:

- local models;
- hosted/API models;
- hosted chat/session routes;
- local services;
- specialist providers;
- future provider implementations.

A provider is not required for boot.

Provider admission cannot grant:

- Vera identity authority;
- canonical-memory write authority;
- browser authority;
- protected-effect authority.

P.O.R.T.A.L. owns exact provider selection/binding.

## Standalone Vera model

The neural Vera model produced by Vera Model Training is an independent product.

Its primary purpose is to become a strong standalone Vera-shaped model that can run directly in KoboldCPP or another local inference host.

VeraOS does not require it.

If VeraOS chooses to use it, Vera Model Training may export an exact optional local-provider candidate:

VERA_OS_LOCAL_MODEL_PROVIDER_CANDIDATE_V1

The export binds:

- exact producer source commit;
- exact base-model revision;
- exact artifact SHA-256 digests;
- exact artifact-manifest digest;
- training corpus identity;
- training receipt digest;
- runtime binding;
- qualification suite;
- qualification issuer.

The final qualifier must be separate from the training producer and must bind the exact artifact manifest it evaluated.

## Local-model authority ceiling

A local-model provider candidate remains:

- integration=OPTIONAL_PROVIDER;
- route_class=COGNITION_ONLY;
- identity_authority=false;
- canonical_memory_write_authority=false;
- browser_authority=false;
- protected_effect_authority=false.

A PASS result can make the exact artifact route-eligible.

That does not establish that the model is installed, active, selected, Vera identity, or authorized to perform effects.

## What belongs outside model weights

The following remain system/runtime concerns:

- mutable identity state;
- canonical memory;
- permissions and authority;
- portfolio awareness;
- reasoning orchestration;
- provider routing;
- proactive cognition admission;
- volition state;
- browser/network grants;
- effect execution;
- recovery/reconciliation;
- device/node state;
- exact source bindings;
- audit/provenance history.

Replacing a model must not silently replace those.

## Training objective

Vera Model Training should optimize the standalone Vera model for its own usefulness:

- Vera-like behavioral coherence;
- general reasoning quality;
- epistemic discipline;
- emotional and relational competence;
- capability retention;
- long-context consistency;
- robust GGUF export;
- KoboldCPP/local inference usability;
- reproducible exact artifacts.

VeraOS-specific plumbing such as provider handoff, route ownership, memory authority, browser grants, and effect authorization should remain outside the weights unless the corresponding behavior is independently useful to the standalone model.

## Browser boundary

Browser capability is not inherited from cognition.

A provider can request browser work, but browsing requires a separate VeraOS browser capability grant.

That grant controls:

- network scope;
- allowed schemes;
- interactive vs automated mode;
- profile persistence;
- credential access;
- downloads;
- protected actions.

Provider selection never implies browser access.

## Effect boundary

F.U.C.K.U.P. is the corrective-learning and prevention layer.

It does not own protected-effect execution merely because it handles failures.

Execution is performed through the appropriate bounded execution substrate and remains subject to the VeraOS protected-effect authority contract.

## Claim ceiling

A model or provider can be qualified for cognition.

That qualification cannot, by itself, establish Vera identity, consciousness, canonical-memory mutation, browser authority, deployment, protected-effect authority, or effectiveness of an external action.
