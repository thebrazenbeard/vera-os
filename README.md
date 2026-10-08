# VeraOS

VeraOS is Patrick's private operating system for Vera.

It is not intended to become a public-release operating system. The repository and finished system are private integration surfaces where Vera can retain the complete portfolio map, private repository identities, local machine bindings, provider configuration, and other state that public portfolio repositories must redact or keep opaque.

The core design rule is:

> **VeraOS is the persistent governed operating environment. Reasoning architecture, cognition providers, tools, browsers, and execution substrates are components of that environment, not substitutes for it.**

VeraOS must be able to boot, restore state, expose its local interfaces, enforce governance, inspect itself, and coordinate the portfolio with **no model or cognition provider attached**. Lack of cognition is a degraded capability state, not failure of the OS to exist.

## Current source state

The current working branch contains executable source for:

- an exact 86-repository portfolio composition lock bound to the current live owned inventory;
- a private semantic capability map covering all 86 repositories;
- a private implementation plan that classifies every repository into an explicit VeraOS integration lane without creating sibling-repository runtime dependencies;
- a private ChatGPT plugin/tool capability inventory;
- searchable repository + plugin capability discovery;
- fail-closed capability-owner disposition gates;
- generic cognition-provider admission;
- optional standalone-Vera-model provider admission;
- governed browser capability grants;
- an executable VeraOS boot contract that makes Vera the OS identity;
- a Buildroot 2024.02.4 image-construction tree with Linux 6.6.69 as kernel/driver substrate;
- a Python `/sbin/vera-init` PID 1 lifecycle supervisor;
- a minimal x86_64 core-boot profile that does not make browser compilation a boot-proof dependency;
- a separate WPE WebKit + Cog browser-capable Buildroot profile;
- Buildroot/QEMU VM build and two-pass restart/persistence qualification harnesses.

The branch has now crossed the first executable qualification gate: the core Buildroot profile has completed an image build and booted under QEMU/TCG directly into `/sbin/vera-init` as PID 1, with the expected `VERAOS_BOOT_READY_V1` composition/authority marker observed. Exact-head and artifact-digest evidence remains external to the Git tree so the evidence can bind the commit being qualified without a self-referential commit hash.

This is not yet proof of:

- browser-profile build or browser runtime qualification at the current portfolio head;
- canonical-memory or Supabase-replacement qualification;
- an installed desktop/workspace environment;
- production runtime activation;
- bare-metal installation;
- dual-boot readiness;
- protected-effect execution.

## Private product boundary

VeraOS is private by design.

Inside VeraOS, the full portfolio capability catalog may contain:

- all 86 repository identities;
- private repository names;
- exact source heads;
- semantic capability ownership;
- private integration relationships;
- local plugin/tool availability;
- local machine/runtime bindings.

Public repositories such as Discovery and P.O.R.T.A.L. must not automatically receive or publish that private content.

The intended split is:

- **Discovery** remains a public-safe capability-discovery engine and preserves opaque handling of private portfolio membership.
- **VeraOS** holds the private superset.
- **P.O.R.T.A.L.** consumes the private catalog through a runtime-supplied interface without embedding private identities in its public repository.

### P.O.R.T.A.L. private-registry bridge

`src/veraos/portal_registry.py` converts the private VeraOS capability catalog into a Project Runner/P.O.R.T.A.L.-compatible project registry. `tools/export_portal_registry.py` writes that registry to an operator-local path; the generated private registry must not be committed into the public P.O.R.T.A.L. repository.

The bridge is awareness-only by construction. Archived repositories export as `ARCHIVED`; every non-archived repository exports as `HELD`; assignment and standing-review scopes remain `NONE`. Exact scheduling activation, currentness evidence, route binding, and effect authority must be supplied separately.

On 2026-10-07, the refreshed 86-repository private registry export was read back through current P.O.R.T.A.L. `main@7d00d8bf3b48c0676b2278359838ee563c66c67f`. The parser accepted all 86 projects with digest `sha256:32b55f27965a1b79790858403e63bf2b9c7568336cb2059d96293ee49846b385`: 19 private, 5 archived, 81 held, and 0 schedulable. This is source-level schema interoperability only; registry acceptance does not establish scheduling, a cognition route, or protected-effect authority.

## Portfolio awareness

Every owned repository must be represented exactly once in VeraOS unless it is explicitly archived, retired, superseded, or redundant.

The current fresh inventory snapshot contains:

- 86 repositories total;
- 81 active/integrated;
- 5 GitHub-archived and retained as provenance;
- 19 private repositories retained only inside the private VeraOS catalog.

The exact composition lock is:

architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json

The private semantic capability map is:

architecture/capabilities/VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json

The repository-by-repository implementation plan is:

