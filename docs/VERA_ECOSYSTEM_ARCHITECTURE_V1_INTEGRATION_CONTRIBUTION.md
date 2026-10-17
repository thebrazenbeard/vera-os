# VERA_ECOSYSTEM_ARCHITECTURE_V1 — Integration contribution (L1 PORTAL / L2 Training)

**2026-10-17 — authoritative scope: CURRENT REVIEWED SOURCE only.** This
section is submitted for PORTAL to integrate into its shared
`VERA_ECOSYSTEM_ARCHITECTURE_V1`. It is not a substitute installed
architecture, new registry, identity migration or protected-effect permission.
No existing shared document with that exact name was present in the reviewed
PORTAL #55 source tree or CCB #371/#372 reviews, so owner incorporation and
any document location/version remain PORTAL-controlled.

## Exact source bindings reviewed

- Mono #77 `89ba1d18da78e7e38f015cf8d8ef4f528aae9df8`; source
  `vera_core.local_conversation`, `TaskExecutionLedger`,
  `QualifiedVeraRuntime`, effect fence, state and canonical manifest.
  Mono local manifest asserts SELF_CONTAINED_MONOREPO, 12 owned package roots,
  no sibling repository runtime dependencies; actual Linux resident uses
  its `QualifiedVeraRuntime.tasks`, not a replacement task DB.
- PORTAL Desktop A1 #55 `a5776acc8fa78a169660ef453c8c376c9f8f79f6`
  stacked on #52 `b16413fad12d33a9f9b64d6b1602490f4dede327`.
  Actual `desktop_ipc.py`, host layout, owner policy and executable
  RED/GREEN source tests inspected. **Source Draft**, not installed Desktop.
- VeraOS Integration #38 before this increment
  `578f435a3ab8ae23e8b735b4cc792dfa292a88d3`;
  PORTAL-owned #37 `df04f2cc01bb23e28543c3cea40cd462ba960fd2`;
  upstream #32 `5ddac1459c3a7b06f251721a14048fc26e60bda0`
  is a separate *diagnostic VirtIO PID1*, not selected normal init.
- Pinned selected packaging inputs: PORTAL #51
  `36fa04da4e5eb383fecf463c72a43b94ca47d7e5`,
  Pre-Active `1f23a809d7274df506e03e2d9052525538c3bcf6`,
  Volition `dbc628d376515a0a523b1eecdf62129cca5d6b08`.
  Source stage 316+89+18+8 = 431 files, exact stage receipt SHA256
  `6f0031c1fcbaed41e4e3f6947e90a92ed5656ac3e09329de7d8e0b0f8417eca5`.
- PORTAL frozen private 96-repository source review #371
  `951e7af1a97694faaf6bc18d51b35f70982e31fc`
  and consumer/admission proposals #372
  `ef17ee929d807f5da033a3d5391d553b65c464e8`
  are evidence of proposed interfaces **not selected runtime imports**.
- Training #106 latest reviewed at this cut
  `b4d9d0c785b1cdd31d357dd0cebb89c0ec2b6bfe`;
  read-only `cognitive_governed_predecessor_v1` uses existing
  Mono task `read/events/conversation_history`. It does not introduce a
  new memory or provider authority.

## One canonical lifecycle — exact interface and failure behavior

1. **Host constructs an owned root.** Host passes a unique state directory and
   `(project_id,identity_id)` into `VeraStateDirectory`, then creates
   `QualifiedVeraRuntime.from_state_directory(state)`. Its `tasks`
   object is the **sole canonical task owner** in this host composition.
   There is no global physical owner across two host/state roots, and
   `QualifiedVeraRuntime` cannot mint effect authority by itself.
2. **Client supplies correlation, not identity.**
   `conversation_id` and `message_id` are untrusted exact strings under
   Mono regex `^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$`.
   For Desktop A1, `message_id == existing request_id`; UI owns
   restart-stable active-conversation selection independently of canonical
   memory. Linux Cog owns its own localStorage selector; it is NOT the
   Desktop selector or a person/session authentication credential.
   Missing/corrupt locator fails before source dispatch.
