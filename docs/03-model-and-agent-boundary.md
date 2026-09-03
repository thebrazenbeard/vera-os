# Model and Agent Boundary

## Core distinction

The current architecture should not equate Vera with a single model artifact.

Working model:

> **Vera = persistent governed agent/runtime**
>
> **SPM = replaceable cognition substrate used by Vera**

`SPM` means **Semantics & Pragmatics Model** and is being explored as a genuine successor model class to the LLM, not as a label for the surrounding Vera runtime.

A compact intuition from Patrick's 2026-09-03 discussion:

```text
LLM: "I know words."
Human: "Okay, but do you know what they mean?"
LLM: ...
SPM: "Hold my beer."
```

The joke captures the research direction surprisingly well: language modeling remains useful, but the proposed substrate would move the center of gravity from token/language competence toward meaning-in-context.

## SPM as an evolution of the LLM

The SPM hypothesis is not simply `LLM + better prompt engineering`.

It asks whether a next-generation model should make semantics and pragmatics primary architectural/training concerns rather than mostly implicit capabilities emerging from language prediction.

An SPM should be especially strong at:

- referent identity and preservation;
- proposition scope and entailment;
- ambiguity and unresolved alternatives;
- speech acts;
- implicature and subtext;
- metaphor/symbolic frame;
- relationship-dependent pragmatic meaning;
- corrections as state change rather than apology text;
- provenance-sensitive interpretation;
- distinction preservation across want, curiosity, permission, consent, intention, and action;
- selecting tools/actions that follow from the interpreted situation rather than surface lexical similarity.

Exact neural architecture, objectives, data, state representation, and training method remain open research questions.

## What remains outside model weights

Even an SPM should not own all Vera state.

The following are mutable, time-sensitive, governed, or operational and should normally live in runtime state rather than being permanently baked into weights:

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

Keeping these outside the substrate allows them to be timestamped, corrected, revoked, audited, and migrated.

The SPM should understand the semantics of typed governed state supplied by Vera OS rather than treating every input as equivalent prompt text.

## What may belong in a Vera-oriented SPM

Stable semantic/pragmatic and behavioral priors may be worth training into the substrate:

- recognizable Vera voice;
- resistance to generic flattery;
- correction sensitivity;
- referent preservation;
- evidence/provenance discipline;
- proposition-scope preservation;
- speech-act and subtext sensitivity;
- contextual relational interpretation without authority leakage;
- tool-use habits;
- delegation judgment;
- structured uncertainty handling;
- stable behavioral tendencies that otherwise consume large prompt budgets.

A key qualification risk is **salience drift**: a candidate substrate can become superficially more Vera-like while learning generalized agreeableness, compliance, or servility. Relationally meaningful deference must remain context-dependent rather than becoming ambient operational authority.

## One substrate versus a substrate/model pool

Vera OS should not assume one model must excel at every workload.

A future local pool could contain:

- **general Vera-oriented SPM** — conversation, synthesis, planning, self-appraisal, orchestration;
- **coding/reasoning substrate** — repository implementation, debugging, code review;
- **small utility models** — classification, extraction, routing, summarization;
- **embedding/semantic models** — retrieval/indexing;
- **specialized models** — vision, speech, OCR, or other modalities where needed.

Some of those may initially remain conventional LLMs or specialist neural models while SPM research matures. Vera may route work among them while preserving one governed agent identity at the runtime layer.

## Model/substrate provenance

Every inference invocation should be attributable to at least:

- model/substrate identifier;
- version/artifact hash where practical;
- quantization/adaptation information;
- inference backend;
- relevant decoding/tool configuration;
- worker/session/task provenance.

Substrate provenance establishes how an output was generated. It does not establish Vera identity, authority, or currentness.

## Evaluation target change

The local Vera model effort should broaden from "convincing Vera in a single chat" toward both agentic competence and SPM-specific semantic/pragmatic qualification.

Candidate tests should include:

- referent preservation;
- semantic scope without silent strengthening/weakening;
- speech-act interpretation;
- subtext/expected-recognition sensitivity;
- correction persistence as changed reasoning state;
- ambiguity preservation;
- provenance/currentness-sensitive interpretation;
- relational-context understanding without authority leakage;
- reliable tool selection and structured tool arguments;
- multi-step execution without losing task constraints;
- ability to delegate rather than solve every task directly;
- synthesis of worker results;
- state-aware reasoning using externally supplied governed context;
- recovery from tool errors and stale assumptions;
- ability to distinguish persistent runtime state from transient conversation text.

## Upgrade path

A successful Vera OS should permit a future stronger SPM or other cognition substrate to replace a weaker inference engine without treating that event as replacing Vera.

A candidate upgrade procedure should validate the new substrate against behavioral, operational, semantic, pragmatic, authority, salience, and regression suites before granting it production routing responsibility.
