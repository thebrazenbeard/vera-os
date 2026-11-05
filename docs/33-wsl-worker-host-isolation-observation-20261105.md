# WSL dev worker host exposure: read-only evidence and release HOLD

**Source base:** VeraOS Draft #74 `a2645c4d0962a472807021ad306ac4faf7818cb1`.
Accepted `main` remains a different authority. This is a source/test
instrument and an operator probe, not an installed worker sandbox.

## Lappy read-only process observation (2026-11-05 09:27:52 UTC)

An authorized, no-write `wsl.exe -d Ubuntu-26.04 --exec bash -lc` probe on
Lappy observed Linux UID/GID 1000, WSL kernel
`6.18.33.2-microsoft-standard-WSL2`, and:

| Real Linux/process observation | Result |
| --- | --- |
| Effective capabilities | `CapEff=0` |
| No-new-privileges and seccomp | `NoNewPrivs=0`, `Seccomp=0` |
| Shared Windows-related mounts | Three `9p` mount entries; zero `drvfs` |
| WSL interop | Environment present; `/run/WSL` traversable |
| Windows binaries under `/mnt/c` | Ordinary `cmd.exe` and `powershell.exe` executable by access check |
| Windows `/mnt/d` | Directory visible |

A separate `env -i /usr/bin/python3 -I -B -c ...` **read-only child** under
the same UID retained the parent's mount namespace
(`mnt:[4026532566]`) and executable visibility of `cmd.exe`, despite
having no `WSL_INTEROP` environment variable. It still reported
`CapEff=0`, `NoNewPrivs=0`. No Windows executable was launched, no
cross-UID access was attempted, and no user or host settings were changed.
Before the probe Windows memory was roughly 3,962 MB free of 32,491 MB;
no GPU or model workload was initiated.

**Evidence level: REAL_SYSTEM_PROBE for these precise read-only process
observations, not a kernel-denial test of `wsl_worker_child.py`.** The child
used the same `env -i` and `-I -B` controls as the developer launcher,
but not the exact runtime child entrypoint. Source review shows
`wsl_pilot._run_data_scoped_child` does not change UID, mount namespace,
seccomp, `NoNewPrivs`, or ambient process network privilege. The distinct
PIDs and empty environment established in Wave 10 prove subprocess/data
separation only.

> **Hostile result:** Sanitizing `env` and Python import paths did not
> remove Windows-host executable access or shared mounts. Even without
> executing a Windows program, the exposed executable path and inherited
> Linux mount namespace falsify any claim that the current WSL development
> worker is independently confined from Windows resources.

## Source-only reproducible inventory

`src/veraos/worker_isolation_audit.py` observes the caller's procfs
credentials, mount type counts and read-only accessibility indicators;
`tests/test_worker_isolation_audit.py` checks forged clean-looking
snapshots, unsafe WSL-like snapshots, malformed evidence and an isolated
Python child. The report **always says `production_worker_isolation=HOLD`**.
The names in `reasons` are diagnostics, not approvals, identity facts or
consent grants. The probe does not open privileged files, create processes
other than a benign Python test child, or read arbitrary private contents.

In the scratch test container the parent mount namespace metadata may be
unreadable under `/proc/1`: that yields a reported
`kernel_evidence_incomplete` HOLD, not an assertion that isolation passed.

## Linux VM / native Linux comparison (INFERENCE, not qualified alternatives)

- **Current Lappy WSL2:** useful for safe foreground development and API
  compatibility tests. Actual observed Windows mounts and executable paths
  disqualify the current worker from protected effects and private-memory
  isolation. `systemd` inside WSL would not prove Windows boot-time service
  ownership.
- **Conventional Linux VM:** can potentially omit host shared folders and
  Windows executable interop, and use different guest UIDs/mount namespaces.
  This remains conditional on exact VM configuration, separate guest state,
  hypervisor permissions and negative syscall/ACL tests.
- **Native Linux:** may simplify a Linux-only authority boundary without WSL
  interop; it still needs distinct principals, a protected broker, state
  custody, revocation and real denial tests. Windows owner authentication
  remains an independent bridge problem if Windows clients are supported.

**Next gate:** On a disposable approved host, exercise real different worker,
state-owner and broker UIDs; verify denial of raw SQLite/WAL/SHM access and
Windows mounts/interop under actual namespaces, and verify broker effects
remain denied. This may require account/ACL/namespace provisioning and
therefore fresh Patrick authorization. Until then, WSL2 stays a development
surface and the release gate stays closed. No attempt was made to bypass the
permission boundary.
