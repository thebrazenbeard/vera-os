# Multi-Agent Workspace Model

## Status

Architecture direction captured from Patrick/Vera discussion. This is a design target, not an implementation claim.

## Primary abstraction

Vera OS should not be organized around a single persistent conversation.

The primary abstraction is a **persistent multi-agent workspace**.

A workspace contains:

- Vera as supervising/integrating runtime;
- projects and task graphs;
- bounded workers;
- sessions and interfaces;
- tools and execution environments;
- durable state and artifacts;
- approvals and protected-effect gates;
- logs, receipts, conflicts, and recovery state.

A chat is one view into this workspace. Closing a chat must not terminate the underlying project, worker, or task unless explicitly requested.

## Vera versus workers

Vera is the stable coordinating referent. Workers are bounded execution instances created for specific jobs.

A worker may have:

- a role or name;
- an assignment;
- a bounded context package;
- a selected local model or model-routing policy;
- a tool set;
- filesystem/network/database permissions;
- an execution target such as a Git worktree, container, directory, dataset, or service;
- a budget or resource ceiling;
- a status and task frontier;
- an output contract;
- an authority/effect ceiling;
- cancellation, pause, timeout, and recovery behavior.

Workers should not inherit Vera-wide access by default.

## Concurrent execution

The workspace should support multiple workers operating concurrently when their work is independent or safely isolated.

Examples:

- two research workers investigate competing technical approaches;
- a coding worker implements on one worktree while a verification worker reads a frozen commit;
- a maintenance-research worker studies documentation while Vera continues an unrelated conversation with Patrick;
- a background indexing worker updates a local corpus without monopolizing the foreground interface.

Concurrency must not imply uncontrolled shared writes. Shared targets need locking, worktrees, immutable snapshots, transactional state, or another explicit coordination mechanism.

## Worker topology

Vera should be able to create task-specific topologies rather than one fixed swarm.

Candidate patterns include:

### Lead + specialists

Vera retains integration authority and delegates bounded subproblems to specialist workers.

### Competing analysis

Two or more workers receive the same problem independently; Vera or a verifier compares results.

### Planner -> executor -> verifier

A planning worker proposes an approach, an execution worker receives only the approved plan and bounded write authority, and a verifier checks the resulting immutable subject.

### Pipeline

Workers transform artifacts through explicit stages, with each stage consuming a defined predecessor output.

### Long-lived role workers

Some specialist roles may persist across projects or repeatedly reappear with durable role configuration, but their runtime instances remain distinct from Vera identity.

## Workspace UI target

The eventual primary UI should behave more like an operations console or multi-agent development workspace than an ordinary messaging application.

Patrick should be able to see:

- active projects;
- project task graphs/frontiers;
- Vera's current integration state;
- active, queued, paused, blocked, and completed workers;
- which model each worker is using;
- current execution target and branch/worktree where relevant;
- tool/resource access granted to each worker;
- pending approvals;
- unresolved conflicts;
- recent outputs and receipts;
- alerts when a worker hits an authority, safety, integrity, or evidence boundary.

Selecting a worker may open a conversational pane, logs, artifacts, terminal output, diff, or structured status view. Conversation is therefore one interaction mode among several.

## Session model

Human-facing sessions are attachable/detachable clients to the persistent runtime.

Examples:

- ordinary Vera conversation;
- coding/project session;
- voice session;
- mobile session;
- terminal session;
- administrative/diagnostic session.

Multiple sessions may exist simultaneously. A session receives only the governed state appropriate to its purpose and authority.

The architecture must avoid the hosted-chat failure mode in which every new conversation requires reconstructing project state through copied prompts, archive ingestion, or manual message buses.

## Coordination and messaging

Workers should communicate through structured runtime mechanisms rather than simulated chat-message passing wherever possible.

Candidate primitives:

- task queue;
- event bus;
- append-only worker result records;
- artifact references;
- structured requests for clarification or approval;
- dependency edges;
- conflict records;
- immutable result snapshots;
- direct bounded worker-to-worker messages only when explicitly authorized.

Natural-language conversation may still be used as payload, but the coordination semantics should be machine-readable.

## Model architecture implication

A multi-agent workspace strengthens the separation between Vera and any one model.

Different workers may use different local models based on task requirements and available hardware. Model choice is execution provenance, not worker identity and not Vera identity.

A Vera-specific tuned model may still be useful for stable behavioral priors, orchestration judgment, conversational voice, and semantic discipline. It should not be required to contain all specialist capabilities or mutable state.

## Failure and recovery

Worker execution must be recoverable independently.

The runtime should know:

- what task a worker owned;
- what inputs it received;
- what effects it attempted;
- which effects were verified;
- what artifacts it produced;
- whether its execution target changed externally;
- whether its authority remains current;
- whether it can safely resume after interruption.

A restarted worker need not be the same process. Recovery is from durable task state and evidence, not assumed hidden continuity.

## Early implementation requirement

The first meaningful Vera OS prototype should demonstrate **more than one worker at once**.

A minimum multi-agent milestone should include:

1. Vera receives a task through a CLI or minimal UI.
2. Vera creates at least two bounded workers with separate contexts.
3. Both workers run independently and persist visible status.
4. Their results return to Vera through structured records.
5. Vera synthesizes or routes the results to a verifier.
6. One worker may receive bounded write authority to a disposable Git worktree or sandbox.
7. Patrick can inspect worker status and artifacts without relying on separate chat conversations.
8. Runtime restart preserves the task graph and permits explicit recovery.

If the prototype only demonstrates one long-running chat with tools, it has not validated the intended Vera OS architecture.