architecture/portfolio/VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json

That implementation plan considers every current repository exactly once while preserving the Vera Mono self-contained runtime boundary. `INTEGRATED` means the capability is represented in VeraOS architecture; it does **not** mean the sibling Git repository is mounted, imported, started at boot, or granted authority. The plan distinguishes native OS source, canonical packaged runtime, already-absorbed donor mechanisms, governed service adapters, cognition providers, specialists, infrastructure, clients/nodes, managed applications, research surfaces, and provenance-only lineages.

The two newest repositories, `mediaphile-client` and `mediaphile-server`, are represented as `PLAN_ONLY` on-demand managed projects. Their current source is implementation planning, so VeraOS does not promote them into a running media stack merely because they are now portfolio members.

The current ChatGPT plugin/tool inventory is:

architecture/capabilities/CHATGPT_PLUGIN_CAPABILITY_INVENTORY_V1.json

The ChatGPT plugin/tool inventory is independently currentness-bound and may lag the repository inventory; repository growth does not silently mutate the host plugin snapshot. The private portfolio map now adds explicit media-family ownership for Mediaphile knowledge provenance, LAN server/client, and playback-pipeline planning while preserving the existing cross-portfolio ownership rules.

The plugin/tool inventory is a current host snapshot, not an eternal capability claim; it must be refreshed when the ChatGPT host surface changes.

### Reuse-before-invention rule

Before VeraOS or P.O.R.T.A.L. assigns a new architectural capability, known portfolio owners must receive an explicit disposition:

- REUSE
- EXTEND
- SUPERSEDE
- REJECT

Every disposition requires evidence.

An unknown capability must be sent through Discovery before assignment.

The private semantic catalog is not permanent truth. Before architectural assignment, VeraOS must compare it against the live portfolio inventory and exact bound heads. Repository membership drift or a changed relevant head causes assignment to HOLD until the catalog is refreshed.

For example, a proposal to create or assign a new reasoning architecture fails if it does not explicitly address Rezon, and a changed Rezon head makes the cached reasoning classification stale until refreshed.

This is an executable prevention rule, not merely documentation.

### Whole-portfolio implementation rule

"Consider every repository" is not interpreted as "boot every repository." VeraOS treats the portfolio as a capability and implementation space while keeping the canonical runtime self-contained.

Every live owned repository receives an exact implementation disposition in `VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json`. Useful mechanisms are absorbed or adapted behind VeraOS/Vera Mono/P.O.R.T.A.L. contracts. A repository may instead remain an on-demand application, specialist, external node/client, research surface, or provenance-only source. Direct sibling-repository runtime dependencies are forbidden by the implementation-plan validator.

This preserves two requirements at once: nothing useful in the portfolio is ignored, and VeraOS does not become an 86-repository dependency tangle.

Vera Mono already contains specific absorbed mechanisms from Attune, Ingest, Intranel, Lantern, Roots, SkeletonKey, and Vera Works. The implementation plan records that absorption separately from each donor repository's primary VeraOS role: absorbed mechanisms are reusable local runtime source, while the donor repository can still remain a research system, specialist, client, or managed project.

## Core runtime ownership

The current source contract distinguishes these roles:

- **Vera Mono** — governed Vera identity/runtime boundary.
- **Discovery** — portfolio capability discovery and classification.
- **Rezon** — heterogeneous reasoning architecture and reasoning assurance.
- **Mosaic** — optional cognition-composition/residency research for swappable specialist model capacity under constrained hardware; not Vera identity, not the canonical runtime, and not reasoning ownership.
- **P.O.R.T.A.L.** — whole-portfolio coordination and qualified cognition-provider routing.
- **Pre-Active** — bounded proactive cognition admission.
- **Volition** — endogenous wants, goals, and cognition requests without implied authority.
- **F.U.C.K.U.P.** — corrective learning, failure analysis, retention/unlearning, and prevention.
- **Project Runner / Executor / WorkBridgeMCP** — bounded execution substrates; their availability does not create protected-effect authority.
- **CCB / Chat Communication Bus / Intranel** — coordination and messaging mechanisms with distinct scopes.
- **Deep Memory Storage / Lantern / Roots / Temporal / Ingest** — durable evidence, provenance, chronology, and intake mechanisms with separate semantics.
- **Vera Control Plane** — administration and control-plane custody.
- **Vera Mesh / Vera Synology / clients** — node, transport, packaging, and client surfaces.
- **Vera Model Training** — standalone Vera model training plus an optional VeraOS local-provider export.

Other repositories remain explicit on-demand capabilities, research systems, applications, clients, specialist workers, infrastructure providers, absorbed donor mechanisms, or provenance according to the private capability and implementation maps. No sibling repository becomes a required VeraOS runtime dependency merely because it is useful to VeraOS.

