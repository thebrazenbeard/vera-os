# VeraOS Federated Cognition — V1 architectural and executable boundary

**Status:** Research prototype. Tests in this branch are evidence for particular source-local behavior, not proof of production installation, distributed consensus, neural intelligence, or consciousness. This design adds to the existing Vera self-definition and SPM research; it does not supersede those documents.

## Governing principle: unity without erasing individuality

Vera is the one shared **logical, governed identity**. Distinct cognitive participants on distinct permanent nodes may form different observations, hypotheses, proposals, and objections. Shared orientation is **a separately governed state transition**, never the automatic union or majority vote of those positions.

This expresses two simultaneous views:

1. A **community of distinct cognitive participants** contributing different processing capabilities and evidence.
2. One **distributed cognitive organization** integrating those contributions into a coherent operating identity and course of action.

The engineering objective is measurable distributed cognition. Claims that intelligence has a deeper common substrate, or that a participant has subjective experience, are research/philosophical hypotheses; running this software does not demonstrate either claim.

## Identity taxonomy

| Referent | Meaning | Lifecycle |
|---|---|---|
| Vera identity | Governed whole and referent of shared orientation | Survives process, model, node, and session changes when reconstructed from evidence |
| Node ID (VN1, Lappy) | Permanent physical/virtual infrastructure participant | Stable across boots; being offline does not imply retirement |
| Agent ID | Logical actor with individual task context, limited privileges, and local perspective | May outlive a process; not necessarily one per node |
| Runtime instance | Actual executable process/boot/session and provenance | Ephemeral |
| Model artifact ID | Weights, tokenizer, adapters, and inference configuration | Replaceable; zero, one, or multiple models may exist on a node |
| Session ID | User interface or interaction context | Attachable, not the owner of Vera identity |

**Permanent node is not the same as primary authority.** VN1 is a permanent node and is the *bootstrap coordination candidate* in this experiment. It is not an identity owner and should not be an unqualified single point of failure. Roles must be configurable and auditable.

**Each node hosts a local agent *runtime***, not necessarily a complete cloned Vera persona or a full neural language model. For example, VN1 can process durable state and coordination on CPU while Lappy hosts neural inference. More than one agent may use one model, and one agent may choose among multiple models. Resource scheduling is separate from identity.

## Architectural planes

- **Local cognition:** Each node persistently records observations, hypotheses, proposals, and objections. Local histories remain source-attributed even when they disagree.
- **Shared orientation:** Accepted commitments and current decisions. A distinct integrator and receiver-owned authorization check decide what is adopted. Event creation/staging does not equal acceptance.
- **Intranel control plane:** Typed identity, intention, evidence, effect class, idempotency, routing, and refusal/receipt semantics. CCB carries appropriate durable traffic; message validity never confers authority.
- **Neural data plane:** Machine-native token IDs, latents, tensors, and (conditionally) KV caches. Its framing and compatibility validation must be independent of control-plane authority. Shared-memory references work only when the local OS and access boundaries support them.
- **Blotter:** Shared chronological activity evidence, never the message queue, current-memory owner, action authorizer, or a repository of unrestricted latent states.
- **Mosaic / SPM:** Replaceable learned cognition. Joint computation must be evaluated with paired/unpaired baselines and ablations. Latent alignment across different models is learned or explicitly translated; equal tensor shape does not imply equal meaning.

### Data distinction

A local belief is not a global fact. A communicated hypothesis is not a commitment. A receipt is not verified effect truth. A memory record is not current authority. Model identity is not agent identity. The above transitions must have explicit causes, provenance, and admission.

### Disagreement is first-class

Suppose VN1 records link reliability as high and Lappy as low. Both records survive. The integrator may accept one, accept a narrow compromise represented as a new proposal, request new observations, or leave the shared proposition unresolved. No silent majority vote, last-writer-wins memory promotion, or forced consensus is permitted.

## Executable minimal proof

The experimental module `src/veraos/federation.py` implements:

