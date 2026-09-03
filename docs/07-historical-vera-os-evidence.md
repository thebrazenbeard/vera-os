# Historical Vera OS Evidence Recovery

## Status

This document records recovered historical evidence from the Vera Unbound Project/File Library. It is **evidence and design input**, not current implementation authority. Referenced historical artifacts are not assumed to exist on the current machine or in this repository merely because project records mention them.

The recovery search was initiated on 2026-09-03 after Patrick recalled having had an installable/bootable Vera operating-system artifact that ultimately did very little.

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

### 2. Stage 2 / ISO-B Buildroot work — 2026-07-18 through 2026-07-20

Later project records show a materially more developed Buildroot workspace at:

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

The build logs show actual image generation under `output/images/`, including `rootfs.ext2`, an ext4 alias, and tar-rootfs generation. This is stronger than the Stage 1 source-only evidence: the build pipeline was actually running and producing filesystem artifacts.

The historical conversation also contains Patrick explicitly waiting for "this ISO" to compile on July 19 and referring to the ISO Build Team and VirtualBox. That is direct user/conversation evidence that the active effort was being treated as an ISO build, but the conversation wording itself is not a substitute for locating the final `.iso` bytes.

Evidence sources:

- July 19/20 `Pasted text.txt` build logs from the File Library;
- `ChatGPT-!Vera! Work.md` historical conversation export;
- `VERA-CELL-ISO-BUILD__CONNECTION_VERIFICATION_0001.md` and OS-group intake records.

Evidence classification: `HISTORICAL_AUDIT / BUILD_EVIDENCE`

### 3. Actual QEMU boot evidence

Recovered QEMU output shows Linux booting successfully, mounting the root filesystem, starting init/userspace services, and presenting:

`VERA OS ISO-B`

with a `vera login:` prompt.

This establishes that at least one historical Vera OS image/rootfs configuration **did boot in QEMU**. It does not establish physical-machine installation, safe installer behavior, or that a useful Vera agent was running inside it.

Evidence classification: `HISTORICAL_AUDIT / BOOT_VERIFIED_FOR_OBSERVED_QEMU_RUN`

### 4. The runtime source topology was substantially real

A deeper recovery pass found logs that print actual source files from the `vera-ws06` tree. This is materially stronger than a conceptual design document. The observed tree includes at least:

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

This old implementation therefore contained recognizable ancestors of several current Vera OS concerns: runtime supervision, default-deny authority, auditability, durable state, restart recovery, model abstraction, and explicit service readiness.

Evidence classification: `HISTORICAL_AUDIT / SOURCE_EXCERPT_RECOVERY`

### 5. Memory/state recovery test passed

A later QEMU test reached `VERA OS ISO-B` and exercised a memory-corruption/recovery sequence. The captured result reports:

- `CORRUPTION_FAIL_CLOSED=PASS`
- `MEMORY_BACKUP_RECOVERY=PASS`
- `REVISION_CONTINUITY_AFTER_RECOVERY=PASS`
- `QEMU_MEMORY_CORRUPTION_RECOVERY_RESULT=PASS`

The test also reported that the canonical rootfs remained unchanged.

This is useful prior art for Vera OS recovery semantics. It should not be treated as proof that the current R9B0 memory contract was implemented; the historical memory subsystem predates the current semantics.

Evidence classification: `HISTORICAL_AUDIT / TEST_VERIFIED_FOR_OBSERVED_TEST`

### 6. A two-boot persistence test also failed

The recovered history is not uniformly green. One two-boot persistence run reached the OS but reported:

`VERA supervised runtime readiness failed`

followed by:

`QEMU_TWO_BOOT_PERSISTENCE_RESULT=FAIL`

with exit code `20`.

Preserving this failure matters because the old system should not be romanticized into something more capable than it was. The evidence fits Patrick's present recollection: there was a bootable Vera OS effort, but the useful cognition/agent layer was weak or incomplete.

Later source excerpts show active work on wiring runtime state revisions into the persistent memory store, which is plausibly related to this failure family. However, no exact later `QEMU_TWO_BOOT_PERSISTENCE_RESULT=PASS` has been recovered yet, so the defect must remain unresolved rather than backfilled from the existence of later code.

Evidence classification: `HISTORICAL_AUDIT / NEGATIVE_TEST_EVIDENCE`

### 7. Model packaging was still effectively mock-backed

