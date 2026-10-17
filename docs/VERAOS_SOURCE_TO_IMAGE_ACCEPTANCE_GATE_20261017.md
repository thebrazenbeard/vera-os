# Integration L1/L2 — canonical source to real VeraOS image gate, 2026-10-17

**Result: NOT_BUILT / NOT_GUEST_QUALIFIED / NOT_READY_KCONFIG_UNRESOLVED.**
This source-only audit increment is subordinate to VeraOS owner PR #38, not a
Buildroot build instruction, actual image acceptance, model admission or boot.

## Frozen source subjects

VeraOS PR #38 before this change: 46152a55393642ed2fc614abf177d6c2572a36c5.
Mono #77: 89ba1d18da78e7e38f015cf8d8ef4f528aae9df8 (316 files).
PORTAL #51: 36fa04da4e5eb383fecf463c72a43b94ca47d7e5 (89).
Pre-Active: 1f23a809d7274df506e03e2d9052525538c3bcf6 (18).
Volition: dbc628d376515a0a523b1eecdf62129cca5d6b08 (8).
Four-source archive: 431 exact files, receipt SHA256
6f0031c1fcbaed41e4e3f6947e90a92ed5656ac3e09329de7d8e0b0f8417eca5.
Selected Buildroot annotated tag 2025.02.18,
peeled commit d030e36bbc9669230c015be971b14b6e062cfdde,
Python 3.12.14. The existing source-symbol probe has NOT run Kconfig.

## Exact missed image defect and source repair

Pre-patch Verify-VeraOSResidentFiles.py only examined extra import
files for DirectoryRootfs, not ExtRootfs. An ext2 image with all 431
expected matching files and one extra stale/import-shadowing module was
ACCEPTED because no ext2 child listing was inspected; a reader unable
to enumerate files was also ACCEPTED. Two new deliberate RED assertions
failed on the exact owner predecessor.

Current verifier requires an image reader to provide a complete
component_files() set: any missing enumerator or differing membership
is a hard integrity HOLD. Both DirectoryRootfs and ExtRootfs support it.
The new ExtRootfs reader recursively requests read-only debugfs
"ls -p /opt/veraos/components[/...]" listings, validates numeric
inode/uid/gid/size, octal types and safe component names, forbids
symlinks/devices/duplicate or malformed entries, and bounds depth,
file/directory count and output size. Unexpected files and missing
child directories block source/image admission before a PASS return.
Actual selected file bytes still require the pre-existing sha256 checks.
Directory enumeration also refuses symlinks and special nodes.

The chosen debugfs -p wire shape is /inode/mode/uid/gid/name/size/.
Exact source: e2fsprogs debugfs(8) ls -p directory listing description
and ext2/3 feature request #12. This is a strict offline parser.
There is NO debugfs executable on this Windows VN1 workstation.
New fake-debugfs protocol tests are not real image tests and were
never described as such. A real ext2 test must be witnessed on an
authorized Linux environment with debugfs and an independently
measured image hash, without changing any physical boot media.

## Actual source verification

Windows VN1 Python 3.13.15, six stdlib unittest suites:

- test_ext2_resident_tree_enumeration_unittest.py = 6 PASS;
  recursive set, unexpected import, malformed/missing/duplicate entries,
  unsupported inode, missing child, bounded output
- test_resident_all_file_audit.py = 12 PASS;
  includes two original RED → GREEN ext2 no-enumerator/orphan conditions
- test_resident_target_rootfs_preflight.py = 6 PASS
- test_resident_exact_stage_rootfs_unittest.py = 1 PASS;
  unchanged immutable VN1 stage input, disposable full copied 431-rootfs
- test_resident_real_buildroot_preflight_unittest.py = 3 PASS;
  pinned source and static missing Kconfig flags only
- test_source_only_discovery_gaps_unittest.py = 2 PASS