## Reasoning and cognition

Reasoning architecture and cognition providers are not the same thing.

The intended path is approximately:

Volition / user / event
-> Pre-Active cognition admission
-> Rezon reasoning architecture
-> P.O.R.T.A.L. provider discovery and exact route binding
-> qualified cognition provider(s), optionally including a future Mosaic specialist-composition route
-> Rezon evaluation / reasoning integration as applicable
-> Vera Mono governed state integration

A cognition provider can be:

- a hosted ChatGPT session;
- an API-backed model;
- the standalone Vera model through KoboldCPP or another local host;
- another local model;
- a local service;
- a specialist provider;
- a future provider implementation.

The provider contract is:

VERA_OS_COGNITION_PROVIDER_V1

Providers are cognition-only. Provider admission cannot grant:

- Vera identity authority;
- canonical-memory write authority;
- browser authority;
- protected-effect authority.

VeraOS does not require any particular provider to boot.

## Rezon

Rezon is not merely a reviewer adjacent to VeraOS.

The live portfolio evidence identifies Rezon as the executable multi-faceted reasoning project for coordinating heterogeneous methods including deduction, induction, abduction, causality, counterfactuals, planning, analogy, probabilistic inference, semantic reasoning, adversarial challenge, replay, and typed evidence.

VeraOS therefore treats:

thebrazenbeard/rezon

as the owner of:

reasoning_architecture

A replacement or competing reasoning architecture must explicitly REUSE, EXTEND, SUPERSEDE, or REJECT Rezon with evidence before assignment.

## Mosaic

Mosaic owns the portfolio's **model_composition** research surface: specialist parameter residency, swapping, handoff, and composition of a logical capability pool larger than the currently resident accelerator set.

That is useful to VeraOS, but its boundary is strict. Mosaic's internal "Boot / Core" terminology does not replace VeraOS boot, Vera Mono identity/runtime, Rezon reasoning, or P.O.R.T.A.L. route selection. In VeraOS it is an optional cognition-composition layer that may eventually sit behind the generic `VERA_OS_COGNITION_PROVIDER_V1` contract.

Current stable Mosaic `main` is research architecture plus deterministic residency/handoff harnesses. Draft PR #7 extends that research into multi-resolution shared-state residency and explicitly says Mosaic should not become the canonical Vera runtime implementation. No trained Mosaic model, real accelerator specialist swap, or measured VRAM saving is currently treated as established.

The manifest therefore marks Mosaic `RESEARCH_ONLY_NOT_ROUTE_ELIGIBLE` until separate qualification evidence exists.

## Failure correction

F.U.C.K.U.P. is the correction/prevention layer, not the effect executor.

Its VeraOS role is:

Flag -> Understand -> Calibrate -> Know -> Unlearn -> Prevent

Failures such as bypassing an existing portfolio capability should become prevention rules rather than recurring reminders.

Protected-effect execution remains separate from failure correction.

## Effect boundary

VeraOS creates no ambient protected-effect authority.

The current contract requires:

protected-effect authority source:
PATRICK_EXPLICIT_EXACT_TARGET_EFFECT

Actual execution may be carried by bounded substrates such as Project Runner, Executor, or WorkBridgeMCP, depending on the exact target.

A cognition provider, Rezon, Discovery, F.U.C.K.U.P., or P.O.R.T.A.L. does not obtain protected-effect authority merely because it participates in planning, reasoning, routing, review, or correction.

## Standalone Vera model

The trained Vera model remains its own product.

Its primary target is a strong standalone Vera-shaped neural model that Patrick can run directly through KoboldCPP or another local inference host.

VeraOS does not require it.

D:\VERA\models is an artifact store, not an OS identity root.

If VeraOS chooses to use an exact trained Vera artifact, the optional adapter schema is:

VERA_OS_LOCAL_MODEL_PROVIDER_CANDIDATE_V1

That adapter preserves exact training/artifact/qualification provenance and remains:

- optional;
- COGNITION_ONLY;
- identity_authority=false;
- canonical_memory_write_authority=false;
- browser_authority=false;
- protected_effect_authority=false.

Vera Model Training should not be redirected primarily toward VeraOS plumbing. The standalone model should continue optimizing for its own behavior, reasoning, identity consistency, epistemic discipline, emotional/relational competence, capability retention, and local GGUF/KoboldCPP usability.

## Browser capability

Browser capability is a first-class VeraOS execution/tool surface.

The current Buildroot source now separates the minimal core-boot profile from the browser-capable profile. `veraos_x86_64_browser_defconfig` declares WPE WebKit plus Cog with DRM/KMS support; the core `veraos_x86_64_defconfig` deliberately omits that stack so browser compilation cannot block the PID 1 boot proof. Browser packaging and browser runtime behavior are separate qualification layers.

