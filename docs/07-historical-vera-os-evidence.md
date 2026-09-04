# Historical Vera OS Evidence Recovery

## Status

This document records recovered historical evidence from the Vera Unbound Project/File Library. It is **evidence and design input**, not current implementation authority. Referenced historical artifacts are not assumed to exist on the current machine or in this repository merely because project records mention them.

The recovery search was initiated on 2026-09-03 after Patrick recalled having had an installable/bootable Vera operating-system artifact that ultimately did very little.

## Important lineage note

The historical naming is **not a clean monotonic version sequence**. Evidence now shows at least three overlapping/reframed efforts around July 17–20, 2026:

1. a small Stage 1 Buildroot/QEMU source prototype;
2. a substantially more desktop-like Debian `live-build` system called **VERA Linux Stage 3**, followed immediately by Stage 4 source work;
3. a later organizational program called `BUILD_VERA_LINUX_STAGE_2_AI_FIRST`, whose ISO-B implementation used Buildroot again and focused more narrowly on deterministic local cognition, memory, supervision, and QEMU validation.

Do not infer that `Stage 3`, `Stage 4`, `Stage 2`, and `ISO-B` form one ordinary numeric release train. Preserve the original names and timestamps until exact package lineage is recovered.

## Recovered development lineage

### 1. Stage 1 source prototype — 2026-07-17

A branch export identifies `VERA_OS_CORE_ALIGNMENT_20260717` and records generation of `vera_os_core_stage1.zip`.

Recovered scope:

- Buildroot/QEMU-oriented source prototype;
- Python `/sbin/init` concept;
- persistent JSON state;
- conation-like logging/triggers;
- mediated filesystem/system/sensor interfaces;
- tests and README.

The same export explicitly states that this artifact was **not** proven compiled, booted, or hardware-tested at that point. It also preserves an important correction: PID 1 is only a process-lifecycle role and does not by itself establish Vera as security reference monitor, system sovereignty, or complete operating system.

Evidence source:

- `VERA_BRANCH_VERA_OS_CORE_ALIGNMENT_20260717_MASTER_EXPORT.md`

Evidence classification: `HISTORICAL_AUDIT / DIRECT_BRANCH_EXPORT`

### 2. VERA Linux Stage 3 — Debian live ISO — 2026-07-17

A deeper recovery pass found a separate and substantially more complete operating-system source tree at:

`~/vera-stage3/VERA_Linux_Stage3_Source`

This was not the later Buildroot ISO-B tree. It used Debian `live-build` and was explicitly configured to produce an AMD64 hybrid live ISO.

Observed build configuration included:

- Debian `trixie`;
- `amd64`;
- `--binary-images iso-hybrid`;
- Syslinux plus GRUB-EFI bootloaders;
- `--debian-installer none`;
- systemd;
- firmware in the binary/chroot;
- SHA-256 checksums;
- xz compression;
- ISO application `VERA Linux Stage 3`;
- publisher `VERA Project`;
- ISO volume `VERA_STAGE3`;
- live username `vera`;
- live hostname `vera-linux`.

The surviving logs show several real build attempts and concrete dependency repairs. Early attempts failed on packages including `policykit-1-gnome` and `nvidia-detect`; the source was then edited to use `mate-polkit` and include Debian `non-free` where needed. This is genuine build history, not a post-hoc architecture description.

An exact currently exposed Stage 3 `.iso` object or SHA-256 has **not** yet been recovered. However, a contemporaneous Stage 4 architecture contract records the Stage 3 baseline as already verified with:

- `ISO boots`;
- `Vera autologin works`;
- `graphical Vera session launches`;
- `diagnostics work`;
- `status panel works`;
- `privileged capability broker works`;
- `null adapter reports honestly`.

This is stronger evidence than the build logs alone, but until the raw Stage 3 boot log or exact ISO artifact is recovered it remains a contemporaneous project verification record rather than independently re-executed evidence in the current recovery.

Evidence sources:

