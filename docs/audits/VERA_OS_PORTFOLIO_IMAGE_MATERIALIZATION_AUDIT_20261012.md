# VeraOS portfolio-to-image audit — 2026-10-12

**Status: VERIFIED GAP / SOURCE-LEVEL REPAIR CANDIDATE.** This report does not claim a newly built OS, resident Vera services, a selected trained model, or a working browser UI.

## Findings from the actual browser image

Examined the 2 GiB Buildroot browser rootfs at Lappy
\`D:\VeraOS\vm\browser-artifacts-20261008\veraos-rootfs.ext2\`,
source \`446bf8e33fa729298d3540ad227e0fcd02d2a9f7\`, build date October 9. SHA-256 of this rootfs and kernel matched their Buildroot receipt; QEMU two-boot lifecycle qualification is independently recorded in \`veraos-vm-qualification.json\`. These facts do not establish resident source packaging.

Read-only \`debugfs\` examination showed:

- \`/opt/veraos/src/veraos/\` contains VeraOS-owned source modules, including \`pid1.py\`, composition and model admission contracts.
- \`/etc/veraos/architecture/\` contains the October 7 **86-repository** composition/capability/implementation catalogs.
- No Vera Mono, P.O.R.T.A.L., Pre-Active or Volition source package exists in the planned \`/opt/veraos/components/\` locations.
- \`/usr/bin/python3\` points to **Python 3.11**, but Vera Mono and P.O.R.T.A.L. \`pyproject.toml\` each require Python **>=3.12**.
- Browser packages are included in the BROWSER build profile, but WebKit/Cog runtime operation has not been demonstrated.

Ran \`tools/vm/Audit-VeraOSImage.py\` against the exact rootfs. It reported \`HOLD_INCOMPLETE_IMAGE\`, all four CORE source components absent, catalog hashes mismatched to the freshly prepared 90-repo source, and source-import readiness false. A machine-readable report was written locally next to the original artifacts:

\`D:\VeraOS\vm\browser-artifacts-20261008\veraos-image-materialization-audit-20261012.json\`

That image is **boot-qualified, not resident-stack-qualified**. \`integrated=81\` in its boot marker is a catalog disposition count, not a measurement of 81 implemented packages.

## Inventory reconciliation

An authenticated October 12 GitHub owned-repository census returned **90 repositories**; the frozen browser image lists **86**. Four missing identities were source-read, assigned exact HEADs and added consistently to the candidate composition, private capability map and implementation plan:

| Repository | Intended disposition | Boot policy |
| --- | --- | --- |
| \`vera-adapter\` | model-neutral adapter prototype; research/adapt, no independent identity root | ON_DEMAND |
| \`blotter\` | shared evidence/knowledge ledger, bounded service candidate | ON_DEMAND |
| \`RSLinux5000000\` | read-only PLC tooling, managed industrial project; never automatic plant/network access | ON_DEMAND |
| \`vera-agi\` | private research/experiment and evaluator custody; not the canonical runtime | NEVER |

Resulting candidate catalog: **90 total, 85 planned integrated/available, 5 archived excluded**. \`INTEGRATED\` in this historical schema means *considered in the private portfolio architecture*, not copied into the OS or started. The original 86 entries retain their last individual recorded source-HEAD observations; the inventory update does not falsely refresh every historical SHA.

The four rootfs-resident **source** roles are currently \`vera-mono\`, \`portal\`, \`pre-active\`, and \`volition\`. Other active repositories should be handled according to their declared roles: on-demand specialist/project, adapter, external device/node, or provenance. Baking every repository into PID 1 or booting all tools would expand attack surface, violate privacy/device boundaries and break the monorepo's self-contained-runtime principle. The trained model stays optional, and model training itself does not run in the OS by default.

## Source preparation and packaging test

A pinned Git archive stager extracts allowlisted source bytes from the exact **committed trees** of the four baseline CORE checkouts. It ignores mutable CRLF-filtered working-copy bytes, untracked files, \`.git\`, test infrastructure and model artifacts; the stage verifies every copied file against an immutable per-file hash list.

Observed Lappy stage \`D:\VeraOS\vm\resident-core-source-stage-20261012\`:

- Vera Mono: **314** source/resource files
- P.O.R.T.A.L.: **88**
- Pre-Active: **18**
- Volition: **8**
- **428** staged files total

Four exact repository HEADs match the October 7 composition snapshot. A separate readback verified staged files, hashes, source roles and receipt. This is **source staging, not installed/imported services**.

The Buildroot post-build hook now accepts an **opt-in** resident source stage, validates its full manifest, requires a target Python **>=3.12**, copies source files and its custody receipt to the rootfs, and grants no auto-start/effect authority. The builder adds an opt-in \`-ResidentSourceStage\` parameter and fails early on the known Python 3.11 Buildroot version. The original CORE_BOOT/BROWSER build paths remain unchanged when the parameter is omitted.

A **disposable target-rootfs simulation** with a Python 3.12 marker exercised the real post-build hook, then the same static image audit. It reported \`READY_FOR_GUEST_IMPORT_PROBES_NOT_QUALIFIED\`; all four source markers, 90-repo catalogs and receipt hashes matched. This proves the packaging **script path**, not the physical target interpreter, external library dependencies, actual guest imports, live resident services or VeraOS UI.

## Verification

- Windows source suite: **101 passed, 6 skipped**, one pytest-asyncio deprecation warning; Linux-native shell/symlink tests account for platform skips.
- Ubuntu/WSL tool suite: **37 passed**, no failures.
- PowerShell build wrapper parser: PASS.
- POSIX post-build shell syntax: PASS.
- Actual October 9 browser ext rootfs: **HOLD_INCOMPLETE_IMAGE**.
- Disposable source-packaging simulation: **READY_FOR_GUEST_IMPORT_PROBES_NOT_QUALIFIED**.
- No active trained-model handoff, canonical memory, P.O.R.T.A.L. route, browser window or full resident-service qualification.

## Next exact frontier

1. Select and pin a reproducible Buildroot base with **Python >=3.12**, while preserving Mesa/WPE WebKit/Cog and the existing guest boot/persistence controls. This changes an exact upstream builder pin and requires a new independently measured build.
2. Add/build target \`jsonschema\`, \`cryptography\`, \`PyYAML\` and other actual imported dependencies for Vera Mono/P.O.R.T.A.L.; validate their licenses and required native dynamic libraries.
3. Build a new **isolated resident-browser** image using the four-source stage; inspect the output's component-file receipt, ABI and native imports inside QEMU before attempting service startup.
4. Separately qualify Pre-Active/Volition routing, resident Vera Mono \`QualifiedVeraRuntime\`, selected trained model artifact consumption, and the VeraOS/P.O.R.T.A.L. GUI roundtrip.
5. Recheck the mutable repository inventory and current four CORE source heads at promotion time; do not treat old observations as latest.

> **HOSTILE REVIEWER:** Does bundling four package markers prove those repositories are actually integrated?
>
> **Accepted:** No. The marker audit intentionally stops at *ready to test imports*. It must never promote source bytes into runtime consumption, authority or behavioral qualification. Native library/ABI tests and real guest service/inference/UI evidence are still required.

No merge, direct \`main\` mutation, OS installation, provider change, paid compute, production cutover or host partition modification was performed by this audit.
