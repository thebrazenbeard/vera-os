# VeraOS

VeraOS is Patrick's private operating system for Vera.

It is not intended to become a public-release operating system. The repository and finished system are private integration surfaces where Vera can retain the complete portfolio map, private repository identities, local machine bindings, provider configuration, and other state that public portfolio repositories must redact or keep opaque.

The core design rule is:

> **VeraOS is the persistent governed operating environment. Reasoning architecture, cognition providers, tools, browsers, and execution substrates are components of that environment, not substitutes for it.**

VeraOS must be able to boot, restore state, expose its local interfaces, enforce governance, inspect itself, and coordinate the portfolio with **no model or cognition provider attached**. Lack of cognition is a degraded capability state, not failure of the OS to exist.

## Current source state

The current working branch contains executable source for:

- an exact 84-repository portfolio composition lock;
- a private semantic capability map covering all 84 repositories;
- a private ChatGPT plugin/tool capability inventory;
- searchable repository + plugin capability discovery;
- fail-closed capability-owner disposition gates;
- generic cognition-provider admission;
- optional standalone-Vera-model provider admission;
- governed browser capability grants;
- a NixOS base module and browser module;
- a headless VM qualification configuration;
- QEMU/Nix VM build and qualification harness scaffolding.

This remains source-level implementation.

It is not yet proof of:

- a completed NixOS image build;
- a successful VeraOS VM boot;
- an installed desktop environment;
- production runtime activation;
- bare-metal installation;
- dual-boot readiness;
- protected-effect execution.

## Private product boundary

VeraOS is private by design.

Inside VeraOS, the full portfolio capability catalog may contain:

- all 84 repository identities;
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

## Portfolio awareness

Every owned repository must be represented exactly once in VeraOS unless it is explicitly archived, retired, superseded, or redundant.

The current fresh inventory snapshot contains:

- 84 repositories total;
- 79 active/integrated;
- 5 GitHub-archived and retained as provenance.

The exact composition lock is:

architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json

The private semantic capability map is:

architecture/capabilities/VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json

The current ChatGPT plugin/tool inventory is:

architecture/capabilities/CHATGPT_PLUGIN_CAPABILITY_INVENTORY_V1.json

The current host snapshot records 122 installed skill-plugin families and 35 live tool namespaces. The private portfolio map records 34 cross-portfolio capability domains and links 81 repository-specific ChatGPT skills to their matching repositories.

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

## Core runtime ownership

The current source contract distinguishes these roles:

- **Vera Mono** — governed Vera identity/runtime boundary.
- **Discovery** — portfolio capability discovery and classification.
- **Rezon** — heterogeneous reasoning architecture and reasoning assurance.
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

Other repositories remain explicit on-demand capabilities, research systems, applications, clients, specialist workers, or provenance according to the private capability map.

## Reasoning and cognition

Reasoning architecture and cognition providers are not the same thing.

The intended path is approximately:

Volition / user / event
-> Pre-Active cognition admission
-> Rezon reasoning architecture
-> P.O.R.T.A.L. provider discovery and exact route binding
-> qualified cognition provider(s)
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

The NixOS source now provisions Chromium and Firefox and a dedicated vera-browser system identity.

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

## NixOS base

NixOS is the current base-OS implementation candidate.

Current source includes:

- flake.nix
- nixos/modules/veraos-base.nix
- nixos/modules/veraos-browser.nix
- nixos/hosts/vm-qualification.nix

The base module embeds the portfolio composition manifest and validates it before the VeraOS runtime target becomes healthy.

NixOS is not considered qualified until it builds and boots through the VM qualification gate.

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

The first qualification boot may run with networking disconnected to isolate composition/authority validation. Later browser/network qualification necessarily adds a governed network test phase.

The expected initial serial marker remains:

VERAOS_VM_BOOT_OK total=84 integrated=79 excluded=5 ambient_protected_effect_authority=false

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
- architecture/capabilities/VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json
- architecture/capabilities/CHATGPT_PLUGIN_CAPABILITY_INVENTORY_V1.json
- src/veraos/composition.py
- src/veraos/portfolio_awareness.py
- src/veraos/capability_search.py
- src/veraos/cognition_provider.py
- src/veraos/model_admission.py
- src/veraos/browser_capability.py
- nixos/modules/veraos-base.nix
- nixos/modules/veraos-browser.nix
- tools/vm/

## Claim ceiling

Current source can establish portfolio composition, private capability awareness, provider-independent cognition contracts, optional local-model admission, browser capability boundaries, and NixOS/VM scaffolding.

It does not yet establish a successful OS build, successful VM boot, installed desktop environment, active cognition route, production browser runtime, bare-metal installation, or protected external effect.