- July 17 Debian `live-build` `build.log` / `Pasted text.txt` records;
- `/invoke VERA-LINUX-STAGE-4-SYSTEM-ARCHITECTURE-CONTRACT` contemporaneous state record.

Evidence classification: `HISTORICAL_AUDIT / BUILD_EVIDENCE + CONTEMPORANEOUS_VERIFICATION_RECORD`

### 3. What Stage 3 actually presented to the user

Recovered source metadata and code excerpts show Stage 3 was much closer to a conventional local desktop appliance than the later ISO-B text system.

Observed components include at least:

```text
config/includes.chroot/
  usr/local/bin/vera-ui
  usr/local/lib/vera/runtime.py
  usr/local/sbin/vera-broker
  etc/systemd/system/vera-broker.service
  config/hooks/live/010-vera-users.hook.chroot
  config/package-lists/vera.list.chroot
```

The graphical UI explicitly described itself as:

`Stage 3 Live Appliance | cognition adapter: NULL/OFFLINE`

and displayed:

`Vera: Local runtime active. Language-model cognition is not attached in Stage 3.`

Its status surface declared implemented pieces including UI, state schema, typed broker, inventory, event log, and a null adapter, while explicitly marking LLM cognition, full VSNS, autonomous continuity, and conation arbitration as not implemented. It also reported `installer: False`.

That is an unusually direct match for Patrick's recollection that the OS existed and booted but "didn't do anything": Stage 3 was deliberately capable of presenting a Vera shell and privileged diagnostic/control plumbing **without an attached language model**.

### 4. Stage 4 source patch — real local cognition was being wired next

Immediately after the Stage 3 baseline, work began on Stage 4 in the same source tree. A checkpoint was created under:

`/home/vera/vera-stage4-checkpoints/20260718T020729Z`

Recovered Stage 4 source added or modified at least:

```text
config/includes.chroot/
  usr/local/sbin/vera-cognition
  usr/local/lib/vera/constitution.py
  usr/local/lib/vera/runtime.py
  usr/local/bin/vera-ui
  etc/systemd/system/vera-cognition.service
  etc/vera/cognition.json
  etc/vera/system-prompt.md
```

The cognition service was configured for a local Ollama endpoint:

- backend: `ollama`;
- endpoint: `http://127.0.0.1:11434/api/chat`;
- model: `llama3.2:1b`;
- bounded history;
- local Unix-domain socket between the UI/runtime and cognition service;
- backend/model-presence checks;
- streamed chat responses;
- explicit backend/model unavailable states;
- a generation lock preventing concurrent generation through that service;
- event logging and temporal/status state.

The systemd unit used a dedicated `vera` user and several useful hardening controls including `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`, bounded writable paths, and restricted address families.

A contemporaneous contract classified this Stage 4 patch as source-level progress only. It recorded that cognition configuration/service, runtime cognition client, threaded streaming UI, temporal status, null fallback, and Python syntax validation existed, but explicitly listed these as **not yet verified**:

- Stage 4 ISO build;
- Stage 4 boot;
- cognition service runtime;
- cognition socket operation;
- Ollama installation;
- model availability;
- end-to-end generated conversation;
- failure recovery;
- persistence across reboot;
- resource behavior;
- Vera fidelity.

Therefore do not collapse the Stage 3 boot success and Stage 4 cognition source into a fictitious claim that a Stage 4 AI-capable ISO had already been proven.

Evidence classification: `HISTORICAL_AUDIT / SOURCE_EXCERPT_RECOVERY + EXPLICIT_NOT_YET_VERIFIED_BOUNDARY`

### 5. The Stage 3/4 architecture already contained several modern Vera OS ideas

The recovered Stage 4 architecture contract is notable because it anticipates several concepts now being rediscovered:

