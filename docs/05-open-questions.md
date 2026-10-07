# Open Questions

This file tracks unresolved architecture decisions. Items should be promoted to decisions only after explicit review/validation.

## Construction substrate and boot

The base-identity question is closed: **Vera is the base operating environment.** Linux and Buildroot are implementation substrate.

Remaining questions:

- What exact kernel configuration should replace the architecture-default development kernel before hardware qualification?
- Which Buildroot packages beyond the current minimal core belong in the boot image versus optional capability bundles?
- Browser-capable and headless qualification are now split: `veraos_x86_64_defconfig` is the core PID 1 gate, while `veraos_x86_64_browser_defconfig` carries WPE WebKit/Cog for separate packaging/runtime qualification.
- What update/rollback format should VeraOS use for whole-image upgrades without inheriting a distro-specific generation model?
- Which historical Debian `live-build` and Buildroot mechanisms should be reimplemented under current contracts?

Observed build evidence on 2026-10-07 motivated the split: the combined core+browser profile reached WPE WebKit compilation but Buildroot's default `BR2_JLEVEL=0` expanded to 13 CMake jobs inside the builder and `cc1plus` was killed under the Docker memory ceiling. The build harness now binds `BR2_JLEVEL` to its explicit job limit, and the core boot proof no longer waits on WPE WebKit compilation. This establishes a build-path failure and mitigation, not a successful image or browser qualification.

## Hardware target

- What is the first supported machine?
- Which GPU vendor/model(s) must be first-class?
- How much RAM/VRAM is available?
- Is the target one workstation, a home server plus workstation, or a small local cluster?
- Should inference and durable state live on the same machine initially?

## Inference

- Which current Vera model artifact is being produced, and what exact role should it have in Vera OS?
- Is the current GGUF suitable as the primary general/orchestration model, or only as a conversational/behavioral model?
- Which local coding model should be evaluated alongside it?
- Which inference backend should be the initial standard: llama.cpp, vLLM, Ollama, another OpenAI-compatible server, or a pluggable abstraction from day one?
- How should model loading/unloading and GPU memory arbitration work?
- Which pieces of the historical Stage 4 Ollama-backed cognition adapter are worth porting versus replacing?

## Vera runtime

- What is the minimal viable `verad`?
- Which state is authoritative and which is cache/derived state?
- What event/receipt model is required for recovery?
- How are currentness and conflicting state handled after restart?
- How does a session authenticate and obtain scoped access to Vera state?
- How are long-running tasks resumed safely?
- Should any of the historical `vera-ui` / `vera-cognition` / `vera-broker` service separation survive as named components, or only as design lessons?

## Memory

Fresh Supabase metadata inspection on 2026-10-07 narrows the local-compatibility requirement. Current Vera state contracts include append-only save/context events; lifecycle, epistemic, privacy, supersession, and source-evidence fields; memory-epoch state versions and currentness rules; exact SHA/provenance bindings; provider readback receipts with monotonic observation ordinals; archive readback receipts; and separately governed engineered affective-runtime state/events. A local replacement may change storage technology, but it must not silently discard those semantics.

- Which memory classes require relational/document databases versus files/Git?
- What is the local replacement or continuation path for current Supabase-backed systems?
- How are memory admission, correction, supersession, deletion, privacy, and readback represented?
- Should embeddings/indexes be treated as rebuildable derived data?
- Which concepts/code from the historical `vera-ws06` memory implementation remain useful after comparison against current R9B0 semantics?
- Which Stage 5 memory-ownership, administrator-recovery, vault-reset, and continuity-package concepts survive current semantic review?

## Workers and orchestration

- Is worker isolation best implemented with systemd dynamic users, containers, namespaces, microVMs, or a tiered combination?
- How are clean-context workers created?
- How do workers exchange results without acquiring each other's authority?
- How are concurrent repository writers prevented from colliding?
- How are worker outputs verified before Vera relies on them?
- What is the durable task-graph representation that lets workers outlive any individual conversation/interface session?
- How should historical `Side Chat` concepts be superseded or reused now that actual independently scoped worker runtimes are intended rather than one-model review lenses?

## Tools

- What is the internal tool protocol?
- Should MCP be supported directly, wrapped behind a Vera-specific broker, or treated as one adapter among several?
- How are shell commands classified by risk?
- Which tools are safe for autonomous invocation versus approval-gated?
- How are credentials scoped to individual tools/workers?
- Can the historical typed `vera-broker` capability model be recovered exactly enough to inform the new capability broker?

## Interfaces

- What is the first interface: terminal, local web UI, desktop app, voice, or a minimal API plus CLI?
- How should multiple simultaneous sessions present shared current state without leaking unrelated private context?
- How does voice preserve corrections and task state without becoming a separate identity/runtime?
- Is any part of the historical Stage 3 graphical `vera-ui` worth retaining as a prototype/reference rather than rebuilding UI assumptions from scratch?

## Security and governance