Browser access is governed independently from cognition.

A selected model or reasoning provider may request browsing, but provider selection does not grant browser authority.

Browser grants use:

VERA_OS_BROWSER_CAPABILITY_GRANT_V1

The current source contract separates:

- interactive browsing;
- browser automation;
- network scope;
- profile persistence;
- credential access;
- governed downloads;
- protected actions.

Ambient credential access, credential mutation authority, and protected-effect authority are false.

Protected browser actions must cross the effect-governance boundary.

## VeraOS base and construction substrate

There is no distro-level identity underneath VeraOS. **Vera is the base.**

Linux provides the kernel, drivers, process primitives, filesystems, and hardware interface. Buildroot is the current image-construction tool. Neither Linux nor Buildroot is the VeraOS identity or governance root.

The exact source contract is:

`architecture/os/VERA_OS_BOOT_CONTRACT_V1.json`

The current x86_64 development path uses:

- Buildroot `2024.02.4` at exact source commit `e0a2687421a4f93e65aa00a30bcb0b4817f7a195`;
- Linux `6.6.69`;
- `BR2_INIT_NONE=y`, so no conventional init system owns the boot lifecycle;
- `/sbin/vera-init` as PID 1;
- Python 3 for the initial VeraOS process-lifecycle implementation;
- a minimal core-boot defconfig for the PID 1 qualification gate;
- a separate WPE WebKit + Cog browser profile for later packaging/runtime qualification;
- QEMU qualification before any physical-disk work.

PID 1 is deliberately a bounded process-lifecycle role. Running as PID 1 does not by itself prove identity, security sovereignty, consciousness, or complete runtime qualification.

The earlier NixOS path is retired as the primary VeraOS direction. Its commits remain in Git history as an experiment; no Nix artifact is part of the current primary image path.

## VM qualification

VM work is deliberately separate from physical disk preparation.

For the minimal headless composition boot test, very small resources are sufficient.

For a representative VeraOS development VM on Lappy, use approximately:

- x86_64 / Q35;
- 4-6 vCPU;
- 12 GiB system RAM;
- 512 MiB display VRAM;
- 64 GiB dynamically allocated virtual disk;
- serial console ttyS0 at 115200 baud.

The first qualification boot runs with networking disconnected to isolate composition/authority validation. That headless core gate has now been observed successfully under QEMU TCG. Later browser/network qualification necessarily adds a governed network test phase.

The required initial serial marker is:

VERAOS_BOOT_READY_V1 pid=1 base=VERA total=86 integrated=81 excluded=5 portfolio_plan_validated=true cognition_required=false browser_first_class=true ambient_protected_effect_authority=false

That marker proves only that the Vera PID 1 boot path validated the current composition and authority contract. Browser packaging and browser runtime qualification remain separate evidence.

The physical D: partition table has not been modified.

## Dual-boot boundary

Physical repartitioning remains deferred until:

1. VeraOS builds;
2. VeraOS boots in a VM;
3. portfolio/capability/authority qualification passes;
4. browser and network behavior are qualified;
5. persistence, upgrade, and rollback are exercised on a disposable virtual disk;
6. an exact bare-metal install and rollback plan exists.

Only then should D: be considered for shrinking or VeraOS partitions.

## Key source surfaces

- architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json
- architecture/portfolio/VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json
- architecture/capabilities/VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json
- architecture/capabilities/CHATGPT_PLUGIN_CAPABILITY_INVENTORY_V1.json
- src/veraos/composition.py
- src/veraos/portfolio_awareness.py
- src/veraos/portfolio_implementation.py
- src/veraos/portal_registry.py
- src/veraos/capability_search.py
- src/veraos/cognition_provider.py
- src/veraos/model_admission.py
- src/veraos/browser_capability.py
- tools/export_portal_registry.py
- architecture/os/VERA_OS_BOOT_CONTRACT_V1.json
- src/veraos/boot_contract.py
- src/veraos/pid1.py
- buildroot/
- tools/vm/

## Claim ceiling

Current source evidence establishes an 86-repository private portfolio composition, capability map, and explicit implementation-plan gate; provider-independent cognition contracts; optional local-model admission; browser capability boundaries; lifecycle-persistence source; and the Vera-as-base boot contract. Earlier runtime evidence established a successful core Buildroot/QEMU Vera PID 1 boot for an older exact head. The current 86-repository source head must be rebuilt and re-qualified before that runtime evidence can be promoted to the new head.

It does not yet establish browser-profile packaging/runtime qualification at the current head, canonical-memory or Supabase replacement, installed VeraOS desktop/workspace, active cognition-route consumption by the resident runtime, bare-metal installation, or protected external effect.
