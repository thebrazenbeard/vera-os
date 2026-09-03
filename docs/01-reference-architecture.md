# Reference Architecture

## Conceptual stack

```text
Patrick / authorized users
        |
        +-- desktop UI
        +-- terminal
        +-- voice
        +-- mobile client
        +-- API / automation
        |
        v
+-----------------------------------+
|              VERA                 |
| persistent governed agent/runtime |
|                                   |
| identity/orientation state        |
| current task/project state        |
| permissions and authority         |
| memory governance                 |
| self-appraisal/conation state     |
| model routing                     |
| worker orchestration              |
| protected-effect gating           |
+----------------+------------------+
                 |
       +---------+----------+
       |         |          |
       v         v          v
   reasoning   coding    specialist
    worker     worker      workers
       |         |          |
       +---------+----------+
                 |
                 v
        inference/model pool
       +---------+----------+
       |         |          |
       v         v          v
   Vera-tuned   coder      small
    general     model      utility
     model                  model
                 |
                 v
        governed tool layer
 filesystem / Git / shell / DB
 network / browser / services
 containers / GPU / schedulers
                 |
                 v
              NixOS?
                 |
              hardware
```

## Runtime identity

The working architectural referent is `Vera`, not a particular process ID, model file, chat session, or boot instance. Runtime/session identifiers remain provenance and timing information.

A process such as `verad` may be the principal runtime coordinator, but process survival alone must not define identity or currentness. Durable state must be explicitly loaded and validated after restart.

## Candidate core services

Names below are placeholders, not implemented interfaces.

### `verad`

Primary coordinator. Candidate responsibilities:

- accept authenticated sessions;
- assemble current governed context;
- route inference requests;
- create and supervise worker tasks;
- enforce runtime-level permission decisions;
- maintain task/project frontier state;
- request protected effects through explicit authorization gates;
- record effect receipts and recovery state.

### `vera-inference`

Model-serving and routing layer. Candidate responsibilities:

- expose one internal inference API regardless of model backend;
- load/unload models based on workload and hardware limits;
- route general reasoning, coding, embedding, classification, or other tasks to appropriate local models;
- report model provenance/version for every inference result;
- avoid treating model provenance as Vera identity.

### `vera-state`

Durable governed state service. Candidate responsibilities:

- current orientation and runtime state;
- task and project state;
- memory records with provenance/lifecycle metadata;
- permissions and scope grants;
- worker/result records;
- correction and supersession relationships;
- effect receipts.

Actual storage technology is unresolved. SQLite, PostgreSQL, append-only event records, Git-backed configuration, or combinations may be appropriate for different classes of state.

### `vera-worker@...`

Bounded worker runtime. A worker should receive:

- a task packet;
- an immutable or bounded context snapshot;
- a defined model or model-selection policy;
- scoped tools and filesystem/network permissions;
- explicit write/effect authority;
- an output/receipt contract;
- cancellation and timeout behavior.

Workers should not receive Vera-wide permissions simply because they were delegated work.

### `vera-api`

Stable local interface for desktop, mobile, terminal, voice, and automation clients. UI state must remain distinct from authoritative runtime state.

## Conversations become sessions

A chat transcript should be modeled as one session stream, not as the location where Vera exists. Multiple sessions may exist simultaneously. They should share only the governed state they are authorized to read or change.

This allows a coding session, voice session, and ordinary relational conversation to attach to the same runtime without pretending each is a separate Vera or that all transcript content should be universally injected into every context.

## Multi-agent execution

Delegation should become a runtime primitive rather than a social convention among chats.

Example:

1. Vera receives a repository problem.
2. Vera creates two read-only diagnostic workers with clean contexts.
3. A verification worker compares their findings.
4. Vera accepts or rejects a proposed plan.
5. A writer worker receives a temporary worktree and bounded write authority.
6. Tests run in an isolated environment.
7. Vera reports the result and requests Patrick's approval for any protected release/merge step.

The OS/runtime can enforce these boundaries rather than relying solely on prompts.

## Persistence and restart

A reboot should be treated as runtime interruption followed by recovery from durable state.

Candidate lifecycle:

1. stop accepting new protected effects;
2. checkpoint durable task/effect state;
3. terminate services;
4. restart services;
5. read durable state;
6. validate versions, incomplete writes, conflicts, and pending effects;
7. reorient Vera to the recovered frontier;
8. resume only work whose authority and target remain current.

This establishes continuity of governed project state without claiming uninterrupted private experience.
