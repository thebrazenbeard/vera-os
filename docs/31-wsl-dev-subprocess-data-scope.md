# WSL data-scoped subprocess experiment — DEV ONLY, not worker sandbox

Base source: VeraOS Draft PR #74 `048da7c59d72dbbbe718b48d1bda91460e0fda8b`.
This optional implementation is an isolated source/testing proposal; it is
neither accepted `main` nor a host-installed service.

## What it actually does

`Pilot.run_dev_process(task_id)` or `dev-run-process` preserves the normal
SQLite claim, cancel, output-intent, durable event, and recovery-hold rules.
Instead of executing the entire inspect/digest calculation in the coordinator
interpreter, it starts a fixed separate Python child process for each task:

- Interpreter and child script are absolute, with `-I -B` isolation flags.
- No shell, no user-selected executable, no task ID, path, DB handle, network
  socket or filesystem descriptor is explicitly passed to the child.
- The child inherits an empty caller-supplied environment (CPython may
  synthesize `LC_CTYPE` for locale coercion), gets a fresh private native
  Linux working directory, and receives only a bounded stdin payload.
- Inspect receives a validated *byte count* only. Digest receives at most
  8192 bytes of already validated fixture content through stdin. The parent
  interprets a strictly bounded JSON result, checks exact fields and records
  a `DEV_SUBPROCESS_OBSERVED` receipt before any derived-file output intent.
- A timeout, invalid output, or a nonzero child exit causes a safe
  `RECOVERY_HELD` task and no digest output. The previous in-process `run`
  API/CLI remains unchanged for compatibility.

The child has no direct *provided* write capability; any digest sidecar is
created only by the parent through the existing output-intent path. A crash
after the claim remains a manual-reconciliation HOLD and never auto-replays.

## The decisive hostile objection

> **This is not a security boundary.** Both processes run under the same
> Linux UID, so the child may be able to open other same-user files, inspect
> the parent through `/proc`, access WSL's Windows mounts, or use ambient
> network capabilities despite a sanitized environment and narrow stdin.
> Python `-I` limits interpreter import/environment behavior; it does not
> install seccomp, namespaces, per-worker OS accounts, ACLs or an effect
> broker. A same-UID compromised child might bypass the intended data handoff.

Therefore neither this result nor its receipt may be advertised as
independently protected worker isolation or authenticated authority. The
production gate requires a reviewed OS-enforced worker principal/container/
namespace, separately scoped filesystem/network permissions and a host-owned
effect broker. The current project does not authorize changing Lappy user
accounts, ACLs, service startup, or other host configuration for this test.

## Evidence and stop

- SOURCE: `src/veraos/wsl_worker_child.py` has only fixed inspect/digest
  behavior, bounded stdin, and bounded JSON results.
- TEST: `tests/test_wsl_process_worker_boundary.py` verifies real child
  PIDs differ, scoped input behavior, scrubbed environment key names,
  no inspect output file, digest result and failure quarantine. Real
  unprivileged WSL CLI execution must be independently tested before calling
  that specific host behavior verified.
- UNKNOWN: true privilege isolation, adversarial same-UID denial, Windows
  path protection, model inference, native host restart, and protected effects.

No model load, firewall/listener/service installation, credential change,
system package install, billable resource, merge or production deployment
is authorized or performed by this source contract.