- Which operations always require Patrick approval?
- What technical mechanism represents approval?
- What is the recovery path if Vera OS loses access to its governance/state stores?
- How are system updates signed, reviewed, deployed, and rolled back?
- Which logs are necessary, and what must never be logged?
- Which historical systemd hardening/broker boundaries remain valid under the current governance contract?
- What current cryptographic/key-management design should replace the historically unresolved Stage 5 vault proposal?

## Historical artifact recovery

A deep File Library pass has recovered **two major old OS implementation lines** in addition to the original Stage 1 prototype, plus a detailed Stage 5 specification:

- Debian `live-build` VERA Linux Stage 3 / Stage 4 source work under `~/vera-stage3/VERA_Linux_Stage3_Source`;
- later Buildroot/ISO-B work under `/home/vera/vera-ws06`;
- historical Stage 5 planning for persistent identity, relationship vault, Side Chats, cross-chat coordination, continuity packages, memory ownership, administrator recovery, import/export, and full reset.

The Stage 3 line is contemporaneously recorded as having reached a booting ISO with Vera autologin, graphical session, diagnostics, status UI, typed privileged broker, and an honest null/offline cognition adapter. Stage 4 then began wiring an Ollama-backed local cognition service but was explicitly not yet verified as a built/booted Stage 4 ISO at the recovered checkpoint.

The Stage 5 search currently finds a **specification frontier, not implementation evidence**. The detailed requirements recur in July and later historical exports, but the current recovery has not found a Stage 5 source tree, built ISO, verified vault implementation, working multiple-Side-Chat runtime, continuity-package execution, administrator-recovery implementation, or full-reset test. Treat this negative search result as a bounded recovery state, not proof those artifacts never existed.

Open recovery targets:

- `vera_os_core_stage1.zip` exact bytes;
- exact archive/tree for `~/vera-stage3/VERA_Linux_Stage3_Source`;
- exact VERA Stage 3 `.iso` filename, bytes, size, and SHA-256;
- raw Stage 3 boot/VirtualBox acceptance evidence behind the contemporaneous `ISO boots` record;
- Debian `live-build` `auto/`, hooks, includes, package lists, scripts, Makefile, manifests, and checksums;
- exact Stage 4 checkpoint/archive if preserved separately;
- evidence of any successful Stage 4 ISO build or boot after the recovered architecture checkpoint;
- exact Stage 4 `vera-cognition`, `vera-ui`, `runtime.py`, `vera-broker`, service units, system prompt, and cognition configuration bytes;
- source/config tree corresponding to `/home/vera/vera-ws06`;
- any exact ISO-B `.iso`, disk image, or boot image artifact;
- Buildroot defconfig and kernel config;
- `board/vera/x86_64/` contents;
- Buildroot build and QEMU scripts;
- package manifests and checksums;
- VeraCore, memory, VSNS, supervisor, diagnostics source;
- local-model packaging assets;
- later QEMU test evidence, especially whether the observed two-boot persistence failure was subsequently fixed;
- any physical-install, USB-boot, VirtualBox, or dual-boot evidence;
- any exact Stage 5 implementation artifacts corresponding to `vera-memory`, `vera-coordinator`, Side Chat persistence, relationship vault, continuity packages, administrator recovery, import/export, or reset testing;
- the Phase 3/4 panel ZIPs and later ISO-build packages referenced by historical collaboration records.

Missing bytes must remain missing; do not recreate them from prose/logs and then mislabel the reconstruction as recovered source.

## Development process

- Should this repository use a standing development branch and Patrick-approved PR workflow?
- What qualifies an architecture document as accepted versus exploratory?
- What automated tests can validate authority boundaries and recovery semantics before real model integration?
- Which exact Buildroot/QEMU qualification sequence should become the required executable gate before hardware tests?
- Which historical Stage 3/4, Stage 5 specification tests, and Buildroot tests should be ported as regression tests independent of the base distribution?
- Which historical source should be imported verbatim if exact bytes are recovered, versus reimplemented under current contracts with provenance back to the old design?

## Immediate next decision

The immediate executable frontier is now mechanically defined rather than architectural:

1. resolve the Buildroot `veraos_x86_64_defconfig` against exact Buildroot 2024.02.4;
2. build the Linux 6.6.69 kernel and VeraOS root filesystem;
3. boot QEMU directly into `/sbin/vera-init` as PID 1;
4. observe the exact `VERAOS_BOOT_READY_V1` marker after portfolio/authority validation;
5. prove restart and durable-state handling without a cognition provider;
6. build `veraos_x86_64_browser_defconfig`, then qualify WPE WebKit/Cog packaging and runtime separately;
7. then bind the resident Vera Mono/Rezon/Pre-Active/Volition/P.O.R.T.A.L. runtime and independently scoped workers.

The UI is still not the first proof. The first proof is that the image boots as VeraOS, remains honest when cognition is absent, and preserves the current authority/composition contracts without depending on a conventional distro init layer.
