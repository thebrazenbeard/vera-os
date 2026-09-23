> **License:** Source-visible, not open source. Original material is proprietary. Commercial use, redistribution, hosted-service use, and commercial derivative products require written permission. See [LICENSE](LICENSE) and [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md). Separately identified third-party components retain their own licenses.

# vera-os

Vera OS is a working architecture for a local, persistent, agentic Vera runtime built on Linux rather than around a single chat application.

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

## Status

This repository is in **architecture discovery**. Documents record the current working model and should not be read as proof that any component has been implemented, installed, deployed, or validated.