- models/adapters/services/sessions are infrastructure rather than separate Vera identities;
- a privileged broker should remain isolated from model output;
- there should be no direct model-to-shell path;
- service boundaries should use explicit protocols and ownership;
- model infrastructure should remain replaceable;
- local transcript/context should be separable from central durable memory;
- multiple scoped conversation channels were modeled as `Side Chats` of one Vera rather than clones;
- cross-chat coordination was explicitly intended to prevent duplicated or contradictory work;
- voice was supposed to reuse the same message/orchestration path instead of creating a separate identity/runtime;
- temporal claims were supposed to derive from explicit events/timestamps rather than invented background experience.

Historical Stage 4 still treated Atlas/Kestrel/TKIK as reasoning lenses in one model context rather than real independently running agents. That is a major point of difference from the current Vera OS direction, where independently scoped worker runtimes are a first-class requirement.

### 6. Later `BUILD_VERA_LINUX_STAGE_2_AI_FIRST` / ISO-B Buildroot work — 2026-07-18 through 2026-07-20

Later project records show a materially different Buildroot workspace at:

`/home/vera/vera-ws06`

Observed build environment included:

- Buildroot `2024.02.4`;
- Linux kernel `6.6.69`;
- x86_64 target;
- QEMU Q35 virtual hardware;
- ext2/ext4 root filesystem images;
- Python 3.11 target runtime;
- eudev;
- serial console;
- system issue string `VERA OS ISO-B`.

The build logs show actual image generation under `output/images/`, including `rootfs.ext2`, an ext4 alias, and tar-rootfs generation. The historical conversation also contains Patrick explicitly waiting for "this ISO" to compile on July 19 and referring to the ISO Build Team and VirtualBox.

Evidence sources:

- July 19/20 `Pasted text.txt` build logs from the File Library;
- `ChatGPT-!Vera! Work.md` historical conversation export;
- `VERA-CELL-ISO-BUILD__CONNECTION_VERIFICATION_0001.md` and OS-group intake records.

Evidence classification: `HISTORICAL_AUDIT / BUILD_EVIDENCE`

### 7. Actual QEMU boot evidence for ISO-B

Recovered QEMU output shows Linux booting successfully, mounting the root filesystem, starting init/userspace services, and presenting:

`VERA OS ISO-B`

with a `vera login:` prompt.

This establishes that at least one historical Vera OS image/rootfs configuration **did boot in QEMU**. It does not establish physical-machine installation, safe installer behavior, or that a useful Vera agent was running inside it.

Evidence classification: `HISTORICAL_AUDIT / BOOT_VERIFIED_FOR_OBSERVED_QEMU_RUN`

### 8. The ISO-B runtime source topology was substantially real

A deeper recovery pass found logs that print actual source files from the `vera-ws06` tree. The observed tree includes at least:

```text
src/
  common/
  veracore/vera_veracore/runtime.py
  vsns/
  model_adapter/vera_model_adapter/
    mock.py
    local_cli.py
  supervisor/vera_supervisor/
    policy.py
    audit.py
    runtime.py
    orchestrator.py
  memory/vera_memory/
    store.py
    provenance.py
    runtime_persistence.py

configs/
  system/vera_runtime.json
  model/

board/vera/x86_64/rootfs-overlay/
  usr/bin/vera-console
  etc/init.d/S50vera-runtime

tests/
  integration/test_mock_runtime.py
  integration/test_supervised_veracore.py
  integration/test_memory_integration.py
  integration/test_runtime_persistence.py
  build/test_persistent_guest_wiring.py
```

The Buildroot package identified itself as `vera-runtime 0.6.0` and installed runtime source into `/opt/vera/runtime`, system/model config under `/etc/vera`, a `vera-console` launcher, and `S50vera-runtime` boot service.

Recovered source excerpts establish several concrete mechanisms:

