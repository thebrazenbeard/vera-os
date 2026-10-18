# VeraOS VN2 effective Buildroot Kconfig qualification — source/config only

**Owner:** Integration (Mono #77 / VeraOS Draft #38). **VN2 live Linux** `patrick-ThinkCentre-M900`, x86-64, Python 3.12.3, GNU make/GCC, ~6.2 GiB initially available RAM. **Mode:** one invoked bounded source/config test. No future scheduling or hidden worker.

## Exact read inputs and reviewer status

- VeraOS #38 **pre-increment** `d10d2b95249c73435f2d73e0c9a01ae100ab40de`, pinned browser-resident defconfig Git blob `227ec1a766ce0a84b0c5af35249358600b46ee7d`, candidate architecture `VERA_OS_RESIDENT_BUILDROOT_CANDIDATE_V1`, Mono #77 `89ba1d18da78e7e38f015cf8d8ef4f528aae9df8`.
- Restored PORTAL private #376 five files 00–04 at `d0f5564df4fc8da5f8a05740ce506a172c91864b`; PORTAL architecture #373, typed #375, component #378, source-cut #379, no-effect seam #380, coordination #381, all source Drafts. Bus #368 current and active delegation context read. Latest Desktop Codex A1 #55 at `88026ea85c1ebc480396b582cf473df5a30e031e`. No peer branch changed.
- Existing #38 Cog malformed/missing `history.truncated` fix already present, `data.truncated!==false`; original VN1 RED and Integration GREEN (13/13 Node on prior assigned VN1) in Bus #6245307026. **No duplicate Cog patch.** VN2 lacks Node; source-browser pixels and independent newest-head requalification remain separate.
- Current selected Python resident imports from `src/veraos/resident.py@3dae5a0e692e2068d353c228956243a45d1b3814`: `vera_core`, selected `portal`, `pre_active`, `volition`; all current `compose_components` imports, only task core intrinsically required for a *different* no-provider-only implementation. Four pinned source selections: Mono 316, PORTAL 89, Pre-Active 18, Volition 8 = 431 source-stage files, frozen stage receipt `6f0031c1fcbaed41e4e3f6947e90a92ed5656ac3e09329de7d8e0b0f8417eca5`. **No 431 files installed or rebuilt on VN2**.
- Exact source-bound guest import graph: `architecture/os/VERA_OS_CURRENT_GUEST_IMPORT_MATRIX_V1.json` in existing #38; 8 actual selected importer/API edges. PORTAL #378 AST 43 package modules / 19 conservatively reachable / 24 not reached / 47 references, not actual guest imports. Windows full PORTAL/Desktop/Project Runner is **not** Linux PID1, the selected PORTAL `runner/` package is embedded source only. 96 portfolio repositories, 147 proposed consumer edges and 4 typed source-stage links are **not 96 boot packages**. Training #109 proved Mono-only cold task/HELD source without Pre-Active/Volition in a separate experiment, not the current selected guest.

## Reproducible lightweight Kconfig command — executed on VN2

Only a 7,229,543-byte official upstream Buildroot **source tarball** for pinned peeled commit `d030e36bbc9669230c015be971b14b6e062cfdde` was downloaded under an isolated `/tmp/bt2-vn2-veraos-kconfig-20261017` workspace. Archive SHA-256:

`32e0115b41fc3a3659f13ed64b14843a98b0ccc0ac4b9edc50f918f952369419`.

Exact source Git blob bytes were materialized through authorized GitHub read into a minimal BR2_EXTERNAL with **10/10 pinned file SHA-1 Git blob objects matching**, including external metadata, selected defconfig, three Cog patches, normal overlay init, diagnostic init and the resident post-build hook. No Windows CRLF checkout ambiguity (10 exact Git byte identities checked); the historical Windows 431-file checkout/stage still has a separate CRLF-vs-immutable Git source issue requiring an image source policy.

Executed **configuration generation only** (not `make` default/build):

```sh
root=/tmp/bt2-vn2-veraos-kconfig-20261017
br=$root/buildroot-d030e36bbc9669230c015be971b14b6e062cfdde
make -C "$br" O="$root/output" BR2_EXTERNAL="$root/veraos-external" \
    veraos_x86_64_resident_browser_defconfig
```

Exit **0**, stderr empty, true effective `output/.config` SHA-256:

`19f54f106aa682650d7230a1087689ef303ffd938720a21893f41bf6afbac9bd`

**51/51** requested defconfig assignments survived actual Kconfig, and **19/19** separately required Python/native/DRM/candidate image symbols remained `y`. Effective config contains 3,943 BR2 symbol assignments/comments, including selected Python 3, sqlite3, SSL, `python-jsonschema`, `python-cryptography`, `python-pyyaml`, WPEWebKit, Cog DRM, Mesa, DejaVu, x86-64 glibc, kernel and ext4 rootfs. Pinned external rootfs overlay, Cog patch directory and executable post-build entry were verified present. A **second** exact limited `make …_defconfig` completed with byte-identical effective SHA256.

New `tools/vm/Probe-ResidentKconfig.py` reads an independently pinned source/Buildroot archive SHA manifest, verifies raw Git object identity of the exact BR2_EXTERNAL files, compares each requested symbol with effective `.config`, rejects duplicates/invalid values/dropped symbols and missing/outside/nonexecutable external paths, and reports **`PINNED_KCONFIG_RESOLVED_SOURCE_ONLY`**. Target symbols, source bytes and config digest are copied to JSON receipt `architecture/os/VERAOS_PINNED_BUILDROOT_KCONFIG_V1.json` plus captured CLI report. Fixed architecture symbol parsing (e.g. actual `BR2_x86_64`) during RED→GREEN. No protected runtime action.

Run/verify:

```sh
VERAOS_VN2_PINNED_KCONFIG_WORKSPACE="$root" \
  python3 -m unittest discover -s tests \
    -p test_resident_pinned_kconfig_unittest.py -v
python3 tools/vm/Probe-ResidentKconfig.py \
  --pinned-inputs architecture/os/VERAOS_PINNED_BUILDROOT_KCONFIG_V1.json \
  --br2-external "$root/veraos-external" \
  --effective-config "$root/output/.config" \
  --upstream-source-archive "$root/buildroot.tgz"
```

Focused Python 3.12 stdlib tests **10 PASS / zero skipped**, including real pinned VN2 configuration, fake/changed Git source bytes, missing external files, dropped Cog flags, duplicate symbols, invalid BR2 path, and wrong upstream archive. Initial tests RED due missing tool, then parser rejected lowercase `BR2_x86_64` before corrected GREEN. This provides host-side reproducibility for the **effective Kconfig stage only**; provenance of the source tarball comes from the exact GitHub commit archive + recorded archive SHA, not a VN2 local git checkout.

## Canonical runtime/effect contract unchanged

Host-selected `VeraStateDirectory → QualifiedVeraRuntime.tasks` opens one exact `TASK_OPENED` for bounded untrusted `(conversation_id,message_id)`, original literal and source digest; per-task expected-head CAS; identical replay, conflicting literal rejected; cold read-only reconciliation; no-provider canonical `PENDING_NO_ADMITTED_PROVIDER`. Windows Desktop presents `HELD`, VeraOS wire `BLOCKED`, ambiguous/truncated history `OUTCOME_UNKNOWN_NO_REDISPATCH`. Linux `veraos/VERA` state root, Windows `VERA_MONO/VERA_PROJECT_IDENTITY_V1` root and ChatGPT Project surface remain **distinct**; no shared SQLite ownership, memory or effect authority. Pre-Active is operational evidence and Volition advisory only. Optional Training/provider issuer+loaded artifact/session/nonce gate remains unqualified; real model execution forbidden absent separate authority.

## Source/config qualification ceiling and first real-image gate

**Now supported:** exact Buildroot pinned upstream tarball, all 10 BR2_EXTERNAL **Git blob bytes**, selected defconfig, resolved Kconfig and reproducible effective `.config`. **NOT** a built toolchain: actual Buildroot 2025.02.18 download/build dependencies, target Python **3.12.14** and compiled cryptography `_rust`, actual ELF `DT_NEEDED` and symbol/loader closure, completed rootfs and member hashes, actual ext2 image and real debugfs byte inventory, graphical kernel/normal `/sbin/vera-init` + resident Cog DRM rendering/input, and two cold boots are **UNQUALIFIED / NOT EXECUTED**.

Next separately authorized **heavy** isolated build must retain the exact upstream/config/external pins, toolchain package hashes and build logs, assemble the target source closure with declared LF/CRLF policy, execute actual target imports/native link test and `Probe-ResidentELFClosure.py` on a built rootfs (synthetic fixture not qualification), and hash/independently inspect exact ext2/kernel artifacts. A separate QEMU approval and resource gate precedes normal graphical boot/two-cold-boot testing. No model/provider, device, production memory/trust/effect/physical installation or main merge.

**Coordination:** PORTAL L1 receives this Kconfig evidence and component-level ACCEPT/SOURCE_ONLY disposition through private Bus #368; Training L2 keeps real model/nonce/provider on HOLD and considers this package profile as *source-selected*, not loaded; VN1 L3/L4 independently reviews exact new #38 source and Kconfig provenance/negative tests (not an Integration self-ACK). No scheduled or background continuation.