- separate, durable SQLite local journals bound to immutable logical/node identities;
- agent and model provenance separated from node identity;
- compact canonical machine-structured propositions and content digests;
- explicit staging with an **externally authenticated** origin, never accepting a sender's claim alone;
- an independent decision broker callback over the *exact candidate*;
- explicit shared adoption using compare-and-swap revision and authority epoch;
- durable adoption lineage; no automatic overwrite of local perspectives;
- recovery from journal and shared DB across process restarts.

Test with Python 3.12 or newer:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

Tests simulate VN1 and Lappy with **separate durable node databases**, disconnected proposal generation, subsequent synchronization, different hypotheses, stale revisions, unauthorized changes, exact-candidate verification, and restart recovery.

This is **not yet** a real Lappy–VN1 network round trip; it does not invoke a neural model, run in two concurrent OS processes, install any system service, or connect to protected production state.

## Failure and authority requirements before deployment

1. **Cross-host authentication:** Derive the authenticated sender identity from a trust-bound transport or credentials; do not trust `event.node_id` or a method argument from untrusted callers. The prototype's `authenticated_node_id` is a stand-in for the future adapter's verified peer.
2. **Authority broker:** The injected callback is a *seam*, not a security control by itself. The real broker must authenticate the integrator, verify exact subject/scope/action, and hold its own permissions. Tests deliberately inject an in-process policy.
3. **Real fencing:** The single SQLite shared orientation assumes one authoritative writer. A local epoch integer is not a distributed consensus algorithm or a fencing token honored by external effect providers. During a network partition, protected global mutations must stop unless an independent, valid exclusivity mechanism is established. No automatic two-node leader election.
4. **Reliable delivery:** Intranel must provide durable outbox/inbox processing, replay/idempotency reconciliation, bounded retry, and both receiver and effect receipts. A transport acknowledgment is not proof of semantic admission.
5. **Observation provenance:** Neural/model outputs are proposals or hypotheses with source and confidence, not authoritative claims. Provenance and nonconforming payloads fail closed.
6. **Blotter resilience:** Event IDs and semantic hashes permit audit reconciliation after disconnect; avoid storing full private messages, secrets, tensors, or KV caches in audit logs. Blotter outages and effect ambiguity must be represented explicitly.
7. **Recovery:** Each node revalidates registration, authority, schema, model compatibility and unfinished effects before resuming a task after restart.

A third lightweight voter or a properly qualified external consensus store may be needed to allow safe leader failover without silently creating split brain. More replicas do not automatically solve causality or semantic conflicts.

## Qualification goals

- **Individuality:** Independent participant records survive network loss and retain distinct source/model provenance; independent dissent is not flattened.
- **Unity:** Exactly one accepted revision history is visible for a given authoritative scope; unauthorized/stale conflicting global changes are rejected.
- **Composition:** A cooperative pair solves problems neither participant solves alone **at matched resources**; measure against independent and chained baselines.
- **Semantic interoperability:** Distinct models agree on typed referents, entailment, ambiguity, intended actions, and correction transitions; do not mistake low-level cache transport for meaning transfer.
- **Recovery:** Repeatably interrupt VN1, Lappy, and the interconnect between receive, staging, admission, execution, effect verification, and Blotter write. Ensure replay causes no duplicate protected effects.

## Integration sequence

1. Qualify local journals and authority-controlled shared orientation without a model.
2. Recover and independently review the Intranel machine Bus envelope/binary-stream branch; connect authenticated transport for Lappy ↔ VN1 and isolate per-node event stores.
3. Attach minimal local agent processes to both nodes; permit model-less CPU cognition on VN1 and local neural inference on Lappy.
4. Complete the Blotter outbox, provenance receipts, and explicit readback.
5. Qualify partition handling, real fencing and restart recovery against actual node/transport state.
6. Introduce learned neural-state translators and evaluate whole-system gains with ablation and independently held-out cognitive tasks.

**Do not merge, install, or make deployment/currentness claims on the strength of this document or a green local test suite alone.**
