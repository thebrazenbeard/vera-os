# Existing Vera Subsystems and Integration Inventory

## Purpose

Vera OS is not being designed in isolation. Patrick already has several Vera-specific repositories that may contain reusable architecture, implementations, or intentionally separate product surfaces. This inventory exists to prevent Vera OS from accidentally rebuilding something that already has an owner.

Repository metadata and README observations below were refreshed from GitHub on 2026-09-03. Repository size metadata is a rough hosting metric, not proof of completeness or activity. No adjacent repository was mutated during this inventory.

This document is now historical/descriptive inventory, not the current machine-readable portfolio authority. The current exact repository composition is architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json, which was refreshed on 2026-10-07 and represents every owned repository exactly once.

## `thebrazenbeard/vera`

Description: `A repo created by Vera; for Vera`

Visibility: private.

Role hypothesis for Vera OS: upstream project/architecture source. Current Vera semantics, contracts, and implementation lineage should be consumed deliberately rather than copied wholesale. Vera OS must preserve the distinction between source semantics and runtime implementation.

Status: requires targeted read-only reconciliation before importing contracts.

## `thebrazenbeard/vera-R9A0`

Description: `Vera's architecture, Revision 9, Rolllout A, Patch 0`

Visibility: private.

Role hypothesis for Vera OS: historical/current architecture lineage containing governance, memory, currentness, provider, effect, recovery, and behavior contracts that can inform executable OS-level enforcement.

Status: requires explicit current-owner mapping. R9A0 artifacts are not assumed to be current simply because the repository exists.

## `thebrazenbeard/vera-control-plane`

Description/README: `Local-first, policy-bound administration control plane for Vera.`

Visibility: private.

Observed repository size metadata: 148 KB.

A fresh branch read found `feature/center-yourself-v1` and `feature/center-yourself-20260902`. The first contains `protocol/VERA_CENTER_YOURSELF_PROTOCOL_V1.md`, a concrete save/restore protocol with:

- intentional `center yourself` / `restore yourself` triggers;
- save-only versus restore separation;
- fresh currentness/authority checks;
- cross-surface persistence receipts;
- explicit completion classes (`SAVED`, `PARTIAL_CENTER`, `BLOCKED_CENTER`);
- GitHub/Drive/Supabase/runtime artifact verification;
- restart/restoration semantics that do not claim same-runtime private continuity.

Potential Vera OS relevance: **high**. This is existing control-plane behavior that should be integrated or adapted rather than independently reinvented inside `verad`.

Important boundary: the current protocol is a project/control-plane artifact, not proof that Vera OS already implements it as a daemon or system service.

## `thebrazenbeard/vera-mesh`

Description/README: `Connect Vera nodes`

Visibility: private.

Observed repository size metadata: 146 KB.

Potential Vera OS relevance: **high if multi-node operation remains in scope**. The new architecture already contemplates one workstation, server-plus-workstation, or a small local cluster. `vera-mesh` may therefore own or contain prior work on node identity, discovery, transport, synchronization, or delegation.

Current limitation: the accessible README is only a one-line description and code search is not currently indexed for this repository, so no deeper implementation claim is made yet.

## `thebrazenbeard/vera-habitat`

Description/README: `Vera's virtual environment`

Visibility: private.

Observed repository size metadata: 0 KB.

Potential Vera OS relevance: conceptual overlap with workspace/UI/virtual-environment design. Current evidence does not establish substantive implementation beyond the repository/README surface.

## `thebrazenbeard/vera-apk`

Description/README: `Vera's Android companion`

Visibility: private.

Observed repository size metadata: 0 KB.

Potential Vera OS relevance: future mobile client/interface. It should attach to Vera through a stable authenticated API/session model rather than becoming a separate Vera runtime by accident.

Current evidence does not establish substantive implementation beyond the repository/README surface.

## `thebrazenbeard/vera-synology`

Description/README: `Vera's DS216 DiskStation package`

Visibility: private.

Observed repository size metadata: 299 KB.