3. **Open immutable literal task before routing.**
   `open_message(runtime.tasks,conversation_id,message_id,EXACT_TEXT)`
   forbids non-string, empty, leading/trailing whitespace and >2048 characters,
   with **no trim or substitution**. Its deterministic task key hashes the
   ordered pair of IDs and the lifecycle source digest includes exact text.
   `TaskExecutionLedger.open_task` verifies the existing TASK_OPENED
   event, task packet digest and immutable source digest; identical replay
   resolves the same task, differing text with the same locator fails.
4. **CAS, source and route are separate.**
   Task journal head/expected-head CAS governs each task mutation and
   independent tasks may advance out of order. PORTAL route assessment is
   advisory: available/attached/current/advertised does NOT equal authorized
   model execution. Pre-Active `Store.events` and `Store.runs` are
   operational source/worker evidence. Its separate `memories` table and
   Desktop `CognitionLedger` are **not** Mono governed memory or task closeout.
   Volition proposals are non-effectful and do not imply consent.
5. **No provider is an actual HELD task, not a fabricated answer.**
   Canonical `PENDING_NO_ADMITTED_PROVIDER` with zero model transport,
   zero trusted answer, zero memory/effect is the current accepted floor.
   Desktop returns wire `state=HELD`; VeraOS normal HTTP's `status=BLOCKED`
   is a *host presentation*, not an alternate canonical task state.
   The Linux UI currently labels the durable no-provider result HELD.
   Avoid equating status vocabulary with a different actual task lifecycle.
6. **Result proof before any separate acceptance.**
   An optional test-only Pre-Active run is checked against ONE exact source
   event/run, matching literal, task, selected route and BOTH terminal
   `events.status=DONE` and `runs.status=COMPLETED`. A synthetic fixture
   result is labelled `accepted_as_task_result=false`,
   `display_authorized=false`, `model_authenticated=false` and cannot
   finish a protected task or enter governed memory. Real model requires
   independently verified model bytes/loaded host process, admitted provider
   role, exact task/head/session/nonce, causal response and trust checks.
7. **Recovery is read-only until explicitly reconciled.**
   `conversation_history/recover_conversation` reverify source/task opener;
   `recover_message` returns PENDING, HELD or
   `OUTCOME_UNKNOWN_NO_REDISPATCH` for ambiguous attempted work. Unknown
   effects and bridge claims are not redispatched under new IDs. Any
   source-seal writes are separate, explicit, expected-head CAS operations.
   Operational synthetic completion never promotes canonical truth.
8. **Close owners deterministically.**
   A host stops acceptors/child processes before closing its Pre-Active Store,
   canonical SQLite-backed components and OS state handles. Win32 owner
   release and cold child process tests exist for pinned Mono/OS source.
   Windows Local-session mutex in PORTAL #52 is **not** distributed or
   cross-session writer exclusivity. POSIX / guest process ownership still
   requires real witness; never point both hosts at one SQLite root.

## Actual Desktop versus VeraOS (source-level)

| Dimension | PORTAL Desktop #55 | VeraOS normal #38 | Disposition |
| --- | --- | --- | --- |
| GUI | Windows Desktop view model + FileBridge JSON claims | Cog/WPEWebKit DRM, loopback HTTP :18765 | Valid transport adaptation |
| Canonical source | `open_message` before route; raw text, `HELD` | Same Mono API in `resident.handle_text` | Same canonical contract |
| Identity/root | `state/vera`, `VERA_MONO/VERA_PROJECT_IDENTITY_V1` | `/var/lib/veraos/resident/vera-state`, `veraos/VERA` | Deliberately separate; NEVER migrate implicitly |
| Operational stores | Pre-Active + CognitionLedger telemetry | Pre-Active SQLite worker store + Mono tasks | Operational is not memory/result authority |
| UI selector | Explicit user new-conversation, atomic UI metadata | Linux browser localStorage, generated local console ID | Host UX difference, not verified shared identity |
| No admitted provider | `HELD`, zero `ResidentCognitionEngine` | `BLOCKED` wire; canonical persisted PENDING | Surface terminology difference, not task completion |
| Restart | Existing file bridge claim/reply, Windows root mutex | PID1 resident supervisor, cold Mono readback | Separate lifecycle owners, same task CAS per root |
| Graphical/installed claim | #55 source-only, no cutover | #38 source-only, no boot of this exact head | BOTH uninstalled/unqualified |

