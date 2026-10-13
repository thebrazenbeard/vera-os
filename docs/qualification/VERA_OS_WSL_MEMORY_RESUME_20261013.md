# VeraOS resident-browser WSL memory recovery (2026-10-13)

Status: **observed, protected isolated build resumed; image incomplete.** This is an engineering continuation record for the existing `RESIDENT_BROWSER` Docker Buildroot candidate, not an OS installation or a runtime qualification.

## Diagnosed interruption

At 2026-10-12 21:33 EDT, the prior serial Buildroot job was compiling WPE WebKit 2.50.5 (Ninja 4099/8301) when Docker returned `error waiting for container: unexpected EOF`.

Windows readback distinguished this from a compiler failure:

- System Resource-Exhaustion-Detector **Event 2004** at 21:33:23: low committed/virtual-memory condition; WSL accounted for ~15.1 billion bytes, competing with other workstation applications.
- Application Error **Event 1000** at 21:33:39: `wslservice.exe` crash with exception `0xc00000fd`.
- Service Control Manager **Event 7034** at 21:33:41: WSL Service terminated unexpectedly.
- No final kernel, rootfs or builder receipt existed after the interruption.
- A read-only examination of the saved Buildroot volume found **one** zero-byte WebKit `.o` file.

This is separate from the *earlier* October 12 16:31 clean Windows restart, also responsible for a previous Docker EOF.

## Reproducible local repair

The operator's user-local `%USERPROFILE%\.wslconfig` did not exist, so a no-overwrite file was created with exact contents:

```ini
[wsl2]
memory=6GB
swap=8GB

[experimental]
autoMemoryReclaim=gradual
```

SHA-256: `fb6cbc519718f5be8344d68e72a56415cd65085f1cd0f833d8a1b808d34a2a5e`.

At the time there were no active Docker containers and only Docker Desktop's WSL distro had been running. The Docker Desktop engine was stopped, WSL cleanly shut down to apply the resource limit, and Docker Desktop restarted; neither Windows nor the bare-metal disks were rebooted/modified. From a bounded Docker probe, observed `MemTotal: 6066812 kB` and `/proc/swaps: /dev/sdc partition 8388608 KiB`.

One and only one zero-byte WebKit object was removed inside the original build volume, and its absence was verified. The exact no-overwrite local repair script is `D:\VeraOS\vm\resident-browser-build-logs-20261013\repair-zero-byte-webkit-object.sh`, SHA-256 `def441581594ec8559a81b02954b718db3a4092ecc14c1d46a23c0ee0e389ae2`. This intentionally did **not** delete object trees, snapshots or the cache.

## Current isolated build

- Source: `D:\VeraOS\vm\resident-python312-probe-20261012` at exact tracked-clean `34825be36f0ac5a2d9014c704e51d6048e9a78bd`, original Draft PR #12. Untracked Python cache folders do not make source bytes current and must be reconciled before exact-clean completion qualification.
- Buildroot: Docker volume `veraos-resident-browser-python312-20261012`, source exact `d030e36bbc9669230c015be971b14b6e062cfdde`, Buildroot 2025.02.18, persistent previous objects intact.
- Resident source stage: `D:\VeraOS\vm\resident-core-source-stage-20261012`, SHA-256 receipt `5d94e38fe243e5ec933c5616c3aa9d720bb0bbd57104de74cf6ca37eb6938b57` (428 exact-source files across Vera Mono, P.O.R.T.A.L., Pre-Active and Volition, older pinned heads).
- Active Docker name at 15:55 EDT: `veraos-resident-browser-memoryguard-20261013`, UID 1000, `VERAOS_JOBS=1`, `--memory=4g --memory-swap=8g --cpus=2`; `memory-swappiness` preference was ignored by WSL's kernel, not a fatal build error.
- At 15:55 EDT, container CPU ~99%, 3.516 GiB / 4 GiB cgroup memory, `OOMKilled=false`, compiling WebKit `Generate bindings (WebCoreBindings)` at Ninja 2/4388 remaining steps. This is one observation, not a guarantee of future liveness.
- Current logs: `D:\VeraOS\vm\resident-browser-build-logs-20261013\build-resume-memory-guard-20261013.stdout.log` and `.stderr.log`.
- Output (not yet present): `D:\VeraOS\vm\resident-browser-artifacts-20261012\veraos-bzImage`, `veraos-rootfs.ext2` and verified completion receipt.
- The existing hourly VeraOS Resident Build Watch was re-enabled after the live container was verified.

## Verification next and limitations

When and **only when** the exact Docker job exits successfully, first compare produced image SHA-256 sidecars, original PR #12 source and build stage pins. Use current Draft PR #15 completion and image-audit scripts for a no-clobber result, actual rootfs byte-level examination of all 428 stage files, and two independent disposable QEMU boots with network disabled. Source packages in the guest do **not** establish runnable `vera_core.QualifiedVeraRuntime`, a selected P.O.R.T.A.L. route, Cog/GUI rendering, a local model, offline ext4 portfolio guest mount, or deployment.

> **HOSTILE REVIEWER:** The 4 GiB Docker memory cap may avoid a host-wide WSL crash but cause WebKit OOM or swap thrashing instead.

**Accepted.** Preserve the prior cache and observe actual cgroup/OS and terminal build evidence. Do not silently raise global memory configuration, kill unrelated programs, spin up another compiler, or claim a complete OS.

**Authority boundary:** no physical disk partitioning, native installation, bootloader changes, main branch merge, credential/trust/provider changes or publication of private resident binaries/images. The reserved 300.39 GiB unallocated Disk 1 space, existing Windows install and prior qualified VeraOS images remain untouched.