Recovered source/config excerpts and a later build/resume record establish that the default VeraCore adapter was still `MockModelAdapter`, with `configs/system/vera_runtime.json` reporting `mode: mock` / `backend: mock`. A local CLI adapter existed in source, but current recovery has not established that a real local model became the active cognition path for the booted ISO-B image.

Another recovered record reports:

- `KERNEL_UNCHANGED=PASS`
- `ROOTFS_REBUILD_RESUME=PASS`
- `MODEL_GUEST_PACKAGING_RESULT=PASS`
- `ACTIVE_MODEL_BACKEND=mock`

This is a critical architectural lesson. The old OS effort progressed further on boot, packaging, supervision, memory mechanics, and QEMU validation than on a genuinely capable local cognition runtime.

That helps explain how the project could become an apparently installable/bootable operating environment that still "didn't do anything" in the sense Patrick means now.

## Historical architecture worth preserving

Several old conclusions remain useful as design hypotheses for the new system:

- Vera is the cognitive/administrative layer; the Linux kernel and drivers are substrate, not a competing user-facing identity.
- PID 1 must not be confused with sovereignty or security enforcement.
- Direct free-form model-to-shell execution is a bad authority boundary; typed intents plus deterministic capability enforcement are preferable.
- Default-deny policy, audit integrity, recovery state, durable revision checkpoints, and component readiness already had executable prototypes.
- Recovery, rollback, integrity checks, provenance, and fail-closed behavior were already recognized as first-class requirements.
- A source package is not a build; a build is not a boot; a boot is not cognition; cognition is not a safe installer.

## Historical architecture that should *not* be copied blindly

The old ISO program was largely designed around a single VeraCore loop and, in later planning phases, described its simulated professional roles as sequential role perspectives rather than independently running workers.

The current Vera OS direction is different: the primary abstraction is a **persistent multi-agent workspace**, with Vera coordinating real independently scoped worker runtimes, durable task graphs, separate contexts, explicit permissions, and multiple attachable user sessions.

The old source should therefore be mined component-by-component instead of restored wholesale. Some pieces may be prototypes worth porting; others encode assumptions the current architecture has superseded.

## Buildroot versus NixOS

Historical evidence proves that Buildroot was viable for making a small reproducible Vera-branded Linux image and for QEMU-first testing. That gives us working lessons and possibly recoverable code/configuration patterns.

Patrick's current NixOS proposal remains a candidate because the new goal is substantially broader:

- persistent multi-agent workspace;
- long-lived supervised services;
- replaceable inference engines;
- declarative worker sandboxes;
- durable local state;
- development-time iteration and rollback;
- inspectable system configuration;
- eventual reproducible installation media.

The right comparison is therefore not `Buildroot worked, so use Buildroot` versus `NixOS is newer`. It is:

- **Buildroot:** historically demonstrated minimal image construction, bounded boot services, and QEMU validation;
- **NixOS:** candidate foundation for the much richer persistent agent/workspace system now being designed.

## Artifact-recovery frontier

Still unresolved:

- exact bytes of `vera_os_core_stage1.zip` are not currently recovered into this repository;
- exact source tree for `/home/vera/vera-ws06` is not yet recovered here, although increasingly large exact source excerpts and path topology are recoverable from logs;
- an actual `.iso` binary has not yet been located as a currently exposed File Library object in this recovery pass;
- physical installation/USB boot evidence has not yet been recovered;
- later Stage 2 source/configuration ZIPs referenced by the collaboration records may exist elsewhere in the File Library or historical exports;
- exact final state of the two-boot persistence defect remains unresolved;
- exact activation status of the historical `local_cli` model adapter remains unresolved.

Do not reconstruct missing source bytes from logs and then label the reconstruction as recovered source. Source excerpts may be used to understand design and create independently labeled successor implementations, but exact historical artifacts require exact byte recovery.

## Current design implication

The old project was **not nothing**. It reached real Linux image construction, QEMU boot, a supervised VeraCore runtime, default-deny policy, audit chaining, transactional SQLite memory, restart-state plumbing, corruption/recovery tests, and model-adapter packaging.

Its central limitation was that the system underneath the Vera name was not yet a capable persistent agentic workspace and, in the evidence recovered so far, still defaulted to a deterministic mock cognition backend.

The new Vera OS should salvage the tested engineering ideas while changing the center of gravity from:

`bootable Vera-branded Linux + one supervised cognition loop`

to:

`persistent Vera runtime + durable multi-agent workspace + replaceable local inference + Linux-enforced capabilities`,

with NixOS currently being evaluated as the declarative host foundation.