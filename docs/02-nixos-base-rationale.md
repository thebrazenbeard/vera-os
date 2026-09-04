# NixOS Base Rationale

## Status

**Candidate, not yet adopted.** Patrick has proposed NixOS as the base for Vera OS. This document records why it appears promising and what must be validated before treating it as the implementation baseline.

## Why NixOS appears aligned

### Declarative system configuration

Vera OS benefits from system state that can be described, reviewed, versioned, reproduced, and rebuilt rather than accumulated through opaque manual installation steps.

A declarative base could make the following explicit:

- system packages;
- users and groups;
- system services;
- filesystem mounts;
- GPU/runtime dependencies;
- network listeners;
- firewall policy;
- worker sandboxes;
- model-serving services;
- runtime configuration locations;
- backup/recovery services.

### Reproducibility

The project should be able to answer: "What exact system configuration produced this runtime?" A Nix-based configuration model appears well suited to pinning dependencies and reconstructing a known system state.

### Rollback

Vera OS will change frequently during development. A system where configuration changes can be rolled back is attractive for an agent runtime that may eventually modify or propose modifications to its own surrounding software environment.

### Separation of configuration from mutable state

The architecture wants a strong distinction between:

- reproducible system configuration;
- model artifacts;
- durable mutable Vera state;
- user data;
- secrets;
- logs and audit records;
- ephemeral worker state.

NixOS appears compatible with that separation, but the exact filesystem/state model remains to be designed.

### Service composition

Vera OS is expected to contain several supervised services rather than one giant chatbot executable. NixOS modules may provide a clean way to declare and compose `verad`, inference servers, databases, worker templates, local APIs, UI services, and supporting infrastructure.

## What NixOS does not solve by itself

Choosing NixOS would not automatically provide:

- Vera's agent runtime;
- memory semantics;
- multi-agent orchestration;
- model routing;
- tool protocols;
- protected-effect authorization;
- a desktop or voice interface;
- model quality;
- safe self-modification;
- worker conflict resolution;
- migration semantics across runtime versions.

Those remain Vera OS responsibilities.

## Validation questions

Before NixOS becomes the confirmed base, test at least:

1. GPU driver and acceleration support for Patrick's target hardware.
2. llama.cpp and/or other chosen inference backend packaging and performance.
3. declarative deployment of the proposed Vera services.
4. persistent state paths that survive generation changes cleanly.
5. container/namespace or other worker isolation options.
6. secret management that does not put credentials into the Nix store.
7. remote administration/recovery behavior.
8. update and rollback behavior when Vera services have database migrations.
9. feasibility of creating reproducible installation media later without making custom-ISO work an early dependency.
10. whether NixOS can retain the useful separation already prototyped historically between Vera UI/session surfaces, cognition/model service, privileged broker, status, and durable services without coupling their lifecycle unnecessarily.

## Initial implementation strategy

Do **not** begin by maintaining a full custom distribution fork.

A lower-risk sequence is:

1. vanilla NixOS installation on development hardware or VM;
2. a `vera-os` flake/configuration repository;
3. Vera-specific NixOS modules and systemd services;
4. local inference and state services;
5. worker isolation and tool layer;
6. interfaces;
7. reproducible host deployment;
8. only then evaluate whether a branded installation image/distribution adds real value.

## Recovered historical baselines

A 2026-09-03 File Library recovery pass established that NixOS is **not** being considered from a blank slate. Vera OS had at least two materially different Linux implementation lines in July 2026. See `07-historical-vera-os-evidence.md` for the evidence boundary.

### Debian `live-build` — VERA Linux Stage 3 / Stage 4 source

The older `~/vera-stage3/VERA_Linux_Stage3_Source` tree used Debian Trixie `live-build` to construct an AMD64 hybrid live ISO with Syslinux + GRUB-EFI, systemd, LightDM, a Vera autologin/session, a graphical `vera-ui`, diagnostics, and a typed privileged broker.

A contemporaneous architecture checkpoint records the Stage 3 ISO as booting successfully with Vera autologin, graphical session, diagnostics, status panel, broker, and an honest null/offline cognition adapter. The UI itself explicitly said language-model cognition was not attached in Stage 3.

Stage 4 source then began adding a local Ollama-backed `vera-cognition` service, Unix socket client path, streamed UI generation, explicit backend/model-unavailable states, and systemd hardening. That checkpoint explicitly did **not** claim the Stage 4 ISO had been built/booted or that Ollama/model inference worked end to end.

This historical Debian line is directly relevant to the current NixOS decision because it demonstrates that a conventional service-oriented Linux host was already a workable fit for the Vera appliance concept. It also shows the cost of treating a booting branded desktop as the milestone when the intelligence/runtime beneath it was still incomplete.

### Buildroot — later ISO-B

A later `/home/vera/vera-ws06` effort used Buildroot `2024.02.4` and Linux `6.6.69`. Historical logs show x86_64 root filesystem generation, actual QEMU boots reaching `VERA OS ISO-B`, a supervised VeraCore runtime, default-deny policy, audit chaining, transactional SQLite memory, corruption/recovery testing, and model-adapter plumbing.

Buildroot demonstrated that a small reproducible Vera-branded appliance image can be built and boot-tested with tightly controlled dependencies. In the evidence recovered so far, however, the active cognition backend remained mock-backed.

## Why the historical evidence strengthens rather than weakens the NixOS candidate

The old Debian and Buildroot systems prove that the project already knows how to put Vera-specific services inside Linux images. Repeating that feat is not the hard problem anymore.

The new requirement is materially harder:

- persistent multi-agent workspace;
- many long-lived supervised services;
- independently scoped worker runtimes;
- durable task graphs and state;
- replaceable inference engines;
- development-time iteration and rollback;
- explicit capability policy;
- multiple attachable interfaces;
- potentially more than one local node.

That favors evaluating a declarative general-purpose host rather than optimizing first for the smallest boot image.

The base decision should therefore compare **roles**, not brands:

- Debian `live-build` is proven prior art for a richer graphical live-appliance image and conventional systemd service composition.
- Buildroot is proven prior art for minimal images, tightly bounded recovery/test appliances, and deterministic QEMU validation.
- NixOS is the current candidate for the primary persistent workstation/runtime host because the new architecture emphasizes service composition, isolation, reproducible configuration, local models, durable state, rapid iteration, and rollback.

A future architecture could use more than one construction method without contradiction—for example NixOS for the full Vera runtime and a smaller Buildroot-style recovery/hardware-validation image. That is only a design option, not a current decision.

## Decision guardrail

Do not choose NixOS merely because it sounds architecturally elegant, and do not reject it merely because Debian/Buildroot already booted. The winning base should be the one that best supports the **new executable Vera runtime** with the least hidden operational complexity. The historical implementations are test cases and prior art against which that claim can be measured.