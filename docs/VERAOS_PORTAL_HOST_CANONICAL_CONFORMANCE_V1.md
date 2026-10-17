# PORTAL Desktop and VeraOS canonical-runtime source conformance

2026-10-17. SOURCE and simulated PACKAGE evidence only; no installed-host
migration, guest/QEMU, model admission, trust, memory or effect authorization.

## Actual PORTAL Desktop source readback, separate owner

Read-only Windows process inspection found an existing parent/child
python -m portal.desktop_host runtime at
%LOCALAPPDATA%/VeraDesktopRuntime/20261015-4d5e793.
Installed portal.desktop_host imports VeraStateDirectory and
QualifiedVeraRuntime from vera_core and calls from_state_directory().
It also owns PortalCommandSession, Pre-Active Store, and a separate
CognitionLedger/VeraRuntimeAcceptance source path.

INSTALLED (NOT upgraded): Mono e5af8cb740267bb5674864571e915842bf5e6677
and PORTAL 4d5e79314378e6aca1088afe1e04d6d9ee8c423f.
Installed Pre-Active 1f23a809d7274df506e03e2d9052525538c3bcf6
and Volition dbc628d376515a0a523b1eecdf62129cca5d6b08.
Installed Desktop state root is state_root/vera, with project_id VERA_MONO,
identity_id VERA_PROJECT_IDENTITY_V1. Resident #38 uses
state_root/vera-state, project_id veraos, identity_id VERA.
The two roots and logical identities MUST NOT silently merge.
The installed host has a Windows named mutex per runtime ID; neither
that mutex nor task-scoped SQLite transaction serialization proves one
exclusive owner for a mixed host/guest state root.

PORTAL-owned host adaptation of Mono #77 open_message, or any live source
refresh/migration, requires PORTAL review and separate deployment authority.
The current live Desktop was NOT touched by these tests or changes.

## Exact fresh remote source and package reproduction

Selected Mono #77: 89ba1d18da78e7e38f015cf8d8ef4f528aae9df8.
Selected PORTAL #51: 36fa04da4e5eb383fecf463c72a43b94ca47d7e5.
Selected Pre-Active: 1f23a809d7274df506e03e2d9052525538c3bcf6.
Selected Volition: dbc628d376515a0a523b1eecdf62129cca5d6b08.

Fresh detached GitHub clones:
D:\VERA\veraos-independent-source-20261017-v2\checkouts
Fresh exact Git archive stage:
D:\VERA\veraos-independent-source-20261017-v2\stage
Source receipt SHA256:
6f0031c1fcbaed41e4e3f6947e90a92ed5656ac3e09329de7d8e0b0f8417eca5
Counts: Mono 316, PORTAL 89, Pre-Active 18, Volition 8 source files.
Stage and subsequent verification exit 0, all required module files present.
No stage is an installed guest; generated Python __pycache__ contaminates
an exact source receipt, so use PYTHONDONTWRITEBYTECODE=1.

Pinned Buildroot 2025.02.18 annotated tag object
b611e07ef088c70c1e21f77c30872bce97a1f1c2,
peeled commit d030e36bbc9669230c015be971b14b6e062cfdde,
fresh sparse checkout D:\VERA\veraos-buildroot-2025.02.18-probe.
Source probe passed PINNED_SOURCE_SYMBOLS_VERIFIED_KCONFIG_NOT_RUN:
target Python 3.12.14, jsonschema 4.23.0, cryptography 44.0.1,
PyYAML 6.0.2; selected SQLite and SSL Python feature flags,
Cog DRM/WPE WebKit/Mesa and DejaVu Sans declarations.
Kconfig dependency resolution, compiled target imports, graphical
renderer/font loading, real browser, PID1, guest image and two boots
remain unverified. No Buildroot image was built.

## Executable tests and owner boundaries

Host/resident source conformance:
tests/test_host_resident_runtime_conformance.py.
Uses actual QualifiedVeraRuntime.from_state_directory and actual resident
compose_components in one explicitly shared disposable state root; one
message/task/digest, no-provider HTTP202 HOLD, literal replay and refusal
of altered text, cross-process duplicate refusal, independent SQLite
task write serialization/release, bounded cold history, separate actual
Desktop identity-root demonstration and no memory promotion. This does
not execute the currently running installed PORTAL Desktop.

Simulated PACKAGE verification:
tests/test_real_staged_resident_package.py.
Copies all exact source bytes and receipt into disposable directory-rootfs
layout, calls existing Verify-VeraOSResidentFiles.py, rejects mutated
Mono code, absent PORTAL module, and altered receipt. Not a built rootfs.

Windows resource leak RED: 20/23 persistent files locked after closing
resident, strong runtime references held, no gc.collect, temporary
directory cannot be removed. Source fix updates original SQLite-owner
transaction scopes in Mono packages; GREEN now 23/23 rename/readback
with cold reopen and strong object references. No extra state backend,
no global sqlite monkeypatch and no new runtime controller.

SOURCE/PACKAGE/GUEST acceptance:
- SOURCE: exact pinned modules and task semantics PASS
- WIN32: 23/23 composed SQLite resource release PASS
- PACKAGE-SOURCE: exact 431-file archive SHA/receipt PASS
- PACKAGE DIRECTORY ROOTFS: exact hash audit PASS (simulated)
- TARGET PYTHON / BUILDROOT SOURCE SYMBOLS: PASS, Kconfig NOT run
- BUILDROOT IMAGE: UNKNOWN, not built
- GUEST/GRAPHICAL/COG/PID1: UNKNOWN, not run
- REAL MODEL ADMISSION: HELD pending Training task-head/nonce/host proof
- INSTALLED DESKTOP SOURCE MIGRATION / SHARED ROOT WRITER: HELD
- CANONICAL MEMORY / PROTECTED EFFECTS: HELD

Existing PORTAL #37 event DONE and run COMPLETED contradiction handling
and supervisor-health source behavior remain semantically reconciled in
VeraOS #38. No PORTAL branch, installed runtime, Supabase, Drive,
Synology or separate evidence provider was modified. No external
provider becomes a boot or memory dependency by mere presence.
