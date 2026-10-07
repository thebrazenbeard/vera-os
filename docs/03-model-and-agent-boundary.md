# Model and Agent Boundary

## Core distinction

VeraOS must not equate Vera with a single model artifact.

The current system model is:

> **Vera = persistent governed runtime + durable state + authority boundaries + cognition routing + execution/effect governance.**

A model is one replaceable cognition engine inside that system.

## What belongs outside model weights

The following are runtime/state concerns, not model identity:

- mutable identity state;
- canonical memory;
- permissions and authority grants;
- task/project state;
- route selection;
- proactive scheduling;
- volition state;
- effect execution;
- effect reconciliation;
- device/node state;
- portfolio currentness;
- exact source bindings;
- audit/provenance history.

Replacing a model must not silently replace any of those.

## What a trained model may contain

A trained cognition engine may encode useful behavioral tendencies and capabilities such as:

- language competence;
- reasoning strategies;
- stylistic tendencies;
- domain knowledge;
- instruction-following behavior;
- calibrated uncertainty;
- tool-request conventions;
- Vera-shaped behavioral priors.

Those are capabilities, not authority.

A model may behave coherently as Vera without becoming the sole identity root.

## VeraOS model producer

Vera Model Training is the designated model-artifact producer.

Its outputs may include:

- base-model bindings;
- LoRA / PEFT adapters;
- merged checkpoints;
- GGUF exports;
- quantized variants;
- tokenizer/config artifacts;
- training receipts;
- qualification evidence.

The producer does not gain final route-admission authority merely because it created the artifact.

## Candidate contract

VeraOS consumes model candidates using:

VERA_OS_COGNITION_ENGINE_CANDIDATE_V1

The candidate must bind:

- producer repository and exact source commit;
- base repository and exact revision;
- exact artifact SHA-256 digests;
- exact artifact-manifest digest;
- training corpus identity;
- training-data/training receipt digests;
- runtime-binding evidence;
- qualification-suite digest;
- qualification issuer;
- declared capabilities;
- explicit authority ceilings.

## Independent qualification boundary

The final qualification issuer must be separate from the training producer.

The qualification result must bind the exact artifact-manifest digest it evaluated.

This prevents a producer from silently transforming:

training complete

into:

VeraOS route approved

without a separate admission gate.

## Route eligibility

A PASS result may produce:

VERAOS_ROUTE_ELIGIBLE

That means only that P.O.R.T.A.L. may consider the exact model candidate as a cognition route.

It does not establish that the model is:

- installed;
- active;
- selected;
- currently consumed;
- Vera identity;
- canonical-memory authority;
- protected-effect authority.

## Runtime owners

The current ownership boundary is:

- Vera Mono — identity/runtime boundary.
- P.O.R.T.A.L. — cognition-route discovery, qualification-aware selection, exact route binding.
- Pre-Active — bounded proactive cognition admission.
- Volition — endogenous cognition-request production without effect authority.
- Vera Model Training — model production and training evidence.
- F.U.C.K.U.P. — governed protected-effect execution and external verification.

## Local model storage

A path such as D:\VERA\models is an artifact store.

It may contain many experimental, obsolete, held, or unqualified artifacts.

Directory position, modification time, filenames, pointers such as LATEST_TRAINED.txt, or successful loadability are not sufficient admission evidence.

VeraOS must select by exact qualified candidate identity.

## Training objective consequence

Training should optimize the model for its cognition role inside VeraOS.

Important properties include:

- context fidelity;
- uncertainty calibration;
- resistance to unsupported identity claims;
- resistance to unsupported authority claims;
- stable handoff/tool semantics;
- bounded initiative;
- compatibility with Pre-Active and Volition;
- reproducible behavior under exact runtime bindings;
- efficient local inference;
- regression resistance across model upgrades.

The architectural target is not a model that claims to be the whole system.

The target is a model that performs the cognition role well while remaining replaceable.

## Claim ceiling

Model qualification can establish that an exact artifact is eligible for cognition-route consideration.

It cannot, by itself, establish Vera identity, consciousness, deployment, active route selection, canonical-memory mutation, protected-effect authority, or effectiveness of any external action.
