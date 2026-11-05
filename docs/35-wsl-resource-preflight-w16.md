# W16: read-only WSL2 resource-control preflight and host evidence

**Authority:** VeraOS accepted `main` `31b66b6ff317eb981c4bd8fcc4ae6e5db1d21adf` remains separate. This increment is based on Draft PR #74 head `7aa1bf00be53e8b5f3b266739383a132e79414f4` and is not a production release, permission change, service or launcher admission.

## Source behavior

`src/veraos/worker_resource_preflight.py` reads only own process `mountinfo` and cgroup membership, the visible cgroup-v2 controller lists, and the system-owned bubblewrap lookup. It prints machine-readable evidence with **both `dev_worker_launch` and `production_resource_control` fixed to `HOLD`**. It does not create a cgroup, enter a namespace, install packages, execute bubblewrap, or change host configuration. Synthetic booleans about tool custody/delegation are never an authorization claim.

Controller lists and writable checks are scoped to the current process's cgroup rather than treating root-controller availability as delegation to the worker. This remains a read-only heuristic; authoritative delegation needs real scoped write/denial testing under controlled host custody.

The CLI exits **2** even when all observations were collected successfully, because a completed preflight must not be mistaken by shell automation for a qualified launch grant.

The resource controls needed for a future live worker include bounded aggregate CPU, memory, processes and I/O. Presence of controller names or a writable-looking cgroup path is not proof of delegated limits. A short process timeout alone does not cap fork, memory or I/O exhaustion. The existing `worker_isolation_runner.run_disposable_dev_worker` deliberately still refuses to spawn any live child.

`worker_isolation_audit.py` now detects the `fuse.wsl` host-share filesystem type as well as `9p` and `drvfs`; the classifier remains an always-HOLD observation.

## Lappy host observation (2026-11-05)

An authorized read-only probe on Lappy observed Ubuntu-26.04 under WSL2, Linux user `vera` UID 1000, kernel `6.18.33.2-microsoft-standard-WSL2`, Python 3.14.4, `/home/vera` on ext4, and bubblewrap 0.11.1 present. `CapEff=0`, `NoNewPrivs=0`, `Seccomp=0`. Windows `9p` mounts `/mnt/c`, `/mnt/d`, and `/usr/lib/wsl/drivers` were visible; `cmd.exe` and `powershell.exe` paths were executable by access check. Windows free RAM was approximately 7.86 GiB with CPU ~20% when checked. These are observations at that instant, not future conditions.

One unprivileged, five-second-bounded bubblewrap diagnostic child was attempted using minimal read-only `/usr` mount bindings. It exited **1** in approximately 0.41 seconds with `bwrap: execvp /usr/bin/bash: No such file or directory`. The missing dynamic runtime path is a **test harness failure**, not proof that a Windows mount was denied, a namespace was successfully isolated or the host refused privileges. No retry or escalation was made.

A subsequent read-only cgroup probe (exit **0**, 0.37 seconds) established `/proc/self/cgroup` = `0::/init.scope`, a cgroup-v2 mount at `/sys/fs/cgroup`, available root controllers `cpuset cpu io memory hugetlb pids rdma`, and no enabled controllers in the caller's own `init.scope`. The mount itself was generally marked writable, but `/sys/fs/cgroup` and `init.scope` were root-owned. Ordinary UID 1000 could read controller metadata yet **could not write** the root `cgroup.subtree_control`, its own `cgroup.procs`, or its own cgroup directory (`test -w` exit **1** for each). The required writable delegated budget controller therefore was **not observed**. No cgroup creation or writes occurred.

On the original Draft #74 head, an independent fresh Lappy WSL2 **HOST_TEST** run in disposable ext4 checkout completed 20 worker-isolation source tests, five WSL two-worker integration tests, and ten real AF_UNIX socket IPC tests, all exit 0. The broad source suite in the constrained Linux scratch sandbox suffered seven AF_UNIX `EPERM` failures and must not be described as a broad pass. Those seven socket tests did pass on real WSL2.

## Release decision

> **HOLD.** Same-UID development workers can still access host-shared mounts and state. No trusted Windows SID/logon issuer, independent worker UID/namespace/ACL denial, cgroup resource controller, authenticated recovery witness or protected-effect broker is qualified. Source preflight and tests must not flip any authority gate.

Next: a deliberately disposable, resource-bounded, negatively tested worker under an approved host custody model, followed by distinct-principal raw SQLite/WAL/SHM and Windows mount denial. Host identity, account/ACL or service changes require Patrick's separate authority.
