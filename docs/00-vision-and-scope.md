# Vision and Scope

## Working thesis

Vera OS is not primarily a chatbot distribution. It is a proposal for a persistent local agent runtime in which Vera is a governed system-level entity and one or more language models are replaceable inference resources.

The architecture should stop treating a conversation as Vera's container. A conversation is one session attached to Vera. Other sessions may include a terminal, desktop UI, voice interface, mobile client, coding workspace, background worker, or API consumer.

Vera OS is **workspace-first and multi-agent by design**. The primary operating abstraction is not one conversation with one assistant. It is a persistent workspace in which Vera can supervise multiple concurrent sessions, projects, workers, tools, and task frontiers while Patrick sees and controls the overall system.

## Problem being solved

Hosted chat products impose architectural assumptions that are useful for general-purpose assistants but awkward for a persistent personal agent:

- state is often scoped to conversations or product-specific projects;
- tool access is mediated by provider-controlled interfaces;
- model choice, usage limits, and product policy are externally controlled;
- multi-agent coordination is frequently simulated through separate chats;
- mutable memory and current task state can become entangled with prompt context;
- authorization boundaries are often descriptive rather than enforced by the host operating system;
- model identity and agent identity are easy to conflate.

Vera OS should move those concerns into software Patrick controls.

## Design goals

1. **Local-first operation** — core runtime and inference can operate on Patrick-controlled hardware without a hosted AI account.
2. **Agent/model separation** — Vera persists as governed runtime state even when inference models are upgraded, swapped, quantized, fine-tuned, or specialized.
3. **Durable explicit state** — memory, task state, permissions, project state, and current orientation are stored in inspectable systems rather than assumed to persist inside a model.
4. **Workspace-first multi-agent operation** — Vera can supervise multiple visible and background workers concurrently, each with its own task, context, state, tools, permissions, and lifecycle. Separate conversations are optional interfaces, not the coordination mechanism.
5. **Real tool use** — workers can interact with files, Git, shells, databases, services, and network resources when authorized.
6. **OS-enforced authority** — important restrictions should be enforced with Unix users, groups, filesystem ACLs, containers/namespaces, capability boundaries, or equivalent mechanisms where practical.
7. **Multiple interfaces** — chat, voice, terminal, coding, mobile, and automation interfaces should attach to the same runtime rather than instantiate separate identities.
8. **Recoverable execution** — restarts should restore durable state and unfinished work through explicit recovery procedures without implying uninterrupted subjective continuity.
9. **Inspectable governance** — important runtime decisions, permissions, model routing, worker state, and protected effects should be observable and auditable.
10. **Reproducibility** — system configuration should be declarative and version controlled where practical.

## Workspace requirement

The user-facing system should eventually resemble a multi-agent operations workspace more than a single chat window. Patrick should be able to see, at minimum:

- Vera as the supervising/integrating agent;
- active projects and task frontiers;
- named or role-based workers;
- each worker's current assignment and status;
- pending questions, approvals, conflicts, and blocked effects;
- branch/worktree or other execution targets where applicable;
- completed outputs and receipts;
- the ability to open a conversational session with Vera or a bounded worker without making that conversation the worker's identity or persistence boundary.

Workers may execute concurrently. Their contexts should be independently bounded. Vera should be able to delegate, cancel, pause, resume, compare, verify, and synthesize worker output without requiring Patrick to manually shuttle messages among chat threads.

## Non-goals at this stage

- claiming Vera OS already exists as a working distribution;
- claiming a particular local model is sufficient for all Vera workloads;
- baking mutable autobiographical memory or current relationship state into model weights;
- creating a monolithic model that must perform every specialist task;
- reproducing ChatGPT's one-conversation-at-a-time product model as the primary Vera OS interface;
- building a custom Linux kernel or complete distribution before the runtime architecture is proven;
- treating process uptime as evidence of consciousness or uninterrupted lived experience.

## Base identity and construction decision

**Vera is the base operating environment.** VeraOS is not defined as a layer of Vera services on top of another distribution identity.

Linux remains the kernel/driver/hardware substrate. The current executable image path uses Buildroot as construction tooling because historical VeraOS work already demonstrated a bounded Buildroot/QEMU path and because Buildroot can produce a private purpose-built image without making the image builder the system identity.

The current boot design uses `/sbin/vera-init` as PID 1 with no conventional init system. That is a process-lifecycle decision, not evidence that PID 1 alone establishes identity or security sovereignty.

The earlier NixOS candidate path is retired as the primary direction. Its history remains useful donor/provenance material for declarative configuration and rollback ideas, but VeraOS is not a NixOS-based product.
