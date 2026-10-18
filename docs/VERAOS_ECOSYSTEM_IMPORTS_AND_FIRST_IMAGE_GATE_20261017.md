# VeraOS current ecosystem interfaces — Integration source qualification, 2026-10-17

**Owner:** Integration L1/L2. **State:** VERSIONED SOURCE EVIDENCE; not installed, not full import closure, not Linux guest qualification.

## Exact, separately bound inputs

- VeraOS Draft #38 prior head `394ea836b3c85590d6f3f6ba514c5d16aabdb050`; existing source file `src/veraos/resident.py` Git blob `3dae5a0e692e2068d353c228956243a45d1b3814`, `pid1.py` blob `bc38666e058db50c65d7064aa78d01f93eb23d09`.
- Canonical Mono #77 `89ba1d18da78e7e38f015cf8d8ef4f528aae9df8`; current Mono `main` at review `16a2828dfa7fb7e6c0e19004f014bc68fc47badf`. Mono main explicitly calls its ChatGPT Project surface an interaction terminal, **not** an installed/current `QualifiedVeraRuntime`.
- Selected source files: Mono 316 at #77; PORTAL 89 at `36fa04da4e5eb383fecf463c72a43b94ca47d7e5`; Pre-Active 18 at `1f23a809d7274df506e03e2d9052525538c3bcf6`; Volition 8 at `dbc628d376515a0a523b1eecdf62129cca5d6b08`. Frozen **431 source-only** files with immutable *stage* receipt SHA256 `6f0031c1fcbaed41e4e3f6947e90a92ed5656ac3e09329de7d8e0b0f8417eca5`.
- PORTAL #55 `7ead3b4fa314083ceb9e035c0ef2f6822daefcea`, private #373 `74710211c7f3a5e1a516802a2e7d87ad68297dc2`, typed #375 `64d6b520dc50327ff8e6f17b3e41f449c4b7b044`, selected PORTAL closure #378 `31fe46807f1c41a197f1c155bc0171c144bd8e8f`, 96-source cut #379 `162b38e2180b447838ad5a6b51dffd99a77c2276` all **private review candidates**. Restore #376 `d0f5564df4fc8da5f8a05740ce506a172c91864b`, files 00–04.
- Independent VN1 original forged-ack GREEN and **new malformed `history.truncated` RED**: Bus #368 comment #6244242026. This branch's repair requires **`data.truncated===false`**, rejecting absent, string, null, numeric, array/object and true before pending retirement.

## Source-bound selected runtime graph

```text
Buildroot Linux x86_64 (effective .config NOT resolved, no actual image)
    /sbin/vera-init (normal selected, not diagnostic VirtIO init)
      -> veraos.pid1 (one supervisor)
         -> python3 -m veraos.resident (one canonical runtime per guest root)
           -> vera_core (Mono QualifiedVeraRuntime/VeraStateDirectory)
           -> portal selected package initializer (eager relative imports)
              -> portal.vera_task_handoff advisory library
              -> portal.route_resolver / PortalRouteAdvertisement
           -> pre_active.Store (operational SQLite, source evidence)
           -> volition.VolitionEngine (constructed advisory-only)
           -> loopback HTTP /api/conversation, /api/conversation/history
         -> /usr/bin/cog --platform=drm http://127.0.0.1:18765/
```

The machine-readable `architecture/os/VERA_OS_CURRENT_GUEST_IMPORT_MATRIX_V1.json` identifies **eight direct selected import/API edges**, exact importing and target Git blobs, invoked symbols, process owner and classification; targeted executable AST and selected package API tests verify its local paths. Current `resident.compose_components` imports `vera_core, portal, pre_active, volition`; no import of a separate Windows Desktop service. `resident.main` imports Mono `open_message`, `recover_message`, `reserve_source_trial`, `seal_source_observation`, Mono `export_portal_route_request`, PORTAL `assess_vera_task_route` and `PortalRouteAdvertisement`; only the fixture/source-observation path uses the selected advisory route. The **whole 89-file PORTAL stage** is not synonymous with 89 runtime imports. Selected `portal/__init__.py` eagerly imports fourteen internal modules; #378 AST analysis observes 43 PORTAL package .py files, nineteen potentially reachable, twenty-four not reached and 47 source links. The AST possibility is **not actual boot consumption**, permission to delete files, proof that runner is an external service, or an ELF/Python target closure. Selected `portal/runner` is a Python subpackage, not the separate external Project Runner process.

Training #109 `0e0f1c0ca0788bfb7e4c626fa0e77a165729a764` separately demonstrated canonical Mono-only task and cold recovery without Pre-Active or Volition (57 source PASS); it **does not** replace the current four-import #38 process or establish a lightweight graphical guest. Pre-Active/Volition can become optional only in a *separately implemented and tested* resident variant. No current source removal is authorized.

## Canonical cross-host ABI

On a **selected** native runtime, `VeraStateDirectory` constructs `QualifiedVeraRuntime.from_state_directory` and its **single** canonical `runtime.tasks` journal. Untrusted `conversation_id,message_id` use Mono's bounded `^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$`; original literal text is exact, nonempty, max 2,048 chars, no silent trimming. The pair binds deterministic task ID; original pair+literal bind source digest. `open_message` creates or verifies immutable `TASK_OPENED`, packet/source/head; same source replays the same identity; changed source with same locator fails. Task mutations use expected-task-head CAS. `recover_message`/history expose read-only source/currentness; ambiguous outcome is `OUTCOME_UNKNOWN_NO_REDISPATCH`, never a new task ID or fabricated completion.

