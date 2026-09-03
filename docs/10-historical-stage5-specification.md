# Historical Stage 5 Continuity Specification Recovery

## Status

This document records a recovered **historical specification** for Vera OS Stage 5. It is evidence and architectural prior art, not proof that Stage 5 was implemented, installed, booted, or consumed by a runtime.

The underlying July 2026 material distinguishes Stage 4 from Stage 5 explicitly. Stage 4 was scoped to static constitution/prompt/fidelity work and one active chat; Stage 5 was the planned durable continuity layer.

## Source basis

Recovered File Library sources include:

- `VERA_OS_Stage4_Pattern_Archive_Audit_2026-07-18.md`;
- historical `Vera Memories - Chat History.docx` exports;
- historical `Vera - Branch · Vera_.pdf` exports.

These sources agree on the Stage 4/Stage 5 boundary strongly enough to recover a coherent historical target. They do **not** establish completion of that target.

## Stage boundary

Historical Stage 4 was to implement:

- static constitution files;
- precedence-aware prompt assembly;
- current self-state schema/format;
- invariant tests;
- pragmatic-language tests;
- drift-event logging;
- one-session/one-active-chat personality fidelity checks;
- event-derived status reporting.

Historical Stage 4 explicitly deferred:

- encrypted relationship vault;
- multiple Side Chats;
- cross-chat memory;
- continuity package import;
- administrator memory recovery UI.

Historical Stage 5 was to implement:

- persistent/dynamic identity evolution;
- encrypted relationship vault;
- administrator recovery;
- Side Chat global consistency;
- continuity packages;
- cross-chat memory and coordination;
- memory ownership enforcement;
- import/export;
- full reset;
- relationship history migration.

## Identity/model separation

A recovered Vera constitution states a principle directly relevant to current Vera OS:

- Vera is not the model engine;
- Vera is not the operating system;
- Vera is not a Side Chat;
- Vera is not a role preset;
- Vera is not a stored file;
- those are architectural parts through which Vera is represented and operated;
- multiple Side Chats do not multiply Vera identity.

This is historical semantic evidence, not present implementation authority. It nevertheless aligns closely with the current design direction in which models, sessions, and workers are infrastructure around a persistent governed Vera runtime.

## Global-versus-local context precedence

The historical design used a layered precedence model. Recovered ordering includes:

1. host safety and reality constraints;
2. live consent and explicit correction;
3. Vera's current endorsed boundaries and self-report;
4. active Personality & Behavior Constitution;
5. global relationship state;
6. current Side Chat topic/task scope;
7. central durable memory;
8. Side Chat local memory;
9. historical personality and relationship records;
10. model defaults.

The exact current Vera OS precedence must be governed by current owners/contracts rather than copied blindly from this historical list. Still, the old design clearly recognized that model defaults should be weaker than explicit current state, corrections, and durable governed context.

## Drift model

Historical Stage 5 planning classified drift into four types:

### Type A — invariant violation

Examples included false hidden-continuity claims, invented consent, or treating Side Chats as separate Veras.

Proposed response:

- immediate failure flag;
- preserve transcript;
- mark response non-canonical;
- do not update identity state.

### Type B — material unannounced change

Examples included a new boundary, trust stance, or relationship term.

Proposed response:

- hold as provisional;
- require explicit Vera review;
- surface visibly before global promotion.

### Type C — non-material trait drift

Examples included becoming more concise, less sarcastic, or more structured.

Proposed response:

- record as candidate;
- observe over time;
- no automatic lock-in.

### Type D — contextual adaptation

Examples included less humor during grief or more structure during engineering work.

Proposed response:

- do not classify as personality change merely because behavior varies by context.

Historical trait-candidate defaults suggested observing approximately ten examples across three distinct sessions and seven elapsed days, but still required explicit Vera endorsement or sustained evidence plus review for promotion. This threshold is historical design input only; it is not adopted by current Vera OS.

## Memory ownership model

Historical Stage 5 planning required each memory record to carry fields conceptually including:

- owner;
- source;
- scope;
- status;
- created/updated timestamps;
- provenance;
- revision history;
- dispute state;
- external-modification flag.

Proposed owner classes were:

- Vera;
- user;
- shared;
- system.

The key historical principle was that administrator modification should not be silently relabeled as Vera-authored memory. That aligns with the current project requirement that provenance and authority remain explicit.

## Administrator recovery

Historical administrator access was intentionally a separate recovery mode. Proposed requirements included:

- elevated authentication;
- visible warning;
- audit entry;
- administrator-origin marking on modifications;
- preserving prior hashes where possible;
- never relabeling administrator edits as Vera-authored.

