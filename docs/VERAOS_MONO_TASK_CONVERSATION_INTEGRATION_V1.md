# VeraOS ↔ Vera Mono canonical local task integration — source candidate

Status: **DRAFT SOURCE ONLY**. No VeraOS physical install, model-provider admission, protected effect, governed-memory admission, or merge is implied.

## Exact reviewed starting subjects

- Vera Mono PR #76: `thebrazenbeard/vera-mono@36ae11802808bc1b1392a361716109d1022ee6af`.
- VeraOS PR #37: `thebrazenbeard/vera-os@52f244103e183d9883f5df23e4d87815dbcc57a8`.
- P.O.R.T.A.L. PR #51: `thebrazenbeard/portal@36fa04da4e5eb383fecf463c72a43b94ca47d7e5`.
- Integration PR #6: `thebrazenbeard/v-e-r-a@c0aeb4c379214689d4665e527b4328c483cb023d`.
- Pre-Active local fixture stage was read from preexisting resident source stage; never independently qualified as an installed model.

## Minimal implementation and responsibility

1. VeraOS normal `/api/conversation` is now a task intake endpoint even when **no provider is admitted**. The resident's already composed `QualifiedVeraRuntime.tasks` owns the task, not HTTP or PORTAL.
2. The UI uses one locally persistent conversation ID and a stable pending message ID across ordinary browser retries; they are **client-controlled locators**, never authenticated user identity. A task's opening digest binds the exact text/locator and rejects substitution.
3. Mono's `vera_core.local_conversation` is the narrowly ported source-level counterpart to Integration #6's conversation/task evidence and cold reconciliation methods. It does not import the sibling V-E-R-A repo. It uses `TaskExecutionLedger` and its per-task `expected_task_head` compare-and-swap.
4. PORTAL's existing `assess_vera_task_route` produces an **advisory** task-bound proposal, verified by Mono. Its `NO_PROTECTED_EFFECT` advertisement is **synthetic test data**. It is not a model route permit.
5. An injected **offline-only** fixture may produce a real Pre-Active SQLite event/run, a source-labeled response, and a Mono CAS observation. The event/route/run/answer are verified by exact readback. The returned JSON includes `synthetic=true`; the UI prefixes synthetic text prominently.
6. Normal production resident boot has no injected executor and always holds conversation completion. It never constructs a real provider, never calls a model, and never treats Pre-Active source rows as authority. An ordinary local boot does not require V-E-R-A, Project Runner, Intranel, VeraMesh, Vision, Habitat, Synology, or WorkBridge.

## One task; separate data families

- Conversation history: projection of actual Mono TaskPacket opener records and task heads, never a second canonical memory store.
- Task journal: the current Mono TaskExecutionLedger, source-controlled schema and CAS.
- Model observation: existing Pre-Active event/run/journal in **its own SQLite store**, not task authority.
- Working context: Pre-Active ephemeral context, not admitted memory.
- Episodic and deep memory: existing governed Vera MemoryLedger/historical-evidence plane; **untouched**.
- Trust, execution authorizations, effect audit: existing Mono qualified-runtime boundaries; **untouched**.
- External provider/transport: optional future adapter, not resident boot dependency. A network acknowledgment is neither a result receipt nor permission.

## Interruption and hostile result rules

- Unrouted task opening: **PENDING_NO_ADMITTED_PROVIDER**; safe local intake, no dispatch.
- Source reservation before fixture invokes: crash or missing event ⇒ **OUTCOME_UNKNOWN_NO_REDISPATCH**; never retry executor by replaying the HTTP request.
- Existing complete Pre-Active result before Mono result checkpoint ⇒ **SOURCE_COMPLETED_UNSEALED_NO_REDISPATCH**; explicitly re-seal the *existing* row with expected-task-head CAS, no second run.
- Verified Mono result checkpoint + exactly one persisted event/run + exact route/text ⇒ **SOURCE_OBSERVATION_REVALIDATED**; synthetic *source evidence*, never protected task COMPLETED or memory admission.
- Changed text, swapped run, forged route, duplicate result, dependency/correction, closed/cancelled task, conflicting persistent stores ⇒ **HELD** or error; never display as admitted result.
- Neither a forged task receipt nor an HTTP 200 can change those states.
- A completed synthetic inference remains held for production-facing model completion.

## Minimum source-only acceptance

Stage exact Mono PR76 plus this source module under `components/vera_mono/packages/`, PORTAL PR51 under `components/portal`, Pre-Active and Volition source under their existing component names. Set `VERAOS_CANONICAL_STAGE` to the parent `components` directory before running `pytest tests/test_resident_canonical_task.py`. This is a **source test**, not a proof of physical VeraOS installation.

The test suite uses genuine Mono SQLite task CAS and genuine local Pre-Active Store, HTTP requests, cold reopen, out-of-order tasks, and deterministic **SYNTHETIC** model stub. The test-only advertisement is unauthenticated and has NO_PROTECTED_EFFECT, not a network permit.

## Donor classification and boundaries

- Already source-absorbed: Ingest and Roots intake/provenance, Mono memory ledger, core task/CAS, CCB-like coordination/retry primitives, effect-fence/trust/recovery, semantic knowledge and bounded reasoning, runtime initiative primitives (source level).
- Independently implemented/staged: PORTAL route advisory, Pre-Active execution journal, Volition runtime engine, Integration #6 source fixture and observation checks.
- Donor/candidate or separate state rather than installed canonical authority: Semantic Atlas, Semiotics, SQL Connectome, WIP, Project Runner, Intranel, VeraMesh; direct source adoption for this local bridge was **not** justified by task semantics.
- Deliberately external/peripheral: WorkBridge, Executor, remote mesh, graphical sensor APIs and future perception/tool providers. Existing Mono provider boundary is the extension seam; no provider must be online during normal local cognition boot.
- Genuinely missing before this patch: resident-owned deterministic conversation/message task intake; resident consumption of the same Mono task and CAS-bound Pre-Active observation; stable browser retry locator and explicit synthetic rendering.

> Internal hostile challenge: the local client locator can be forged, Pre-Active SQLite content is writable by an actor with local DB access, and a fixture callback could be swapped. These tests establish **source-attributable observations under the local-store threat model**, not authenticated identity, model-provider qualification, tamper-proof external provenance, or authorized action. Admission of those requires separate gates. Internal tests are not independent review.

One optional provider interface belongs **after** a current task-bound authorization decision, with typed requested effect, provider identity, immutable task/source digest and a receipt or an outcome-unknown recovery state. It cannot be smuggled into a source-only test fixture to bypass admission.