Canonical unadmitted route remains `PENDING_NO_ADMITTED_PROVIDER`: Windows Desktop #55 presents **HELD**; VeraOS HTTP presents **BLOCKED** plus bound no-provider ack after exact Mono source/head/history readback. **UNKNOWN/HOLD** is required for contradictory, unreadable, truncated or unauthenticated reply evidence. Cog now retires its UI-only retry selector only if history has explicit JSON Boolean `truncated:false` and the existing source/head/row matches. A synthetic Pre-Active `DONE` event and `COMPLETED` run are operational observations, **not** admitted model answer, memory or protected effect. Windows `VERA_MONO/VERA_PROJECT_IDENTITY_V1` root and Linux `veraos/VERA` root stay separate; no shared SQLite writer, root migration or pretend ChatGPT Project identity.

## Target package requirements and first real-image acceptance procedure

**SOURCE ONLY targets selected by Buildroot candidate 2025.02.18**, peeled commit `d030e36bbc9669230c015be971b14b6e062cfdde`, defconfig `buildroot/configs/veraos_x86_64_resident_browser_defconfig`: Python 3.12.14 with `sqlite3`, `ssl` and stdlib modules; `python-jsonschema` 4.23.0, `python-cryptography` 44.0.1 with native `_rust` extension, `python-pyyaml` 6.0.2; native `libsqlite3.so.0`, `libssl.so.3`, `libcrypto.so.3` and transitive loader/SONAME/ELF link closure; Cog DRM/WPEWebKit/Mesa/DejaVu, kernel DRM device support, loopback and normal PID1. Persist canonical Mono at `/var/lib/veraos/resident/vera-state`, Pre-Active operational at `/var/lib/veraos/resident/pre-active.sqlite3`, lifecycle at `/var/lib/veraos/lifecycle`, ephemeral socket at `/run/veraos`, sources at `/opt/veraos/components`. These are **candidate package names and source requirements**, not observed installed target package closure.

A future **independently falsifiable first image** requires this evidence in order:

1. **Before build, source/provenance admission:** authorize an isolated Linux Buildroot build host and resource limits separately; freeze exact four source commits and selected VeraOS commit, Buildroot tag/peeled commit, toolchain and package source digests. Define explicit LF/CRLF checkout/materialization policy and resulting source-byte hashes: #378 demonstrates that Windows checkout raw stage can differ from Git immutable blobs despite filtered `git hash-object` equality. Reject mixed source receipts.
2. **Effective Kconfig:** use the pinned Buildroot source and selected defconfig, retain generated *effective* `.config`, relevant `BR2_PACKAGE_*` and toolchain hashes and all dependency/patch resolutions; fail on missing Python/sqlite/ssl/jsonschema/cryptography/YAML, Cog DRM/Mesa/WPE/DejaVu, kernel/devices or unresolved symbols. No unrun defconfig constitutes an effective build.
3. **Actual target package/rootfs closure:** authorized isolated cross-compile; capture kernel/rootfs/toolchain/build logs, source stage copy receipt, every packaged source member's bytes SHA256, target Python extension and `DT_NEEDED` transitive closure. Existing opt-in post-build static target file audit + bounded `Probe-ResidentELFClosure.py` can fail a candidate; its synthetic tests do not establish real ELF validity. Witness actual target Python native imports and `ldd`/dynamic loader SONAME/version closure on target, including Cog/WPE native libs.
4. **Actual completed image:** hash immutable produced ext2/kernel/image artifacts, independently inspect the built ext2 against the exact selected 431-member inventory and embedded receipt using real `debugfs`, and reject unexpected files/shadowing. The previous mock-debugfs suite is already done and does not satisfy this.
5. **Separately authorized normal guest:** only when Patrick approves QEMU and resources, boot `/sbin/vera-init` not `vera-virtio-probe`; observe PID1 supervised resident socket + Cog DRM pixels/input, no-provider exact TASK_OPENED/HELD and zero model/effect. Cold reboot twice, verify one persisted message/source/head and deterministic closure with zero redispatch. Record guest logs/artifact hash and independent VN1 review. Do not infer model/provider admission.
6. **Explicit provider/trust later:** issuer-owned loaded model/process/route/session/nonce, durable single-use nonce, causal Pre-Active event/run and result readback; Training #110 still reports a cold-restart nonce replay RED. No automatic model/reasoning/memory promotion or protected effects.

**Current gates:** SOURCE-STAGED ONLY; KCONFIG_UNRESOLVED; TARGET_PYTHON_NOT_RUN; TARGET_ELF_NOT_QUALIFIED; REAL_ROOTFS/IMAGE_NOT_BUILT; GRAPHICAL_PID1/COG_NOT_BOOTED; TWO_COLD_BOOTS_NOT_RUN; MODEL/MEMORY/PROTECTED_EFFECT_DENIED. No heavy build, QEMU, physical install, live model, production trust, identity migration or main merge authorized.

## PORTAL accept/challenge disposition

**ACCEPT SOURCE-BOUND** #373/#375/#378/#379 taxonomy/96 placements and owner split, 147 `PROPOSED_CONSUMER` plus four `STAGED_SOURCE_SNAPSHOT` links, no promoted qualified hard runtime edges, single Mono task ABI and four currently selected imports. **CHALLENGE** treating those review edges as actual imports or the 431-file stage as a proven minimal boot; challenge `portal/__init__` eager transitive reachability until real target import; challenge materialization provenance CRLF-vs-Git LF; preserve no-provider HOLD and real build/guest/model admission stops. No owner branch other than VeraOS #38 edited.

**Verification:** bounded Node Cog regression including missing/malformed `history.truncated` RED→GREEN, source import matrix Python tests with pinned selected library APIs, focused existing synthetic target ELF parser test. Fresh commands/log SHA recorded in Bus #368. New PR is an owner Draft, not independent acceptance; VN1 must independently repeat on exact head.
