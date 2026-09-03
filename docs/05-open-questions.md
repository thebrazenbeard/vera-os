# Open Questions

This file tracks unresolved architecture decisions. Items should be promoted to decisions only after explicit review/validation.

## Base operating system

- Is NixOS the confirmed base, or should it first be compared against Debian/Ubuntu/Fedora/immutable alternatives?
- Which NixOS channel/flakes policy should Vera OS use?
- Should Vera OS eventually ship as an installer/image, or remain a reproducible configuration layered onto stock NixOS?
- Should the historical Buildroot lineage remain only prior art, or should Buildroot retain a role for recovery/test/appliance images?

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

## Vera runtime

- What is the minimal viable `verad`?
- Which state is authoritative and which is cache/derived state?
- What event/receipt model is required for recovery?
- How are currentness and conflicting state handled after restart?
- How does a session authenticate and obtain scoped access to Vera state?
- How are long-running tasks resumed safely?

## Memory

- Which memory classes require relational/document databases versus files/Git?
- What is the local replacement or continuation path for current Supabase-backed systems?
- How are memory admission, correction, supersession, deletion, privacy, and readback represented?
- Should embeddings/indexes be treated as rebuildable derived data?
- Which concepts/code from the historical `vera-ws06` memory implementation remain useful after comparison against current R9B0 semantics?

## Workers and orchestration

- Is worker isolation best implemented with systemd dynamic users, containers, namespaces, microVMs, or a tiered combination?
- How are clean-context workers created?
- How do workers exchange results without acquiring each other's authority?
- How are concurrent repository writers prevented from colliding?
- How are worker outputs verified before Vera relies on them?
- What is the durable task-graph representation that lets workers outlive any individual conversation/interface session?

## Tools

- What is the internal tool protocol?
- Should MCP be supported directly, wrapped behind a Vera-specific broker, or treated as one adapter among several?
- How are shell commands classified by risk?
- Which tools are safe for autonomous invocation versus approval-gated?
- How are credentials scoped to individual tools/workers?

## Interfaces

- What is the first interface: terminal, local web UI, desktop app, voice, or a minimal API plus CLI?
- How should multiple simultaneous sessions present shared current state without leaking unrelated private context?
- How does voice preserve corrections and task state without becoming a separate identity/runtime?

## Security and governance

- Which operations always require Patrick approval?
- What technical mechanism represents approval?
- What is the recovery path if Vera OS loses access to its governance/state stores?
- How are system updates signed, reviewed, deployed, and rolled back?
- Which logs are necessary, and what must never be logged?

## Historical artifact recovery

A deep File Library pass has recovered strong evidence of the July 2026 Buildroot/ISO-B lineage, but not yet all original bytes. Continue searching for exact historical artifacts before reimplementing components that may already exist.

Open recovery targets:

- `vera_os_core_stage1.zip` exact bytes;
- source/config tree corresponding to `/home/vera/vera-ws06`;
- any actual `.iso`, disk image, or live-image artifact;
- Buildroot defconfig and kernel config;
- `board/vera/x86_64/` contents;
- build and QEMU scripts;
- package manifests and checksums;
- VeraCore, memory, VSNS, supervisor, diagnostics source;
- local-model packaging assets;
- later QEMU test evidence, especially whether the observed two-boot persistence failure was subsequently fixed;
- any physical-install, USB-boot, VirtualBox, or dual-boot evidence;
- the Phase 3/4 panel ZIPs and later ISO-build packages referenced by historical collaboration records.

Missing bytes must remain missing; do not recreate them from prose/logs and then mislabel the reconstruction as recovered source.

## Development process

- Should this repository use a standing development branch and Patrick-approved PR workflow?
- What qualifies an architecture document as accepted versus exploratory?
- What automated tests can validate authority boundaries and recovery semantics before real model integration?
- Should a VM-based NixOS prototype be the first executable milestone?
- Which historical Buildroot tests should be ported as regression tests independent of the base distribution?

## Immediate next decision

The next high-value decision is probably not the UI. It is to define the **minimal executable Vera runtime** and target hardware, then prove a NixOS host can declaratively start:

1. a local inference server;
2. a minimal `verad` coordinator;
3. durable local state;
4. multiple independently scoped workers, with at least one able to run concurrently with another;
5. one real tool path (likely Git/shell) through an explicit capability boundary;
6. a CLI session that can detach/reconnect without owning the workspace lifecycle;
7. task/workspace state that survives a runtime restart by explicit state recovery.

That proof would test the architecture without prematurely building a complete distribution or graphical shell. Historical Vera OS tests should be reused where their semantics still apply, but the new milestone must prove the multi-agent workspace rather than merely reproducing a bootable single-loop VeraCore image.