Total 30 PASS / 0 FAIL / 0 SKIP, with exact executable exit codes zero.
Python packages required for broad Mono/VeraOS pytest regressions are
not available in VN1's default interpreter, so this turn did NOT
re-run or requalify the broad suites.

## Next acceptance contract — never silently advance evidence class

1. Source: exact five Git subjects and 431-file stage receipt, readback
   and clean selected Buildroot source. **Source PASS**.
2. Effective Kconfig: separately authorize generating the exact
   Buildroot .config; compare resolved Kconfig symbols, toolchain,
   C++/glibc/Python 3.12 and all target runtime dependencies to
   selected defconfig; retain .config SHA, Kconfig log and effective
   package versions. **UNEXECUTED, NOT_READY**.
3. Buildroot output: authorized isolated build only, real kernel/rootfs
   artifact hashes and captured build provenance, no existing image
   overwritten. **NOT_BUILT**.
4. Real target filesystem: run all-431 image-byte verifier on ACTUAL
   built ext2 image using debugfs; require COMPLETE ext2 tree
   membership match and embedded receipt equal immutable stage bytes;
   record image SHA and image-to-build-source binding. **NOT TESTED**.
5. Actual target ABI: invoke compiled target Python under isolated
   guest and import jsonschema/cryptography/yaml/sqlite3/ssl,
   inspect ELF DT_NEEDED, soname resolution and transitive dependencies;
   static file presence is NOT enough. **NOT TESTED**.
6. Normal PID1 selection and UI: witness /sbin/vera-init and
   veraos.pid1.main, unique resident child and health, no-provider
   canonical task opener before source fixture, no fake completion,
   Cog DRM framebuffer with fonts, real text entry and returned HELD.
   Second cold boot must recover one canonical pending task and
   provenance without redispatch. **NO GUEST/GRAPHICS PASS**.
7. Model/trust/effects: require independent host-owned process/model
   manifest, task/current-head/session/nonce and source-result causal
   receipt, with explicit separate authorization; no provider now.
   **HOLD**.

No actual Buildroot image, ext2 or QEMU, real target import, model
execution, deployment or protected effects occurred here.

## Cross-host / source ownership

PORTAL Desktop #52 remains independent; Codex A1 return currently
only partial tests GREEN and four WinError5 os.link failures, with
uncommitted branch edits and no verified GREEN mergeable head.
Integration earlier ACKed that Mono #77 open_message accepts UI-owned
untrusted conversation_id and message_id=request_id, original exact
literal and task/CAS provenance. PORTAL owns GUI and transport fixes,
including narrower request_id grammar, selector persistence and
missing-locator BLOCK before routing. VeraOS uses a separate
(project_id, identity_id, state_root) and is NOT a shared SQLite
writer with Desktop. #37 PORTAL-owned supervisor source remains
untouched; #38 layers canonical intake and terminal event integrity
over bounded restart/health logic, without cherry-picking #37.

Training #106 latest source helper cognitive_governed_predecessor_v1.py
at source head b4d9d0c785b1cdd31d357dd0cebb89c0ec2b6bfe (same helper blob\nbef5cb9ff07455733494461fee49e5cd8634b36f) reads existing
Mono task ledger read/events and local_conversation.conversation_history
without opening new tasks or granting memory: same-conversation
source-head and original literal can be reconstructed as
UNAUTHENTICATED_USER_INPUT. No source API change required. Semantic
referent/scope mapping is caller-supplied, not attested by Mono;
missing predecessor stays HOLD. Training reported Lappy real-ledger
11 tests and frozen supported/adverse evaluation; it did NOT establish
authenticated loaded-model inference or memory admission.

PORTAL private consumer overlay #372 exact ef17ee929d807f5da033a3d5391d553b65c464e8
is a 96-repo *proposal*, not an executable resident dependency graph.
V-E-R-A 44 snapshots and historical 90-entry VeraOS catalog remain
source/provenance only. No new guest imports or automatic donors.
