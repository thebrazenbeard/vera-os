# VeraOS Resident Browser — Exact Build and Qualification Checklist (2026-10-12)

Scope: an **isolated Buildroot virtual-machine image**, not a physical-disk install, not production activation, and not proof that Vera's services or graphical browser actually run. All paths below are on Lappy. The source-built kernel/rootfs under test are from VeraOS Draft PR #12 at `34825be36f0ac5a2d9014c704e51d6048e9a78bd`, even though the **new qualification scripts** are in Draft PR #15. Do not confuse the two distinct source heads.

## 1. Preserve the active compilation

Use an actual Docker/live-process and log progression check before starting any second attempt:

```powershell
docker ps --format '{{.Names}} {{.Status}}'
Get-Content 'D:\VeraOS\vm\resident-browser-build-logs-20261012\build-resume-docker-recovery-20261012.stdout.log' -Tail 12
Get-Content 'D:\VeraOS\vm\resident-browser-build-logs-20261012\build-resume-docker-recovery-20261012.stderr.log' -Tail 8
```

Expected currently active container: `veraos-resident-browser-recovery-20261012`. Source: `D:\VeraOS\vm\resident-python312-probe-20261012`; stage: `D:\VeraOS\vm\resident-core-source-stage-20261012`; Buildroot Docker volume: `veraos-resident-browser-python312-20261012`, exact Buildroot head `d030e36bbc9669230c015be971b14b6e062cfdde`. Buildroot image: `veraos-buildroot-builder:2025.02.18`. Do not modify that volume while building; maintain one job.

**Historical interruption clarified:** At 2026-10-12 16:31:16 EDT, Windows User32 event 1074 recorded StartMenuExperienceHost.exe initiating a host restart. EventLog ID 6006 and Kernel-General ID 12 verify a clean shutdown/reboot at 16:31:39. The earlier Docker `unexpected EOF` happened because Windows restarted. Preventing another reboot during compilation is the immediate operational protection; compiler flags and package patches won't fix that event.

## 2. Only after the actual build exits successfully

Require both of these normal builder-produced output files **plus their SHA-256 manifests** under `D:\VeraOS\vm\resident-browser-artifacts-20261012`:

`veraos-bzImage`, `veraos-bzImage.sha256`, `veraos-rootfs.ext2`, `veraos-rootfs.ext2.sha256`.

Use the **PR #15** completion helper against the **PR #12 source checkout** (not against its own PR #15 checkout). Fail on dirty source, stage drift, an active build, a SHA mismatch or an existing result:

```powershell
& 'D:\VeraOS\vm\resident-completion-candidate-20261012\tools\vm\Finalize-VeraOSResidentBuild.ps1' `
  -RepoRoot 'D:\VeraOS\vm\resident-python312-probe-20261012' `
  -ArtifactRoot 'D:\VeraOS\vm\resident-browser-artifacts-20261012' `
  -ResidentSourceStage 'D:\VeraOS\vm\resident-core-source-stage-20261012' `
  -BuildVolume 'veraos-resident-browser-python312-20261012' `
  -ExpectedSourceHead '34825be36f0ac5a2d9014c704e51d6048e9a78bd'
```

This creates a build result with an exclusive-create operation. It does not attest to OS boot or resident-service behavior.

## 3. Check actual guest filesystem contents

Use WSL2 Linux `debugfs` read-only; **never** mount or alter a physical disk. First run the existing PR12 static audit:

```powershell
wsl.exe -d Ubuntu-26.04 -- python3 /mnt/d/VeraOS/vm/resident-python312-probe-20261012/tools/vm/Audit-VeraOSImage.py `
  --ext2 /mnt/d/VeraOS/vm/resident-browser-artifacts-20261012/veraos-rootfs.ext2 `
  --repo-root /mnt/d/VeraOS/vm/resident-python312-probe-20261012
```

Then use the PR15 **all-file** auditor. It requires the byte-identical embedded source receipt and compares **all 428 staged files** (314 Vera Mono, 88 P.O.R.T.A.L., 18 Pre-Active, 8 Volition) inside the image against the separately verified local source stage.

```powershell
wsl.exe -d Ubuntu-26.04 -- python3 /mnt/d/VeraOS/vm/resident-completion-candidate-20261012/tools/vm/Verify-VeraOSResidentFiles.py `
  --ext2 /mnt/d/VeraOS/vm/resident-browser-artifacts-20261012/veraos-rootfs.ext2 `
  --stage /mnt/d/VeraOS/vm/resident-core-source-stage-20261012 `
  --repo-root /mnt/d/VeraOS/vm/resident-python312-probe-20261012
```

Both are static source-byte checks, not Python module import/behavior checks. No receipt should be called successful until their exact output is read back.

## 4. Two isolated guest boots

Only after the completion and image audits pass, use the **PR15** VM qualifier with `-RepoRoot` pointing to the original **PR12** source. Its QEMU overlay is disposable and separate from the rootfs. Guest networking is disabled. Keep memory modest given observed Lappy RAM pressure:

```powershell
& 'D:\VeraOS\vm\resident-completion-candidate-20261012\tools\vm\Test-VeraOSVm.ps1' `
  -RepoRoot 'D:\VeraOS\vm\resident-python312-probe-20261012' `
  -ArtifactRoot 'D:\VeraOS\vm\resident-browser-artifacts-20261012' `
  -LogRoot 'D:\VeraOS\vm\resident-browser-qualification-logs-20261012' `
  -MemoryMiB 4096 -CpuCount 2 -TimeoutSeconds 360
```

Require observed `VERAOS_BOOT_READY_V1` and lifecycle persistence markers on **both** boots and read back `veraos-vm-qualification.json`. Any missing markers, nonzero compiler exit or mismatch is a HOLD; do not claim two boots from a launch attempt.

## 5. Later, separate runtime and UX qualification

Static package/source success and two PID1 boots **do not** show that `vera_core.QualifiedVeraRuntime` was instantiated, that P.O.R.T.A.L. routes requests, that Pre-Active/Volition run continuously, or that local model weights were selected. Those demand separate guest import/service/model tests. Nor does WPE/Cog inclusion imply that a desktop/browser rendered.

Private offline portfolio source: `D:\VeraOS\vm\offline-portfolio-vault-20261012`; verified 90-repository supplementary ext4 data image: `D:\VeraOS\vm\offline-portfolio-images-20261012\VeraOS-Offline-Portfolio-20261012.ext4`. That image has independently passed Linux read-only mount and Git restoration on the build host, but **not** been guest-mounted. Local Vera wallpaper/launcher assets are staged at `D:\VeraOS\vm\local-branding-stage-20261012`, receipt SHA-256 `c78383c2f32082755d26899fd07b8a138f6b56f74eeecb344fae68b860d5ec12`; these have **not** been added retrospectively to the running PR12 build.

No installation, bootloader mutation, partitions, merges or private material publication. The **300.39 GiB unallocated** on Disk 1 is reserved for a future separately authorized install after hardware, UEFI, recovery and dual-boot qualification.