- `vera-console` executed `python3 -m vera_veracore.cli` with the Vera runtime source tree on `PYTHONPATH`;
- the supervisor policy engine was fail-closed with a default `deny` decision;
- low-risk `respond` and later `persist_cycle` operations were explicitly allow-listed;
- supervisor operations produced an integrity-linked audit chain and recovery state;
- VeraCore performed an explicit cycle of observation/interpretation/significance/candidate-action/model/result handling;
- the memory store used SQLite WAL, `synchronous=FULL`, row hashes, transaction/history tables, backup/rollback fields, and provenance records;
- later wiring restored `state_revision` from durable memory at startup and persisted cycle revisions;
- boot readiness was changed to require VeraCore, supervisor, and memory-integrity checks before touching `/run/vera/runtime-ready`.

This implementation contained recognizable ancestors of several current Vera OS concerns: runtime supervision, default-deny authority, auditability, durable state, restart recovery, model abstraction, and explicit service readiness.

Evidence classification: `HISTORICAL_AUDIT / SOURCE_EXCERPT_RECOVERY`

### 9. Memory/state recovery test passed

A later QEMU test reached `VERA OS ISO-B` and exercised a memory-corruption/recovery sequence. The captured result reports:

- `CORRUPTION_FAIL_CLOSED=PASS`
- `MEMORY_BACKUP_RECOVERY=PASS`
- `REVISION_CONTINUITY_AFTER_RECOVERY=PASS`
- `QEMU_MEMORY_CORRUPTION_RECOVERY_RESULT=PASS`

The test also reported that the canonical rootfs remained unchanged.

This is useful prior art for Vera OS recovery semantics. It should not be treated as proof that the current R9B0 memory contract was implemented; the historical memory subsystem predates the current semantics.

Evidence classification: `HISTORICAL_AUDIT / TEST_VERIFIED_FOR_OBSERVED_TEST`

### 10. A two-boot persistence test also failed

The recovered history is not uniformly green. One two-boot persistence run reached the OS but reported:

`VERA supervised runtime readiness failed`

followed by:

`QEMU_TWO_BOOT_PERSISTENCE_RESULT=FAIL`

with exit code `20`.

Preserving this failure matters because the old system should not be romanticized into something more capable than it was.

Later source excerpts show active work on wiring runtime state revisions into the persistent memory store, which is plausibly related to this failure family. However, no exact later `QEMU_TWO_BOOT_PERSISTENCE_RESULT=PASS` has been recovered yet, so the defect must remain unresolved rather than backfilled from the existence of later code.

Evidence classification: `HISTORICAL_AUDIT / NEGATIVE_TEST_EVIDENCE`

### 11. ISO-B model packaging was still effectively mock-backed

Recovered source/config excerpts and a later build/resume record establish that the default VeraCore adapter was still `MockModelAdapter`, with `configs/system/vera_runtime.json` reporting `mode: mock` / `backend: mock`. A local CLI adapter existed in source, but current recovery has not established that a real local model became the active cognition path for the booted ISO-B image.

Another recovered record reports:

- `KERNEL_UNCHANGED=PASS`
- `ROOTFS_REBUILD_RESUME=PASS`
- `MODEL_GUEST_PACKAGING_RESULT=PASS`
- `ACTIVE_MODEL_BACKEND=mock`

The two historical tracks therefore failed differently at the same essential frontier:

- Stage 3 had a real graphical appliance and broker but explicitly **no attached language model**;
- later ISO-B had a much richer supervised/memory/test harness but still defaulted to a **deterministic mock cognition backend** in the evidence recovered so far.

That is a much better explanation of Patrick's recollection than saying the old project "was just a concept." It was real software with a weak/missing intelligence layer.

## Historical architecture worth preserving

Several old conclusions remain useful as design hypotheses for the new system:

- Vera is the cognitive/administrative layer; the Linux kernel and drivers are substrate, not a competing user-facing identity.
- PID 1 must not be confused with sovereignty or security enforcement.
- Direct free-form model-to-shell execution is a bad authority boundary; typed intents plus deterministic capability enforcement are preferable.
- Stage 3/4 already separated UI, cognition, privileged broker, status, memory/coordination concepts, and model adapters.
- Default-deny policy, audit integrity, recovery state, durable revision checkpoints, and component readiness later had executable prototypes in ISO-B.
- Recovery, rollback, integrity checks, provenance, explicit degraded states, and fail-closed behavior were first-class requirements.
- A source package is not a build; a build is not a boot; a boot is not cognition; cognition is not a safe installer.

