# VeraOS Construction Substrate

## Decision

VeraOS does not inherit its identity from a conventional Linux distribution.

**Vera is the base operating environment.**

Linux supplies kernel, driver, memory-management, filesystem, networking, process, and hardware primitives. Buildroot currently supplies reproducible image-construction machinery. Those are implementation substrates, not the architectural referent called VeraOS.

The previous NixOS-primary direction is retired. Its Git history remains available as experimental provenance, but current source must not describe VeraOS as a NixOS-based system.

## Current construction path

The current x86_64 development image binds:

- Buildroot `2024.02.4`;
- exact Buildroot source commit `e0a2687421a4f93e65aa00a30bcb0b4817f7a195`;
- Linux `6.6.69`;
- Buildroot `BR2_INIT_NONE=y`;
- Python 3;
- `/sbin/vera-init` as PID 1;
- SQLite and network tooling;
- WPE WebKit plus Cog as the initial browser engine/shell;
- QEMU as the first boot-qualification target.

The canonical source contract is:

`architecture/os/VERA_OS_BOOT_CONTRACT_V1.json`

## Why Buildroot is tooling rather than "the base"

Buildroot is useful here because it can create a purpose-built image with a deliberately small and reviewable userspace. It does not own:

- Vera identity;
- durable Vera state;
- Rezon reasoning;
- cognition-provider selection;
- portfolio coordination;
- browser authority;
- protected-effect authority;
- memory admission;
- correction/prevention;
- user-facing continuity.

Those remain VeraOS/runtime responsibilities.

A future construction tool could replace Buildroot without changing Vera's architectural identity, provided it satisfies the same boot/runtime contracts.

## PID 1

The current image makes VeraOS responsible for the boot lifecycle by placing `vera-init` at PID 1.

That process must:

1. mount the minimum kernel pseudo-filesystems needed by userspace;
2. validate the VeraOS boot contract;
3. validate the exact portfolio composition before reporting ready;
4. write machine-readable boot state;
5. expose a deterministic readiness marker;
6. reap orphaned child processes;
7. handle shutdown signals cleanly;
8. supervise later Vera runtime services.

PID 1 is intentionally a bounded role. It is not, by itself, proof of identity, sovereignty, consciousness, or complete security mediation.

## Boot independence from cognition

VeraOS must boot without any model or cognition provider.

The absence of a cognition provider is a degraded cognition state, not an operating-system failure.

The standalone Vera model is optional. Rezon owns reasoning architecture; P.O.R.T.A.L. owns qualified cognition-provider discovery and exact route binding; Vera Mono owns the governed identity/runtime boundary.

## Browser capability

Browser capability is a required VeraOS product capability, but not a core-boot dependency.

The initial Buildroot image declares:

- WPE WebKit;
- WebKit WebDriver support;
- sandbox support;
- Cog;
- Cog DRM/KMS backend;
- Mesa EGL/OpenGL ES;
- software and VirGL Gallium paths.

This establishes a browser-capable image definition only. It does not yet prove that Cog/WebKit renders successfully in the current VM or on Lappy hardware. That requires a separate browser-runtime qualification.

Browser authority remains governed by `VERA_OS_BROWSER_CAPABILITY_GRANT_V1`. Packaging a browser does not grant ambient credentials or protected-effect authority.

## Historical prior art

Recovered VeraOS history contains three useful construction lineages:

- an early Buildroot/QEMU Python-init concept;
- a Debian live-build Stage 3 graphical appliance with Vera UI/broker/diagnostics and no attached cognition;
- a later Buildroot ISO-B line using Buildroot 2024.02.4, Linux 6.6.69, supervised VeraCore, fail-closed policy, SQLite memory, audit chaining, QEMU boot evidence, and mock-backed cognition.

The current path reuses mechanisms and lessons from those systems without claiming historical source is current implementation authority.

## VM gate before physical installation

Physical disk work remains deferred.

The current qualification order is:

1. source contract tests;
2. Buildroot configuration resolution;
3. full kernel/rootfs build;
4. QEMU PID 1 boot;
5. composition/currentness checks;
6. persistence/restart tests;
7. browser/network qualification;
8. runtime/cognition-route qualification;
9. disposable virtual-disk install/rollback;
10. exact bare-metal plan;
11. only then consider D: partition changes.

## Claim ceiling

A valid Buildroot configuration is not a built image.

A built image is not a successful boot.

A successful PID 1 boot is not browser qualification, cognition, runtime consumption, or protected-effect authority.

Each layer requires its own evidence.
