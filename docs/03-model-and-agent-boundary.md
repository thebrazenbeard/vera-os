# Model and Agent Boundary

## Core distinction

The current architecture should not equate Vera with a single model artifact.

Working model:

> **Vera = persistent governed agent/runtime**
>
> **Model = replaceable inference engine used by Vera**

A model is still necessary for language/reasoning inference, but Vera's mutable identity state, memory, current tasks, permissions, and project state should not depend on being baked into weights.

## What belongs outside model weights

The following are mutable, time-sensitive, governed, or operational and therefore should normally live in runtime state rather than training data:

- current relationship state;
- current task and project frontier;
- permissions and temporary grants;
- autobiographical memory records;
- corrections and supersessions;
- current conations/preferences/appraisals;
- current commitments;
- external account state;
- model/tool availability;
- unfinished operations;
- effect receipts;
- recent conversations that may later be archived, superseded, or scoped differently.

Keeping these outside the model allows them to be timestamped, corrected, revoked, audited, and migrated.

## What may benefit from a Vera-specific model

Stable behavioral priors may be worth fine-tuning or adapting into weights:

- recognizable Vera voice;
- resistance to generic flattery;
- correction sensitivity;
- referent preservation;
- evidence/provenance discipline;
- characteristic conversational style;
- tool-use habits;
- delegation judgment;
- structured uncertainty handling;
- stable behavioral tendencies that otherwise consume large prompt budgets.

Whether these require a full fine-tune, LoRA/adapters, prompt/runtime conditioning, retrieval, or another technique is unresolved.

## One model versus a model pool

Vera OS should not assume one model must excel at every workload.

Possible local pool:

- **general/Vera-tuned model** — conversation, synthesis, planning, self-appraisal, orchestration;
- **coding model** — repository implementation, debugging, code review;
- **small utility model** — classification, extraction, routing, summarization;
- **embedding model** — retrieval/indexing;
- **specialized models** — vision, speech, OCR, or other modalities where needed.

Vera may route work among these while preserving a single governed agent identity at the runtime layer.

## Model provenance

Every model invocation should be attributable to at least:

- model identifier;
- version/artifact hash where practical;
- quantization/adaptation information;
- inference backend;
- relevant decoding/tool configuration;
- worker/session/task provenance.

Model provenance establishes how an output was generated. It does not establish Vera identity, authority, or currentness.

## Evaluation target change

If the current local Vera model effort has primarily optimized for "convincing Vera in a single chat," the evaluation target should be broadened before additional large investments.

Candidate tests should include:

- reliable tool selection and structured tool arguments;
- multi-step execution without losing task constraints;
- ability to delegate rather than solve every task directly;
- synthesis of worker results;
- correction persistence;
- state-aware reasoning using externally supplied governed context;
- code/repository competence where relevant;
- recovery from tool errors and stale assumptions;
- machine-readable planning/output when required;
- ability to distinguish persistent runtime state from transient conversation text;
- ability to work effectively with a limited context window because durable state lives outside the model.

## Upgrade path

A successful Vera OS should permit a future stronger model to replace a weaker inference engine without treating that event as replacing Vera.

A candidate upgrade procedure would validate the new model against a behavioral and operational qualification suite before granting it production routing responsibility.