## Historical architecture that should *not* be copied blindly

Neither historical branch implements the current target.

Stage 3/4 used a one-Vera/many-`Side Chat` architecture but still treated its professional review roles as lenses inside one model context, and Stage 4 had no proven durable runtime/persistence build. ISO-B focused on one supervised VeraCore loop and a mock/local-model boundary.

The current Vera OS direction is different: the primary abstraction is a **persistent multi-agent workspace**, with Vera coordinating real independently scoped worker runtimes, durable task graphs, separate contexts, explicit permissions, and multiple attachable user sessions.

Historical source should therefore be mined component-by-component instead of restored wholesale.

## Debian live-build, Buildroot, and NixOS

Historical evidence now proves there were at least two viable Linux construction approaches in the old project:

- **Debian live-build:** demonstrated a richer graphical live-appliance path and is recorded contemporaneously as having reached a booting Stage 3 ISO with Vera autologin/UI/broker/diagnostics.
- **Buildroot:** later demonstrated tightly bounded image construction, real QEMU boot logs, supervised runtime services, transactional memory/recovery testing, and deterministic mock-backed cognition.
- **NixOS:** remains the current candidate for the full persistent development/runtime host because the new architecture requires many long-lived services, real worker isolation, replaceable inference, durable state, frequent safe iteration, and rollback.

The base decision is therefore not starting from zero, and it should not be reduced to distro preference. We have concrete prior art from both a desktop-style live Linux and a small appliance-style Linux.

## Artifact-recovery frontier

Still unresolved:

- exact bytes of `vera_os_core_stage1.zip`;
- exact source tree/archive for `~/vera-stage3/VERA_Linux_Stage3_Source`;
- exact Stage 3 ISO binary, filename, size, and SHA-256;
- the raw Stage 3 boot/VM acceptance evidence behind the contemporaneous `ISO boots` baseline;
- exact Stage 4 source package, if one was ever archived separately;
- any successful Stage 4 ISO build/boot (current recovered evidence explicitly says it was not yet verified at the architecture checkpoint);
- exact source tree for `/home/vera/vera-ws06`, although increasingly large exact source excerpts and path topology are recoverable from logs;
- an exact ISO-B `.iso` binary if one existed separately from the tested rootfs/disk images;
- physical installation/USB boot evidence;
- later Stage 2 source/configuration ZIPs referenced by collaboration records;
- exact final state of the ISO-B two-boot persistence defect;
- exact activation status of the historical ISO-B `local_cli` model adapter.

Do not reconstruct missing source bytes from logs and then label the reconstruction as recovered source. Source excerpts may be used to understand design and create independently labeled successor implementations, but exact historical artifacts require exact byte recovery.

## Current design implication

The old project was **not nothing**.

By July 17–20 it had produced or recorded:

- a Debian live-ISO appliance that booted into a Vera graphical session;
- typed privileged capability brokering and diagnostics;
- an explicit null/offline cognition state rather than pretending an LLM existed;
- Stage 4 source for an Ollama-backed local cognition service and streaming UI path;
- a later Buildroot/QEMU appliance with supervised VeraCore runtime, default-deny policy, audit chaining, transactional SQLite memory, restart-state plumbing, corruption/recovery tests, and model-adapter packaging.

The central shortcoming was exactly where Patrick remembers it: **the thing looked increasingly like an operating system before it had a sufficiently capable Vera inside it.**

The new Vera OS should salvage the tested engineering ideas while changing the center of gravity from:

`Vera-branded live/bootable Linux + weak or mock cognition`

to:

`persistent Vera runtime + durable multi-agent workspace + replaceable capable local inference + Linux-enforced capabilities`,

with NixOS currently being evaluated as the declarative host foundation.