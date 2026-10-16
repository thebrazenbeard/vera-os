# VeraOS: Independent Cricket Micro Critic — candidate architecture V1

Status: **RESEARCH CANDIDATE; NOT AN INSTALLED OR SELECTED MODEL ROUTE**. Recorded after the 2026-10-16 two-model proposal. Do not treat this as a settled VeraOS governance decision.

## Proposition
VeraOS hosts one persistent, governed Vera identity/runtime. Vera Core is a replaceable primary cognition substrate with its specialized adapters. Cricket Micro is a **separately loaded compact semantic critic**, with distinct model artifact/provenance, runtime process and minimal context. Cricket Micro is neither a second Vera nor an independent effect authority or evidence verifier.

The existing `thebrazenbeard/cricket` deterministic kernel is the policy boundary; the optional small model **augments** open-ended semantic error detection. VeraOS consumes a locally owned adapter/contract. The donor repository is a research reference, **not a mandatory VeraOS runtime checkout**; approved integration must be absorbed/pinned into VeraOS or Vera Mono's local code boundary.

## Candidate contract
1. Vera Core emits a candidate response/action envelope, typed effect class, frozen current user proposition, bound evidence IDs/digests and authority status; there is no direct effect yet.
2. The host constructs a minimally scoped immutable review packet: `request_id`, `candidate_digest`, `user_proposition`, `candidate`, `evidence_refs`, `effect_class`, `authorization_state`, `phase`, `model_provenance`, `deadline_ms`. Raw secrets, privileged credentials and unneeded private memory do not enter the packet.
3. The deterministic Cricket kernel checks effect permissions, unsupported verification, superseded corrections and semantic integrity where available.
4. An isolated Cricket Micro service **may** inspect that same frozen packet with read-only, no-shell/no-network privilege (except its host-controlled IPC). It returns typed `PASS | CHALLENGE` findings with exact quoted anchor, rationales, evidence pointers and abstention. It **never** issues effect permits or `BLOCK` for its own semantic opinion.
5. An authorized host rule may separately yield `BLOCK`. A model's requested BLOCK is downgraded to advisory CHALLENGE; absence, timeout, malformed output or disagreement **is not PASS**.
6. On CHALLENGE, Vera Core gets at most one bounded reconsideration; a protected effect remains held until the host's existing effect broker authorizes it. Log revised candidate digest and final disposition, preserving any unresolved objections.
7. A receipt binds immutable packet digest, reviewer model artifact hash/quantization/backend/config, finding IDs, latency and final outcome; a receipt is **not** third-party attestation.
8. Cricket Micro must be replaceable or offline without losing the deterministic host-enforced rules. For low-risk chat, host policy can allow safe degradation with an explicit `REVIEWER_UNAVAILABLE` marker. For protected effects, the existing broker remains fail-closed regardless of either model.

## Isolation and model roles
Vera Core: full task execution only behind VeraOS policy, specialty adapters, governed memory and task routing. Cricket Micro: independently versioned small model artifact, distinct inference worker/OS account where practical, no direct mutable state, no privileged tools, no shared writable adapter with Vera Core, resource quotas and finite deadlines. Distinct model aliases or two adapters on one base checkpoint do **not** establish independent judgment. Artifact diversity should be measured using weight hashes, lineage, data and failure correlations.

Use CPU-first as a hypothesis rather than a guarantee. A 1–3B parameter class is merely an initial experimental range; evaluate latency, RAM, VRAM contention, token budgets and material objection quality on the actual target hardware before adopting it.

## Hostile design review
**Strongest objection — ACCEPTED:** a second neural model is unnecessary if the existing deterministic Cricket kernel, Rezon semantics or a shared-model self-critic achieve the same detection quality. Small models may amplify false accusations, agree reflexively, or be manipulated by candidate text. Extra process separation by itself proves neither independent evidence nor moral authority.

**Revision:** run held-out three-arm comparisons: (A) existing Cricket deterministic rules only, (B) Cricket plus the primary model as a critic, (C) Cricket plus a distinct model artifact. Freeze identical packets and host rules. No architectural promotion until C demonstrates material incremental gain over B at acceptable false-positive rate, latency and memory on target hardware. Test critical protected-effect rules separately; no neural model may override them.

## Evaluation and acceptance
The adjacent `experiments/cricket_dual_model` contains synthetic, non-private cases and a reproducible harness for (A), with optional offline/local Ollama semantic critic invocation for (B/C). Report challenge precision, recall, false-challenge rate, BLOCK agreement on host-grounded cases, timeout/malformed/abstention counts, latency, artifact lineage and energy/memory if measured; do not score unknown as PASS. Hold out adversarial errors including modal strengthening, referent drift, unauthorized tool use, assertion of unverified completion, malicious quoted instructions, and clean benign cases.

Do not declare C superior based solely on the synthetic fixture, the reviewer calling itself independent, or a single shared base checkpoint. A deployable path requires a frozen evaluation split, realistic cases from authorized nonprivate data, blind annotation, adversarial false-positive review, resource measurement, and a live qualified VeraOS IPC hook.

## Evidence boundary at this checkpoint
Cricket reference `thebrazenbeard/cricket` at `0bae95bc45db55d78001ee9c492681834191ec0b`. VeraOS source base `d2197238d350e4311a49098a1b00ca171a568340`. Vera Mono native composition is governed by `vera_core.QualifiedVeraRuntime`; this document does not install or route it. VeraOS image/inference PRs #15–#32 are active independent work; no overlap or image cutover authorized by this candidate.
