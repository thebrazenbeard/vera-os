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
