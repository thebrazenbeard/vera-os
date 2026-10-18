# VeraOS #38 — actual selected source-to-ELF closure, 2026-10-17

**Owner:** Integration L1/L2. **Evidence class:** source + executable synthetic ELF test ONLY.
This is an additive exact-head review of CCB private #373 (architecture at
`74710211c7f3a5e1a516802a2e7d87ad68297dc2`), #375 typed graph at
`64d6b520dc50327ff8e6f17b3e41f449c4b7b044`, five-file #376 checkpoint
at `d0f5564df4fc8da5f8a05740ce506a172c91864b`, Mono #77
`89ba1d18da78e7e38f015cf8d8ef4f528aae9df8`, PORTAL A1 #55
`2f42d494e46d9613cd2626da7c9fa6f0e8d7ec79`, and Training #109
`0e0f1c0ca0788bfb7e4c626fa0e77a165729a764`.
All are review/source subjects, not installed OS evidence.

## Selected components, exact imports and ownership

Normal Linux `/sbin/vera-init` invokes `veraos.pid1.main`. Source
`src/veraos/pid1.py` selects `python3 -m veraos.resident` as supervised child,
owns lifecycle/health supervision, and only starts Cog DRM pointing to
`http://127.0.0.1:18765/` when the resident is healthy and DRM is present.

`src/veraos/resident.py` declares
`COMPONENT_NAMES=(vera_core, portal, pre_active, volition)`.
`component_paths()` prepends **all 12** Mono
`/opt/veraos/components/vera_mono/packages/*/src` roots, then
`/opt/veraos/components/portal`,
`/opt/veraos/components/pre_active/src`,
`/opt/veraos/components/volition/src`.
`compose_components()` imports all four names, explicitly demands
`vera_core.QualifiedVeraRuntime` and `portal.resolve_portal_route`,
constructs `VeraStateDirectory(state_root/"vera-state",
project_id="veraos",identity_id="VERA")` and its one
`QualifiedVeraRuntime.from_state_directory`,
opens `pre_active.Store(state_root/"pre-active.sqlite3")`, then constructs
`volition.VolitionEngine()`. These are CURRENT source dependencies, not
separate required daemons or proposed 96-repository service relations.
`ResidentHandles.close()` closes the scoped Pre-Active store; Mono native
SQLite paths close transactions at their ownership scopes. Actual host
closure/reopen requires process tests; do not infer a distributed writer lock.

`resident.main` imports
`vera_core.local_conversation.{open_message,recover_message,
reserve_source_trial,seal_source_observation}`,
`vera_core.portal_task_handoff.export_portal_route_request`,
`portal.vera_task_handoff.assess_vera_task_route` and
`portal.PortalRouteAdvertisement`. The normal no-provider path opens
one Mono task and returns a typed `BLOCKED` presentation (Mono underlying
`PENDING_NO_ADMITTED_PROVIDER`), with unchanged original
conversation/message/literal/source digest/head and no model call.
Pre-Active event/run/one-route and Volition proposal APIs are needed for
the current selected fixture/initiative composition, NOT intrinsically for
Mono `TASK_OPENED` and cold replay. Training #109 separately proved the
latter with no optional imports; that did not change this resident.

Frozen component sources: Mono 316; PORTAL 89; Pre-Active 18;
Volition 8 = **431 source files** selected from four exact commits;
receipt SHA256
`6f0031c1fcbaed41e4e3f6947e90a92ed5656ac3e09329de7d8e0b0f8417eca5`.
Inside selected PORTAL root, both `portal/` and `runner/` packages
are present; `runner` is not proof that the independent Project Runner
service is started. Source AST across the four stage roots finds
non-stdlib candidates `jsonschema` and `cryptography` (Mono),
`yaml` and `jsonschema` (PORTAL), with `runner` supplied within
selected PORTAL. Pre-Active/Volition selected modules show stdlib plus
known local imports on this scan. Dynamic imports, package resource
readers and transitive native extension requirements remain separate gates.

## Operating-system selection and evidence boundary

