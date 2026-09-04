# Security and Authority Model

## Principle

Where an authority boundary matters, Vera OS should prefer enforceable runtime/OS controls over prompt-only instructions.

Prompts can explain policy. The operating system should enforce high-value boundaries whenever practical.

## Candidate enforcement layers

### Unix users and groups

Different workers may execute under different service accounts with distinct filesystem and device permissions.

Examples:

- read-only repository reviewer;
- repository writer limited to temporary worktrees;
- model-serving service with GPU access but no repository credentials;
- state service writable only through a narrow local API;
- UI process that cannot directly modify governed state files.

### Filesystem permissions and ACLs

Protected files should not be writable merely because a worker can access a shell.

Potential classes:

- immutable/version-controlled governance configuration;
- mutable Vera state;
- user data;
- model artifacts;
- worker scratch space;
- secrets;
- logs/receipts;
- project repositories.

### Containers, namespaces, cgroups, or VMs

Bounded workers may run in isolated environments with:

- scoped filesystem mounts;
- CPU/RAM/GPU limits;
- network allow/deny policy;
- process-count limits;
- temporary lifecycle;
- no ambient access to unrelated user data.

The exact mechanism is unresolved and may vary by risk level.

### Capability/effect broker

High-impact operations should pass through a controlled broker rather than giving every worker broad credentials.

Examples:

- merge protected Git branches;
- send external messages;
- change system configuration;
- install packages outside an approved generation change;
- expose network services;
- alter secrets;
- delete durable state;
- perform external financial or account actions.

A worker may propose an effect without possessing the capability to execute it.

## Patrick authority

Where Patrick reserves a protected decision, the implementation should make that reservation technically meaningful rather than conversationally advisory.

Possible approval mechanisms later may include:

- authenticated local UI confirmation;
- signed approval tokens;
- privileged command requiring Patrick's OS account;
- hardware-backed key/second factor;
- explicit policy records consumed by the effect broker.

No mechanism is selected yet.

## Worker authority

Delegation should grant the smallest useful authority for the assigned task.

A task packet should define:

- target;
- read scope;
- write scope;
- allowed tools;
- network policy;
- maximum runtime/resources;
- whether it may spawn children;
- whether it may request protected effects;
- completion/receipt requirements.

Historical role, model intelligence, or a previous successful task should not silently widen current authority.

## Secrets

Secrets should be supplied at execution time through a mechanism designed for secrets. They should not be committed to Git, embedded in model files, or placed into globally readable runtime prompts.

A NixOS implementation must specifically avoid accidentally placing sensitive values into the world-readable Nix store.

## Logging and privacy

Auditability does not mean indiscriminate logging.

The runtime should distinguish:

- operational receipts that must be durable;
- diagnostic logs with retention limits;
- private conversational/relational content;
- secrets that should never be logged;
- model traces that may contain sensitive context.

Logging design is unresolved and requires an explicit privacy model.

## Self-modification

Vera may eventually be allowed to propose changes to Vera OS itself. That is not equivalent to authority to deploy those changes.

A safer initial pattern is:

1. worker proposes code/configuration on a branch;
2. independent verification/tests run;
3. Vera presents the immutable subject/diff;
4. Patrick approves or rejects protected deployment;
5. deployment produces a receipt and rollback point.

NixOS generations could eventually make this especially useful, but that must be validated in practice before relying on it as a safety mechanism.