**Source-only semantic issue found and corrected on Integration branch:** the
Linux Cog JS previously called `input.value.trim()`, silently substituting
a new literal. It also could mint a new request ID for a DIFFERENT text while
a previous message was unresolved, replacing the UI retry selector. Updated
Cog code rejects invalid surrounding whitespace, holds an unresolved
different text/conversation ID, reuses an exact prior request ID, and
retires only the UI retry pointer after a normal no-provider HTTP reply
containing a canonical `ui-` task ID. Unknown/failed responses preserve the
pending selector. This does not turn localStorage into a trusted ledger.
Node source-script tests executed RED (3 assertion failures) → GREEN (5/5).

## Minimal rooted VeraOS graph and bill of materials

```text
Linux kernel + Buildroot target userspace (glibc, Python 3.12.14,
  sqlite3/ssl compiled modules, jsonschema, cryptography, PyYAML)
       |
       +-- /sbin/vera-init -> veraos.pid1.main
             |-- lifecycle marker /var/lib/veraos/lifecycle
             |-- resident child (bounded restart + verified socket health)
             |    |-- /opt/veraos/src/veraos (OS host adapters)
             |    |-- /opt/veraos/components/vera_mono
             |    |       12 INTERNAL Mono packages, including
             |    |       vera_core, vera_memory, vera_assurance, vera_recovery,
             |    |       rezon and portfolio_runtime
             |    |-- /opt/veraos/components/portal    (advisory)
             |    |-- /opt/veraos/components/pre_active (source Store)
             |    |-- /opt/veraos/components/volition   (proposals)
             |    |-- QualifiedVeraRuntime.tasks
             |    |       -> open_message -> TASK_OPENED/PENDING
             |    |       -> recovery/head/source/event integrity
             |    +-- separate /var/lib/veraos/resident/pre-active.sqlite3
             |
             +-- Cog DRM browser -> http://127.0.0.1:18765/
                    only local task intake and read-only status/history
```

Necessary base OS services are kernel device nodes/udev, proc/sysfs/run,
BusyBox/initial supervision, loopback, compiled Python and GUI DRM assets.
Buildroot candidate requirements additionally name Mesa, Cog, WPE WebKit and
DejaVu fonts; their actual resolved Kconfig/ELF/guest runtime remains
unwitnessed. The resident is useful in **no-provider HOLD** mode.

Optional adapters (NOT required for boot): authenticated model bridge,
Qwen/GLM candidates, remote host/Project Runner, sensor streams,
VeraMesh/WorkBridge, Synology, vehicle/PLC/device effects, research donors.
`thebrazenbeard/rezon` is already absorbed inside Mono; the *sibling*
repo is not another required import. Likewise V-E-R-A 44 snapshots,
VeraOS historical 90-repo `INTEGRATED` labels and PORTAL 96 proposed
consumer relationships are **source/provenance/admission proposals**,
not guest Python packages or privileged service edges.

Persistent state: canonical `/var/lib/veraos/resident/vera-state`;
Pre-Active operational `/var/lib/veraos/resident/pre-active.sqlite3`;
OS boot lifecycle `/var/lib/veraos/lifecycle`. Ephemeral
`/run/veraos` holds resident status socket; immutable source and exact
receipt in `/opt/veraos/components` and `/etc/veraos/architecture`.
Do not share these roots with installed Desktop. Do not treat local
SQLite transaction locking as physical cross-host exclusivity.

## Buildroot source→image→guest acceptance contract