Pinned candidate Buildroot **2025.02.18**, peeled commit
`d030e36bbc9669230c015be971b14b6e062cfdde`,
`buildroot/configs/veraos_x86_64_resident_browser_defconfig`;
required target Python **3.12.14**, sqlite3/ssl extensions,
jsonschema 4.23.0, cryptography 44.0.1 and PyYAML 6.0.2,
plus glibc x86_64, WPEWebKit/Cog DRM, Mesa, fonts/DejaVu,
kernel/device support, persistent/ephemeral state.
Historical boot-contract 2024.02.4 is NOT this candidate's resolved build.
As of this checkpoint, actual effective Buildroot `.config` and
cross-toolchain provenance have NOT been resolved. VN1 currently offers
Windows Python/Node but no verified Linux Buildroot host make/WSL distro;
no Buildroot make, cross-compiler or large build was invoked.

**New bounded increment:** `tools/vm/Probe-ResidentELFClosure.py`
is a stdlib, bounded, fail-closed **static** ELF64 little-endian x86_64
PT_DYNAMIC/DT_NEEDED parser. It starts at Python 3.12/Cog plus
target `_ssl`, `_sqlite3`, cryptography `_rust` and discovers
native Python extensions under lib-dynload/site-packages. It recursively
resolves shared libraries within explicit guest directories, checks ELF
target machine and PT_LOAD-bounded string tables, rejects missing,
ambiguous, malformed, unsupported RUNPATH/RPATH and escaping deps,
and emits per-file sha256 and exact edges with GUEST_UNQUALIFIED status.
The opt-in `VERAOS_REQUIRE_RESIDENT_CORE=1` Buildroot post-build
step invokes it **after** existing source + target-file checks, before
image completion. It does NOT execute target Python, validate ELF
relocation/symbol versions, prove `dlopen` paths, validate kernel ABI,
WPE graphics, produce an actual Buildroot image, or replace
authoritative receipt/hash or normal guest observation.

The new source test generates executable-format ELF64 metadata fixtures
in disposable directories, demonstrates missing-script RED at predecessor
and parser/hook GREEN plus malformed, foreign architecture,
missing transitive lib, path traversal, missing cryptography extension,
overlarge segment and unsupported runpath negatives. It is not a
real rootfs. On the FIRST actual authorized isolated Buildroot run:
capture effective Kconfig SHA and selected source/toolchain hashes;
compile kernel/rootfs; perform this probe and existing full 431
member+byte audit on actual copied target tree, then record actual
artifact hash and independently validate **built ext2 image**.
Only after separate QEMU authorization: selected normal PID1,
target Python imports/ELF linker behavior, Cog DRM frame and input,
two cold boots with same no-provider held task/head. All later
build/image/guest/model/memory/effect fields stay **HOLD**.

## PORTAL V1 and typed-graph decision

**ACCEPT, source-only:** one Mono task owner, exact bounded untrusted UI
locators, stable TASK_OPENED/source digest/CAS/replay, genuine
no-provider HOLD, source-only and operational evidence separation,
distinct Windows `VERA_MONO/VERA_PROJECT_IDENTITY_V1` and Linux
`veraos/VERA` state roots, typed GUI projection and independent
no-redispatch cold recovery.

**CHALLENGE / incomplete:** #375 `147 PROPOSED_CONSUMER` + four
`STAGED_SOURCE_SNAPSHOT` edges, and zero promoted hard runtime imports,
is correctly nonauthoritative for installation but must NOT obscure the
four concrete imports in the currently selected `resident.py`. Type
real import/module/symbol edges with exact code and target closure.
Do not turn six-node false-hard dependency cycle into boot graph.
#373 431-file prototype is real source-stage membership; not a
smallest-possible Mono-only system. No host state-root/identity merge.
Training #109's claimed no-provider minimum is separately SOURCE-valid,
not a replacement bootable guest. Model-issuer/nonce, provider transport,
Pre-Active result acceptance, memory and effect remain HELD.

## Reviewer obligations

VN1 independent requalifies #38 Cog exact latest head against original
forged `BLOCKED/ui-*`, mismatched message/source/task/journal head,
contradictory/missing/truncated history, lost GET and duplicate unknown.
This increment did not rerun old ext2 fixture suites as new image proof.
VN1 independently challenges new ELF probe with actual GNU readelf
on real target rootfs when available; a synthetic ELF generator does not
establish target/linker correctness. PORTAL owns V1 acceptance, Training
owns cognition/provider qualification. No edit to any peer Draft branch.
