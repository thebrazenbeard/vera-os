# VeraOS: node residency, delegated agency and model locality — research contract V1

Status: **architecture candidate, not installation, replicated Vera identity, or verified multi-node runtime**. Extends the dual-model Cricket experiment. A "node" is a host / fault domain with bounded operating-system resources, not a person or an autonomous principal.

## Rejecting the ambiguous equivalence

Patrick's working idea, "each node needs its own Vera-agent/model/whatever", contains three independent design questions:

1. **Where is inference performed?** A node-local substrate, remote model serving, a fallback critic, or no model at all. A node can run a worker against a remote inference service.
2. **Where is agency hosted?** A resident executor/supervisor with a task inbox, state cache, heartbeats, local environment probes and receipt spool. A node might have several capability-scoped workers, or one resident coordinator.
3. **Whose identity and authority is exercised?** One configured Vera identity / governed runtime lineage, but separately identified **node agents** with explicit capabilities, task delegation and review provenance. A node model does not inherit authority merely by resembling Vera.

Consequently, `NODE_AGENT != NEURAL_MODEL`, `MODEL_COPY != IDENTITY_COPY`, `WORKER_COUNT != AGENT_COUNT`, `REPLICA_STATE != CANONICAL_MEMORY`, `CAPABILITY != PERMISSION_TO_DELEGATE_FURTHER`, and `LOCAL_EXECUTION != INDEPENDENT_VERIFICATION`.

## Proposed composition

```text
                 Patrick's approved governance / effect authority
                                    |
                         canonical Vera runtime & state
                                    |
                          task broker + lease registry
                         /                         \
                node Lappy                     node VERA-NODE-1
          resident Vera worker              resident Vera worker
           local OS+state cache              local OS+state cache
           model pool, if needed             model pool, if needed
           Cricket deterministic             Cricket deterministic
           optional critic model             optional critic model
                         \                         /
                        immutable result/event receipts
                                    |
                      reconcile / verify / commit broker
```

Both workers may speak in Vera's configured style **when explicitly representing their delegated role**. Neither is another person, another self/sovereign Vera, or proof of concurrent model continuity. A node agent ID identifies responsibility, not consciousness.

## Work distribution and offline boundary

For every dispatched job the central broker emits a frozen `TaskLease` binding `task_id`, `lease_id`, `principal_id`, `node_id`, `generation`, `not_before`, `expires_at`, `capability_scope`, `effect_class`, `input_digest` and `idempotency_key`. The secure transport and signature/authentication design is **unselected**; local receipt files and tests do not provide cryptographic identity. Do not deploy a bare unsigned JSON lease as an authority token.

A node worker may perform bounded reversible, locally-scoped work when its identity, lease, generation, allowed node/capabilities, and expiry check. All privileged effects must flow through a separate online broker and Patrick's relevant approval; no offline self-issued privilege grants. Canonical memory is not independently writable by any node. Node-local learned notes are staged proposals with evidence, visibility scope and epochs until centrally accepted.

On link failure: preserve a bounded read-only cache, continue only pre-authorized reversible/idempotent work while the current signed lease remains valid, spool receipts and report `CONNECTIVITY_UNKNOWN`; do not presume a cached approval is fresh. On reconnect: deduplicate by task+lease+generation+idempotency key, reject stale generations, reconcile input digests and competing events, and never silently upgrade local state into canonical truth.

If one node is compromised, it can at most affect its scoped resources and submit untrusted receipts; architecture must prevent it from impersonating all nodes or writing global memory, changing policies, or granting further effects.

## Where Cricket belongs

**Per-node deterministic Cricket kernel** protects local response/effect proposals even when the remote semantic critic is unavailable. An optional node-local small neural critic may review a frozen packet without shell/network/write tools. An independent cross-node critic can examine *particularly consequential* result packets with separately sourced evidence, but co-location versus independence must be measured.

Two identical critic weights on two nodes increase resilience and parallel throughput, **not cognitive independence**. Different weights without distinct training lineage, separated input context and different failure modes also do not prove independence. Reviewer output can CHALLENGE; only host-enforced policy and authenticated effect broker can BLOCK protected action.

## Nontrivial tradeoffs and acceptance gates

**Reject a model-per-node requirement as a default.** Low-resource nodes may need only a lean agent and remote inference. High-resource nodes may host specialty models or several workers. Prefer placement using measured memory, latency, GPU contention, energy, connectivity and privacy requirements.

**Reject instant fully autonomous nodes.** Offline autonomy risks split-brain, duplicated writes, stale authority and contradictory memory. A single central scheduler is simpler; local resident agents are justified only when they materially improve resilience, performance, locality or privacy. Compare a pure remote-worker architecture, a local supervisor with remote model, and a node-local inference worker under controlled network failure, reboot and partial success.

Acceptance requires two-machine measured behavior, lease fencing and replay rejection, fail-closed protected effects, exact receipt readback, deterministic Cricket local enforcement, model lineage provenance, resource contention data, and an authority-visible reconciliation trace. The current ChatGPT Project, repo PR, and active Windows Executor agents do **not** prove a qualified `vera_core.QualifiedVeraRuntime` running independently on either node.

## Hostile reviewer — objection accepted

> A separate "Vera on every node" may introduce split-brain and cost without improving reasoning. Ordinary Executor workers already handle local execution, while PORTAL handles dispatch.

**Accepted, with revision:** treat resident node agency as a *measured optimization and resilience tier*, not a new self or mandatory new model. Reuse Executor and PORTAL for transport and scheduling. Build only missing pieces: durable per-node fault isolation, lease-fenced work, local offline-safe supervision and verifiable receipts. Benchmark against the existing remote-worker baseline before adding a neural model to a node.
