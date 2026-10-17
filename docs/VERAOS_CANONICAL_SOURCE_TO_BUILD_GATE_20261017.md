# VeraOS canonical source-to-build readiness gate — 2026-10-17

CURRENT ASSESSMENT: **NOT_READY_KCONFIG_UNRESOLVED**. SOURCE selected and verified. No actual image build, target Python import, guest PID1, Cog rendering, model execution, trust/effect or canonical memory admission.

## Exact selected source
- Vera Mono #77: 89ba1d18da78e7e38f015cf8d8ef4f528aae9df8 (316 files).
- PORTAL #51: 36fa04da4e5eb383fecf463c72a43b94ca47d7e5 (89).
- Pre-Active: 1f23a809d7274df506e03e2d9052525538c3bcf6 (18).
- Volition: dbc628d376515a0a523b1eecdf62129cca5d6b08 (8).
- 431-file exact staging receipt SHA256: 6f0031c1fcbaed41e4e3f6947e90a92ed5656ac3e09329de7d8e0b0f8417eca5.
- Verified unchanged by existing Stage-VeraOSResidentSources.py against read-only C:\VeraVN1FinalStage20261017\stage on VERA-NODE-1; exit 0.
- The staged SOURCE is NOT an actual Buildroot rootfs.

## Selected build inputs, measured on VERA-NODE-1
- Buildroot annotated tag 2025.02.18, tag object b611e07ef088c70c1e21f77c30872bce97a1f1c2, peeled commit d030e36bbc9669230c015be971b14b6e062cfdde.
- Fresh sparse source checkout C:\VeraIntegrationOSGate20261017-Buildroot, separate from VN1 reviewer work.
- Profile buildroot/configs/veraos_x86_64_resident_browser_defconfig.
- Target Python 3.12.14, jsonschema 4.23.0, cryptography 44.0.1, PyYAML 6.0.2.
- Selected Python sqlite/ssl, Cog DRM, WPE WebKit, Mesa and DejaVu Sans/DejaVu static feature flags.
- Executed Probe-ResidentBuildroot.py on exact upstream source, exit 0; output PINNED_SOURCE_SYMBOLS_VERIFIED_KCONFIG_NOT_RUN, build_readiness=NOT_READY_KCONFIG_UNRESOLVED, ready_for_authorized_build=false. A successful SOURCE preflight does not resolve Kconfig or authorize a build.

## New owned source-to-package change, unexecuted inside Buildroot
Only the opt-in VERAOS_REQUIRE_RESIDENT_CORE=1 branch of buildroot/board/veraos/x86_64/post-build.sh is modified. Its future build path requires target /usr/bin/python3 to be python3.12 (not merely a newer host), verifies the exact stage, copies component files and source receipt, re-verifies ALL COPIED 431 source bytes with Verify-VeraOSResidentFiles.py, rejects unexpected/stale extra component source files, then calls Probe-ResidentTargetRootfs.py. Any failure stops the opt-in packaging operation. No image build was initiated in this turn.

Probe-ResidentTargetRootfs.py is a static read-only directory-rootfs checker. It denies a missing Python 3.12 interpreter/stdlib sqlite/ssl source or compiled extensions, missing jsonschema/cryptography/yaml Python source, missing or changed VeraOS pid1/resident/desktop source, incorrect /sbin/vera-init invocation, missing Cog executable or DejaVuSans.ttf. A fixture with all expected files reports TARGET_ROOTFS_STATIC_PRESENT_GUEST_UNQUALIFIED with all runtime/graphical/import/model/effect booleans false. This CANNOT verify target linking/imports, real executable permission, DRM device, service startup or rendered Cog UI.

Normal future PID1 is /sbin/vera-init -> veraos.pid1.main, resident process with components at /opt/veraos/components, run root /run/veraos, persistent state at /var/lib/veraos/resident. Cog is /usr/bin/cog --platform=drm http://127.0.0.1:18765/ and can only be started after resident no-provider health, loopback and DRM gate. No guest was observed.

## Exact targeted source-only Windows Python 3.13.15 verification
- python -m unittest discover -s <os>/tests -p test_resident_target_rootfs_preflight.py -v : 5 PASS (including nine missing module/asset/PID1 subcases, bad Python version, malformed source, false-claim denial).
- python -m unittest discover -s <os>/tests -p test_resident_all_file_audit.py -v : 10 PASS (including stale-copy extra-file rejection and missing/altered byte/receipt).
- VERAOS_BUILDROOT_CHECKOUT=<pinned buildroot> python -m unittest discover -s <os>/tests -p test_resident_real_buildroot_preflight_unittest.py -v : 3 PASS (absent Cog, DRM, font, SQLite/SSL flags or wrong Buildroot source pinned SHA all deny).
- VERAOS_REAL_STAGE=<exact stage> VERAOS_TEST_TEMP=<short isolated temp dir> python -m unittest discover -s <os>/tests -p test_resident_exact_stage_rootfs_unittest.py -v : 1 PASS; independently copied all 431 files to disposable rootfs, verified all bytes/receipt, then refused stale import, changed byte, wrong receipt. The original VN1 stage was NOT written.
- Total **19 PASS / 0 SKIP** across four specifically executed builtin unittest suites. Previously independently verified Mono and VeraOS regression evidence remains applicable to its exact prior heads; the broad owner pytest suite was NOT rerun during this patch: pytest is absent from VERA-NODE-1 default Python. No green suite is claimed beyond actually run tests.

## SOURCE / PACKAGE / GUEST gates
SOURCE exact selected 4 repos and archive receipt PASS. Upstream Buildroot 2025.02.18 static source symbols PASS. READY_FOR_AUTHORIZED_BUILD remains **NOT_READY** pending resolved exact Kconfig/toolchain. Actual post-build copied-rootfs hooks are source-tested and disposable-directory tested but NOT executed under Buildroot. Actual target Python import, PID1 health, Cog fonts/DRM/rasterization, browser-local HTTP conversation and two cold boots UNKNOWN/UNTESTED. Training source-only task/head/nonce model gate HELD; real signed loaded-provider evidence absent. Canonical memory and protected effects HELD.

## L1/L2 host contract and ownership
Read PORTAL Desktop #52 source: desktop_cognize still uses its own operational cognition ledger, strips input text, and does not open Mono #77 canonical task before routing. The Codex A1 fix is PORTAL-owned; no edits to the Codex/PORTAL branch. Mono local_conversation.open_message already supports explicit stable conversation/message IDs, exact untrimmed literal input, task CAS/source digest, and cold recovery. No demonstrated Mono API gap required modifying #77. Separate PORTAL installed state/identity and VeraOS resident state/identity are NOT automatically one physical root; no migration/exclusive writer claim. V-E-R-A #6 remains a source and historical snapshot/evidence workspace, not a 44-repo guest dependency. Supabase/Drive/Synology/coordination data are not canonical memory or runtime boot requirements by presence. Training #106 scoped turn is not model admission. Source tests do not authorize an actual build, guest, model or effect.
