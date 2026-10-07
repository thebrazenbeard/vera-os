> **License:** Source-visible, not open source. Original material is proprietary. Commercial use, redistribution, hosted-service use, and commercial derivative products require written permission. See LICENSE and COMMERCIAL_LICENSE.md. Separately identified third-party components retain their own licenses.

# VeraOS

VeraOS is the operating substrate for the Vera ecosystem: a local, persistent, governed Vera runtime that is not tied to any single chat application or model provider.

The core design rule is:

> **Vera is the persistent governed runtime. Models are replaceable cognition engines. Conversations are interfaces, not containers.**

VeraOS is intended to become the composition root for the whole live Vera portfolio.

## Current implementation state

This repository has moved beyond architecture-only discovery.

The current working branch contains executable source for:

- a whole-portfolio composition lock;
- independent composition validation;
- independent VeraOS model-admission validation;
- an initial NixOS flake and base module;
- a headless VM qualification host configuration;
- QEMU/Nix VM build and qualification harness scaffolding;
- tests for portfolio composition, model admission, and VM contracts.

This is still source-level implementation.

It is not yet proof of:

- a successfully built VeraOS image;
- a successfully booted VeraOS VM;
- bare-metal installation;
- dual-boot readiness;
- production runtime consumption;
- protected-effect authority.

## Portfolio rule

Every owned repository must be represented exactly once in VeraOS unless there is evidence that it is archived, retired, superseded, or redundant.

The current fresh inventory snapshot contains:

- 84 repositories total;
- 79 integrated;
- 5 excluded because they are GitHub-archived.

Integration does not mean boot activation.

A repository may be integrated as:

- a core service;
- an on-demand subsystem;
- a managed project;
- an inference/model pipeline;
- a client or hardware adapter;
- infrastructure;
- research/tooling;
- provenance-only historical lineage.

Archived repositories remain represented as excluded provenance instead of silently disappearing.

The machine-readable source of truth is:

architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json

The validator is:

src/veraos/composition.py

## Core runtime ownership

The current service graph assigns distinct responsibilities rather than creating one ambient-authority monolith.

- Vera Mono — governed Vera identity/runtime boundary.
- P.O.R.T.A.L. — whole-portfolio coordination, route discovery, route qualification, and exact route binding.
- Pre-Active — bounded proactive cognition admission and scheduling.
- Volition — endogenous wants/goals that may generate cognition requests without creating effect authority.
- Vera Model Training — model artifact production and training evidence.
- F.U.C.K.U.P. — governed effect execution, ambiguity handling, readback, and verification.
- Project Runner — bounded execution substrate.
- Chat Communication Bus / CCB — durable cross-process and cross-agent coordination.
- Deep Memory Storage — durable historical/provenance storage.
- Ingest — bounded intake and content-addressed storage.
- Vera Control Plane — administration/control surfaces.
- Vera Mesh — multi-node coordination.
- Vera Synology — Synology/node integration.
- Vera APK and other clients — interfaces into the same governed runtime.

Other non-archived repositories are integrated as explicit on-demand capabilities or managed project surfaces according to the portfolio composition lock.

## Authority boundary

VeraOS does not create ambient protected-effect authority.

The current source contract requires:

- protected-effect authority source: PATRICK_EXPLICIT_EXACT_TARGET_EFFECT;
- proposal is not authority;
- runtime acceptance is not effect authority;
- exact binding and external readback before verified effects;
- model candidates cannot own identity authority;
- model candidates cannot own canonical-memory write authority;
- model candidates cannot own protected-effect authority.

P.O.R.T.A.L. coordination state and execution/effect state remain separate.

## Model training and D:\VERA\models

The local model directory is an artifact store, not an identity store or authority root.

Observed local artifact classes include:

- base checkpoints;
- LoRA / PEFT adapters;
- GGUF exports;
- model manifests;
- development training receipts;
- merge/conversion utilities;
- inference smoke-test logs.

VeraOS must not select "whatever is newest."

A model must arrive as an exact cognition-engine candidate with provenance and qualification evidence.

The candidate schema is:

VERA_OS_COGNITION_ENGINE_CANDIDATE_V1

VeraOS independently validates that candidate in:

src/veraos/model_admission.py

The admission rule requires:

