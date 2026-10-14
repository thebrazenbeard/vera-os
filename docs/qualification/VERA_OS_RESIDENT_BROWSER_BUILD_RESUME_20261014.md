# VeraOS resident-browser build continuation — 2026-10-14

Status: **isolated Docker Buildroot compilation running at last observed readback; kernel/rootfs incomplete and unqualified.** This is source-controlled recovery evidence, not an assertion of future liveness or an operating-system installation.

## Exact inputs and protected scope

- Source checkout: `D:\VeraOS\vm\resident-python312-probe-20261012`, tracked files clean at `34825be36f0ac5a2d9014c704e51d6048e9a78bd` (VeraOS Draft PR #12). The checkout still contains untracked Python `__pycache__` directories; do **not** claim full worktree cleanliness or run indiscriminate `git clean`.
- Buildroot source: existing Docker volume `veraos-resident-browser-python312-20261012`, verified by read-only in-volume `git rev-parse HEAD` as `d030e36bbc9669230c015be971b14b6e062cfdde` (Buildroot 2025.02.18).
- Builder image: `veraos-buildroot-builder:2025.02.18`, locally observed SHA-256 image ID `5810b2dc524a6077568955290a9ab9fbfdb7602cd841f67e0d5c91f6a493a11c`.
- Read-only resident stage: `D:\VeraOS\vm\resident-core-source-stage-20261012`. The stage verifier **ran** and returned `PINNED_SOURCE_FILES_VERIFIED_NOT_INSTALLED`, receipt SHA-256 `5d94e38fe243e5ec933c5616c3aa9d720bb0bbd57104de74cf6ca37eb6938b57`: Vera Mono 314, P.O.R.T.A.L. 88, Pre-Active 18, Volition 8 source files (428 total). No resident import/activation is implied.
- Artifact directory: `D:\VeraOS\vm\resident-browser-artifacts-20261012`. Before restart, only `veraos-buildroot-build.sh` was present, SHA-256 `07622b04b225a206d24972ac7b160cf6e7f6ea8fdfffd19f914a3b02309ec138`. No kernel/rootfs result was admitted.

## Bounded repair before restart

The 2026-10-13 memory-guard job ended with Docker `error waiting for container: unexpected EOF`. On 2026-10-14 no VeraOS builder was running; the existing cache contained exactly **one zero-length WebKit object**:

`/work/output/build/wpewebkit-2.50.5/Source/WebCore/CMakeFiles/WebCore.dir/__/__/WebCore/DerivedSources/unified-sources/UnifiedSource-3a52ce78-74.cpp.o`

The read-only scan also found intentional zero-byte glibc `stamp.o` files; these were untouched. A no-overwrite repair script at `D:\VeraOS\vm\resident-browser-build-logs-20261014\repair-zero-byte-webkit-object-20261014.sh` (SHA-256 `c4da552247d4eb366b3b55f09fc093ef45dc3a6344d561b810aaea7003e8bcdf`) checked the Buildroot exact commit, required that the WebKit tree have exactly one zero-size `*.o`, removed only that exact file, and verified its absence. Output: `ZERO_BYTE_WEBKIT_REPAIR_VERIFIED`. No other cache, physical volume, OS partition, or unrelated process was changed.

## Restarted container and readback

One persistent-inspectable detached Docker container was started, **without creating another build volume**:

- Name: `veraos-resident-browser-memoryguard-20261014`
- Full ID: `bc19a7785d730de47b0178163d91b4a2d7f0e99d01332167ef4ff71e58e331ac`
- Options: `--user 1000:1000 --memory 4g --memory-swap 8g --cpus 2`; `VERAOS_JOBS=1`; `HOME=/home/vera-build`; `VERAOS_REQUIRE_RESIDENT_CORE=1`; `VERAOS_RESIDENT_STAGE=/resident`; `VERAOS_DEFCONFIG=veraos_x86_64_resident_browser_defconfig`; the exact Buildroot version/commit above.
- Mounts: source checkout read-only `/workspace`; resident stage read-only `/resident`; existing artifact directory writable `/artifacts`; existing Buildroot volume writable `/work`.
- Entrypoint: `/bin/sh /artifacts/veraos-buildroot-build.sh`.
- **Fresh readback at 2026-10-14 16:46:25 EDT:** Docker `STATE=running`, `OOM=false`, CPU ~99.97%, 1.762 GiB / 4 GiB cgroup memory. WebKit log progressed to `[3/4171]` building `UnifiedSource-3a52ce78-74.cpp.o` (the repaired object). This snapshot is not a guarantee that build will finish.

Use `docker inspect veraos-resident-browser-memoryguard-20261014 --format '{{.State.Status}} {{.State.ExitCode}} {{.State.OOMKilled}}'`, `docker logs --tail 30 veraos-resident-browser-memoryguard-20261014`, and `docker stats --no-stream veraos-resident-browser-memoryguard-20261014` for fresh state. Do **not** start another builder sharing the volume. Preserve container exit status for postmortem instead of blindly retrying.

The focused tests at **local, older PR #15 checkout** `056d9546afc0f5088864025b8129b730839b840e` were 12 passed, 1 warning for `tests/test_resident_all_file_audit.py` and `tests/test_resident_qualification_contract.py`; this does **not** qualify the current GitHub PR #15 head `8f37e696aa1b41ab5ae3476ac0d8897edd2954d0` or guest runtime behavior.

## Required next executable checks

1. Fresh-read container status/log progression and host pressure. A stopped container with nonzero exit or OOM is a **HOLD**, not a successful compilation. Check exact failure and cache state before any further restart.
2. Only after Docker exits **0**, require `veraos-bzImage`, `veraos-bzImage.sha256`, `veraos-rootfs.ext2`, and `veraos-rootfs.ext2.sha256`. Compare builder manifests against host rehashes before accepting a build receipt. Inspect generated `__pycache__` entries individually if the source clean-tree gate rejects them; never broad-clean unknown files.
3. Follow `VERA_OS_RESIDENT_BROWSER_RELEASE_CHECKLIST_20261012.md`: apply the reviewed completion helper against the original PR #12 source; run both image audits including all 428 guest-source file hashes; then perform two disposable, offline QEMU guest boots. Read back exact output receipts and record failures.
4. Separate later guest import, P.O.R.T.A.L. routing, local model, Cog/graphical render, branding, and offline ext4 data mount qualification. Source staged ≠ runtime working; VM boots ≠ hardware install.

Protected boundary unchanged: **no Windows/native disk/EFI edits, no 300.39 GiB reserved partition changes, no main merge, no credentials/trust edits, no publication of private staged sources or derived images**. This is a recoverable VM build task, not deployment authority.