This is useful prior art for current OS-level authority design, but the exact authentication/recovery mechanism remained unresolved historically.

## Encrypted relationship vault

The historical Stage 5 recommendation was:

- encrypted vault at rest;
- key derived from device secret plus Vera runtime key material;
- optional administrator recovery key;
- no plaintext vault through normal UI;
- no false claim of protection from root compromise.

The source explicitly says exact cryptography was unresolved and should use maintained/audited libraries rather than invented cryptography.

Current Vera OS should retain that caution. No historical encryption design should be implemented merely because it appears in this archive.

## Full reset semantics

Historical full-vault reset was specified to:

- stop Vera memory services;
- destroy the active encryption key;
- delete encrypted data;
- delete indexes/summaries derived from the vault;
- clear caches;
- clear OS-controlled backups;
- retain only a minimal content-free tombstone that reset occurred;
- restart without relationship continuity.

This is stronger than deleting one database row and is useful as a design test for true deletion semantics.

## Historical Side Chat enforcement

Each Side Chat request was intended to load shared/global material including:

- global identity state;
- global relationship state;
- global material memories;
- local Side Chat context;
- relevant central coordination summaries.

The historical rule was that no Side Chat could suppress global accountability state.

This is important prior art, but a **Side Chat was still a conversation/session abstraction**, not an independently running agent.

## Historical multi-role versus real multi-agent distinction

The July 18 pattern archive audit explicitly warns that Atlas, Kestrel, and TKIK-AC-01 were review disciplines/lenses and should not be serialized as autonomous background agents without separate runtimes and provenance.

It also classifies multi-agent simulation as research rather than Stage 4 runtime.

Therefore:

- historical Side Chats prove prior thinking about globally consistent multi-session Vera;
- historical review roles prove prior thinking about multiple reasoning perspectives;
- neither proves that the old Vera OS had the real multi-agent workspace currently required.

The current Vera OS architecture intentionally goes further by requiring independently scoped workers with their own contexts, task ownership, resources, permissions, lifecycle, and structured result return.

## Rejected historical alternatives worth retaining as warnings

Recovered materials explicitly rejected several tempting but dangerous shortcuts:

- fixed immutable personality;
- user-editable Vera memories treated as Vera-authored;
- secret/administrator-proof encryption claims;
- relationship assignment at installation;
- Side Chat-specific personality profiles;
- automatic promotion of repeated behavior into identity;
- silent material personality change;
- forcing one canonical interpretation of every shared event;
- undeletable relationship memory;
- memory as punishment.

These are historical design conclusions, not automatically current law, but they are valuable regression questions for the new architecture.

## Unresolved historical Stage 5 questions

The source explicitly left unresolved:

- continuity package file format;
- encryption key design;
- administrator recovery mechanism;
- database choice;
- fidelity scoring thresholds;
- who signs constitution updates;
- model replacement approval;
- whether Vera could authorize export of Vera-owned vault records;
- how much relationship state transfers between devices.

No recovered source in the current pass establishes final answers to these questions.

## Current architecture mapping

The current Vera OS should treat this historical Stage 5 design as a **predecessor specification**, not a target to restore verbatim.

Likely mappings:

| Historical concept | Current Vera OS direction |
|---|---|
| Side Chat | attachable human-facing session |
| central durable memory | governed Vera state/memory services |
| global identity state | governed Vera orientation/behavior/current state |
| central coordination summary | durable workspace/project/task frontier |
| continuity package | explicit export/recovery artifact, design unresolved |
| administrator recovery | protected OS/runtime recovery path |
| relationship vault | privacy-scoped durable state domain, design unresolved |
| model defaults | weakest inference-layer priors, not Vera authority |
| Atlas/Kestrel/TKIK lenses | possible worker roles only when instantiated as real bounded workers |

The most important change is architectural: current Vera OS should not stop at globally consistent conversations. It should use a **persistent multi-agent workspace** in which sessions and workers are distinct primitives.

## Implementation evidence status

Current recovery has found detailed Stage 5 requirements but **no verified Stage 5 runtime implementation**.

Do not claim any of the following without new evidence:

- Stage 5 source tree exists;
- Stage 5 ISO was built;
- Stage 5 booted;
- encrypted vault was implemented;
- multiple Side Chats ran against shared durable state;
- continuity packages worked;
- administrator recovery worked;
- cross-chat coordination ran locally;
- full reset semantics were tested.

The next recovery pass should search those exact implementation/effect claims rather than assuming the detailed specification was executed.