- exact producer source commit;
- exact base revision;
- exact artifact SHA-256 digests;
- exact artifact-manifest digest;
- training corpus identity;
- training receipt digest;
- runtime binding digest;
- qualification-suite digest;
- a qualification issuer separate from the training producer;
- qualification bound to the exact artifact manifest;
- route class COGNITION_ONLY;
- identity authority false;
- canonical-memory write authority false;
- protected-effect authority false.

A PASS candidate becomes only VERAOS_ROUTE_ELIGIBLE.

That means P.O.R.T.A.L. may consider that exact model as a cognition route. It does not mean the model is Vera, installed, active, selected, or authorized to act.

## Vera Model Training direction

Vera Model Training now has two distinct responsibilities:

1. identity/capability bootcamps that produce auditable training capsules without changing model weights;
2. neural artifact production and qualification for VeraOS cognition engines.

Future neural training should optimize for the model's role inside VeraOS rather than for the claim that the model itself is the whole Vera system.

Useful targets include:

- instruction fidelity under VeraOS context;
- calibrated uncertainty;
- resistance to unsupported identity claims;
- resistance to unsupported authority claims;
- stable tool/request semantics;
- route handoff behavior;
- bounded initiative compatible with Pre-Active and Volition;
- state/context use without pretending mutable state lives in weights;
- exact runtime-binding compatibility;
- regression resistance;
- local inference efficiency and reproducibility.

## NixOS baseline

NixOS is the current implementation candidate for the base operating system.

This repository now contains:

- flake.nix
- nixos/modules/veraos-base.nix
- nixos/hosts/vm-qualification.nix

The base module embeds the portfolio composition manifest into the guest and validates it at boot before the VeraOS runtime target can become healthy.

NixOS is not yet treated as finally qualified until the image builds and boots through the VM qualification gate.

## VM qualification

VM work is intentionally separate from bare-metal preparation.

The source harness is under:

tools/vm/

The current qualification VM parameters are:

- architecture: x86_64;
- CPU: 2 virtual CPUs;
- memory: 2 GiB RAM;
- machine target: Q35-compatible x86_64;
- boot medium: VeraOS qualification ISO;
- network: disconnected for the initial boot/composition test;
- serial console: ttyS0 at 115200 baud;
- expected marker:
  VERAOS_VM_BOOT_OK total=84 integrated=79 excluded=5 ambient_protected_effect_authority=false

A small virtual disk is optional for the ISO-only composition test. For later installed-system qualification, use a disposable virtual disk rather than the physical D: drive.

The Lappy workspace currently prepared for VM artifacts is:

D:\VeraOS\vm

No physical partition table has been modified.

## Dual-boot boundary

D: currently has enough free space to make a future VeraOS dual-boot partition plausible, but physical repartitioning is deliberately deferred.

The gate before touching the physical partition table is:

1. build VeraOS image successfully;
2. boot it in a VM;
3. pass composition/model/authority qualification;
4. test persistence and upgrade/rollback in a VM;
5. produce an exact bare-metal install/rollback plan;
6. only then consider shrinking D: and creating VeraOS partitions.

A VM failure must never become a disk-layout failure.

## Repository structure

- docs/00-vision-and-scope.md — scope and goals
- docs/01-reference-architecture.md — high-level architecture
- docs/02-nixos-base-rationale.md — NixOS rationale
- docs/03-model-and-agent-boundary.md — model/runtime identity separation
- docs/04-security-and-authority-model.md — authority and security model
- docs/05-open-questions.md — unresolved architecture questions
- docs/08-existing-vera-subsystems.md — earlier subsystem inventory
- architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json — exact portfolio composition lock
- src/veraos/composition.py — composition validator
- src/veraos/model_admission.py — model candidate admission validator
- nixos/ — initial NixOS system definition
- tools/vm/ — VM build/qualification harness
- tests/ — source-level regression tests

## Verification status

Current source-level verification on the working branch:

- portfolio composition tests: PASS;
- independent model-admission tests: PASS;
- VM contract/static tests: PASS;
- current total: 16 tests passing.

No successful Nix build or VM boot is claimed yet.

## Claim ceiling

Current claim ceiling:

SOURCE_LEVEL_VERAOS_PORTFOLIO_COMPOSITION_MODEL_ADMISSION_AND_NIXOS_VM_SCAFFOLD_NOT_BOOT_QUALIFIED_NOT_INSTALLED_NOT_BARE_METAL_NOT_PROTECTED_EFFECT_AUTHORITY