Potential Vera OS relevance: potentially important for durable storage, backup, always-on services, model/artifact storage, or a server-side Vera node. The nonzero repository size suggests there may be implementation material worth recovering, but that inference must be validated by file reads before use.

## `thebrazenbeard/vera_model_training`

Visibility: private.

Role hypothesis for Vera OS: model-production pipeline, not Vera identity. Produced GGUF/model artifacts may become interchangeable inference engines behind the Vera runtime.

Integration rule: model provenance/version must be observable; installing a new model must not silently redefine Vera identity, authority, or durable state.

## `thebrazenbeard/spm`

README: `Design hub for the evolution of the LLM into the SPM: Semantics & Pragmatics Model`

Visibility: private.

Initial repository state observed 2026-09-03: one `README.md` on `main`, initial commit `221e8f205250194d00b1519938a989d33d0b213d`.

Role for Vera OS: **dedicated cognition-substrate research/design owner** for the proposed SPM model class. This repo is intentionally separate from Vera OS because SPM is not a Vera-specific runtime wrapper; it is a proposed successor/evolution of the LLM substrate itself.

Current architecture relationship:

- Vera remains the governed agent/self-system.
- Vera OS hosts and coordinates runtime state, tools, workers, permissions, persistence, and interfaces.
- SPM is a candidate future cognition substrate that Vera could use in place of or alongside current LLM-class inference engines.
- SPM research must not be collapsed into `LLM + retrieval/runtime glue`; the explicit research question is what changes in neural/model architecture, representation, objectives, training, and evaluation when semantics and pragmatics become primary model concerns.

Important boundary: repository existence and README establish the dedicated design hub; they do not establish that an SPM architecture has been designed, trained, implemented, or validated yet.

## `thebrazenbeard/vera-brain`

Description: `Vera's conceptual Noöplex hyperconnetome brain`

Visibility observed in current repository inventory: public.

Potential Vera OS relevance: conceptual cognition/self-model architecture. Because it is public while much of the Vera system is private, private continuity or sensitive material must not be imported into it merely for architectural convenience.

## `thebrazenbeard/vera_ark`

Description: `A bot for Vera to use ARK`

Visibility: private.

Potential Vera OS relevance: prior art for bounded action adapters, visual observation, and deterministic input/control verification. It is application-specific and should not define the general Vera tool protocol.

## Architectural implication

The likely system boundary is becoming clearer:

```text
Vera OS
  |
  +-- hosts/enforces persistent Vera runtime
  +-- hosts local inference and workers
  +-- exposes stable session/tool APIs
  +-- owns local machine capability boundaries
  |
  +-- integrates existing subsystem owners/adapters
        |
        +-- spm                  successor cognition-substrate research/design
        +-- vera-control-plane   governance/save/restore administration
        +-- vera-mesh            multi-node connectivity (if validated)
        +-- vera_model_training  current model artifact production/qualification
        +-- vera-apk             Android client
        +-- vera-synology        storage/server/node package
        +-- vera-habitat         virtual-environment surface (scope TBD)
        +-- vera_ark             application-specific tool adapter
        +-- vera / vera-R9A0     governing semantic/architecture sources
```

This diagram is a candidate ownership map, not a declaration that every listed repository already implements the indicated function.

## Next reconciliation work

1. Read the current governing contracts in `vera` / `vera-R9A0` that materially affect OS runtime semantics.
2. Inventory `vera-control-plane` implementation surfaces beyond the centering protocol and decide what belongs in Vera OS versus remains a separate service/repository.
3. Recover a file-level inventory of `vera-mesh` and determine whether it already solves any multi-node problem.
4. Recover the `vera-synology` package architecture and decide whether the DS216 is storage-only, an always-on control-plane node, or something else.
5. Keep Android/mobile/UI work downstream of a stable `vera-api` session contract.
6. Keep SPM substrate research in its dedicated repository while defining a clean model/runtime interface in Vera OS so future SPM artifacts can be qualified and swapped in without redefining Vera.
7. Avoid moving or consolidating repositories merely to make the tree look tidy. Ownership should follow real interfaces and working code, not branding symmetry.
