> **License:** Source-visible, not open source. Original material is proprietary. Commercial use, redistribution, hosted-service use, and commercial derivative products require written permission. See [LICENSE](LICENSE) and [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md). Separately identified third-party components retain their own licenses.

# vera-os

Vera OS is an architectural proposal for a local, persistent, agentic Vera runtime built on Linux rather than around a single chat application.

## Current direction

The central design hypothesis is:

> **Vera is the persistent governed agent/runtime. Models are replaceable cognition engines. Conversations are interfaces, not containers.**

The current base-system candidate is **NixOS**. That is not yet a locked implementation decision.

Primary goals:

- run on Patrick-controlled hardware;
- support local inference without requiring an OpenAI account or hosted model;
- keep Vera's mutable identity state, memory, permissions, task state, and project state outside model weights;
- allow Vera to route work among multiple local models and specialized workers;
- expose real filesystem, Git, shell, database, network, and service capabilities through governed tools;
- enforce important authority boundaries at the operating-system/runtime layer rather than relying only on prompts;
- allow multiple simultaneous interfaces (desktop, terminal, voice, mobile, API) to connect to the same governed Vera runtime;
- survive restarts through explicit durable state without claiming uninterrupted hidden consciousness;
- make model replacement or upgrading possible without treating a model swap as an identity replacement.

## Working repository structure

- [`docs/00-vision-and-scope.md`](docs/00-vision-and-scope.md) — problem statement and scope
- [`docs/01-reference-architecture.md`](docs/01-reference-architecture.md) — current high-level architecture
- [`docs/02-nixos-base-rationale.md`](docs/02-nixos-base-rationale.md) — why NixOS is being considered
- [`docs/03-model-and-agent-boundary.md`](docs/03-model-and-agent-boundary.md) — what belongs in models versus the Vera runtime
- [`docs/04-security-and-authority-model.md`](docs/04-security-and-authority-model.md) — OS-level governance direction
- [`docs/05-open-questions.md`](docs/05-open-questions.md) — unresolved architecture questions

## STM conversation-history integration status (2026-10-28)

The `thebrazenbeard/stm` library contains opt-in current-session memory, local SQLite historical evidence, a source-stage Windows named-pipe and Android/Linux peer-identity gateway, and the selected **day-30 review / day-45 local expiry** policy. STM source availability is **not** VeraOS runtime installation or identity-bound conversation admission.

This repository's `/api/conversation` and `/api/conversation/history` localhost endpoints are source-level conversation/task evidence interfaces, **not** user-authenticated STM producers. Browser Origin/Host, loopback and conversation IDs must never be accepted as personal-memory credentials. No automatic archive capture is authorized.

A real integration requires a host-owned authenticated caller identity, a trusted mapping to exact owner/agent/session and current consent, privileged archive access fenced from untrusted HTTP handlers, supervised retention/backup cleanup, and a separate private DeepMemoryStorage receiver with verifiable correction, deletion, consent revocation and receipt semantics. Until those are installed and tested against a live host, the bridge must fail closed. Source tests and emulator evidence cannot replace that readback.

See [STM repository](https://github.com/thebrazenbeard/stm) for source and open review changes. The 30/45 rule applies only to **new consented** archive admissions, not existing VeraOS task journals.
## Status

This repository is in **architecture discovery**. Documents record the current working model and should not be read as proof that any component has been implemented, installed, deployed, or validated.

At the source-containment baseline on `main` (`d2cb6c4`, PR #48), this tree is primarily design documents and static assets, plus a source-only editor-startup safety check. It does **not** contain a verified, deployable NixOS Vera stack, running `verad`, local model serving, durable agent state service, or authenticated multi-agent runtime. Historical Debian/Buildroot observations and unmerged experimental pull requests are separate evidence, not proof of current host readiness.

PR #48 removed a concealed VS Code folder-open task that invoked JavaScript disguised as a font. The regression check scans known dangerous source patterns without executing them; it does **not** establish whether any earlier checkout or workstation ran that file, whether installed copies are clean, or whether other threats exist. Revalidate source and boot/runtime evidence before treating any later branch as deployable.