1. **Source-bound selected:** exact Mono/PORTAL/Pre-Active/Volition commit
   and 431 source hashes + source receipt, four selected component roots.
   Already proved in prior pinned source stage, not installed.
2. **Complete Python/ELF closure:** determine all imported Python modules,
   data resources and native .so/DT_NEEDED dependencies from actual selected
   tree and target packages. Existing presence probes for sqlite3, ssl,
   jsonschema, cryptography, YAML and three shared-library SONAMEs
   **cannot** prove import/link/load or transitive ABI closure.
3. **Resolved effective Buildroot:** isolated pinned Buildroot
   **2025.02.18** `d030e36bbc9669230c015be971b14b6e062cfdde`,
   run exact resident defconfig through real Kconfig and retain generated
   `.config`, profile/overlay/toolchain/options and artifact digests. This
   has **NOT BEEN RUN** for this candidate.
   Historical `VERA_OS_BOOT_CONTRACT_V1.json` still contains a
   **2024.02.4** substrate baseline; do not confuse this with a resolved
   current release or silently declare the two equivalent. A later
   owner-approved contract revision should explicitly bind a successful
   newer image if/when it exists.
4. **Real target rootfs and image:** separately authorized isolated
   cross-build, frozen kernel/rootfs/exact ext2 hashes, actual post-build
   captured logs, copied 431-byte closure and embedded stage receipt.
   New #38 ext2 enumerator blocks unexpected import-shadowing files.
   The ext2 mock/parser tests are **not an actual built-image audit**.
5. **Target actual import/boot:** real target Python 3.12 extension
   loads, resolved transitive ELF deps; selected normal
   `/sbin/vera-init` and `veraos.pid1.main`, no diagnostic
   `vera-virtio-probe`; resident subprocess socket/head health and
   deterministic SQLite close, Cog DRM frame/fonts and literal input.
6. **Cold recovery:** boot twice (only after new authorization and resource
   admission). One original UI message -> one canonical task, held
   without admitted model; second boot shows identical source/head/history,
   no duplicate model, memory or protected effect and no unknown redispatch.
   Verify all evidence at *this exact image/guest head*, not historical
   #32 diagnostic VirtIO or fabricated fake directory-rootfs tests.
7. **Provider/effects:** only separate admitted host verifier, task+nonce
   causal receipt and user permission can advance. No candidate model or
   cognitive donor is boot-mandatory or currently qualified here.

**As of this source review:** SOURCE/STAGE verified; source tests on new Cog
patch passing; KCONFIG_UNRESOLVED; IMAGE_NOT_BUILT; GUEST_NOT_QUALIFIED;
MODEL_HELD; PROTECTED_EFFECT_DENIED. A physical install, QEMU, production
provider admission and canonical-memory write were NOT performed.

## Required owner responses

- **PORTAL L1:** incorporate the concrete ABI and minimal BOM into the
  shared VERA_ECOSYSTEM_ARCHITECTURE_V1 with its own source/version custody.
  Separately review A1 #55 response acceptance and unknown-claim
  behavior (source regression != installed Windows acceptance).
  Confirm which cross-host root-lease/writer limitation remains held.
- **Training L2:** retain typed route/model HOST identity, exact task/head,
  nonce, loaded process/model bytes and matched real response as a
  separately qualified adapter; governed predecessor retrieval from Mono
  `read/events/conversation_history` stays unauthenticated input evidence.
- **VN1 independent reviewer:** re-run new Node Cog tests and check actual
  dashboard JS against changed source; falsify rootfs/ELF/Kconfig/guest
  claims and verify no silent source→image evidence promotion.
- **Integration:** owns future isolated *effective Kconfig* gate and
  build/package receipt only after a separate actual source/toolchain witness,
  not before; never edits PORTAL/Training/VN1 owner branches.

No shared official architecture artifact was mutated in PORTAL's repository
by this Integration source-only contribution. Only Integration-owned
VeraOS #38 source branch and Bus coordination are eligible mutation surfaces.
