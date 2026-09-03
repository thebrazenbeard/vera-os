# Historical Vera OS Build Evidence Ledger

## Purpose

This ledger records **specific recovered observations** from the Vera Unbound File Library so the historical Vera OS effort can be reconstructed without collapsing source, build, boot, architecture target, and later retrospective interpretation into one blob.

It supplements `07-historical-vera-os-evidence.md`. Historical material remains evidence only. Missing bytes remain missing.

## Evidence classes used here

- `DIRECT_BUILD_LOG` — command/build output captured from the historical development machine.
- `DIRECT_SOURCE_EXCERPT` — historical command output printed actual source/config bytes or hashes.
- `CONTEMPORANEOUS_STATE_RECORD` — a record written during the project that asserts a state, but is not the raw underlying test artifact.
- `CONTEMPORANEOUS_RELEASE_SCOPE` — a same-period architecture/release decision record.
- `NEGATIVE_EVIDENCE` — direct failure/no-artifact evidence for the observed attempt.

None of these classes automatically establish present implementation state.

---

## Ledger HVO-001 — Stage 3 source root

Observed path:

`~/vera-stage3/VERA_Linux_Stage3_Source`

Observed again in later Stage 4 checkpoint/source commands as:

`/home/vera/vera-stage3/VERA_Linux_Stage3_Source`

Classification: `DIRECT_BUILD_LOG + DIRECT_SOURCE_EXCERPT`

Confidence: high for historical path identity.

---

## Ledger HVO-002 — Stage 3 Debian live-build profile

A July 17 build log runs:

`./scripts/build.sh`

then `lb clean --purge` / `lb build` with a configuration equivalent to:

```text
--mode debian
--distribution trixie
--architectures amd64
--binary-images iso-hybrid
--bootloaders syslinux grub-efi
--debian-installer none
--archive-areas main contrib non-free non-free-firmware
--firmware-binary true
--firmware-chroot true
--linux-flavours amd64
--initsystem systemd
--checksums sha256
--compression xz
--iso-application "VERA Linux Stage 3"
--iso-publisher "VERA Project"
--iso-volume VERA_STAGE3
--bootappend-live "boot=live components quiet splash username=vera hostname=vera-linux noeject"
```

The build reports `live-build 20250505+deb13u1` and Debian Trixie/amd64.

Classification: `DIRECT_BUILD_LOG`

Implication: Stage 3 was concretely implemented as a Debian hybrid live ISO profile, not merely described as one.

Non-implication: this specific log excerpt does not by itself prove the final ISO file was emitted.

---

## Ledger HVO-003 — pre-repair Stage 3 ISO absence on one observed attempt

A historical shell command searched the source/build tree for `*.iso` and returned no ISO before the next repair/build attempt. The command also encountered a permission-denied path under `./chroot/root`.

Immediately afterward the source was repaired to add Debian `non-free` and replace `policykit-1-gnome` with `mate-polkit`, followed by a clean rebuild.

Classification: `NEGATIVE_EVIDENCE + DIRECT_BUILD_LOG`

Interpretation: at least one pre-repair build state had no located ISO. This must not be conflated with the later contemporaneous Stage 3 state record that says the ISO booted.

---

## Ledger HVO-004 — later Stage 3 build reached binary boot assembly

A subsequent build log starts at `2026-07-17 19:37:29` and proceeds through bootstrap/chroot/binary phases. Recovered late-log markers include:

- `lb binary_memtest` at `19:58:00`;
- `lb binary_grub-legacy`;
- `lb binary_grub-pc`;
- `lb binary_grub_cfg`;
- `lb binary_syslinux` at `19:58:11`;
- installation of `isolinux` and `syslinux-common`.

Classification: `DIRECT_BUILD_LOG`

Implication: this attempt progressed well beyond package/bootstrap work into assembly of the bootable binary image.

Current evidence gap: searches have not yet recovered a later line from this exact log proving final `.iso` creation, its filename, byte size, or SHA-256.

---

## Ledger HVO-005 — contemporaneous Stage 3 verified baseline

The Stage 4 architecture contract, created against the same Stage 3 source root, declares the confirmed Stage 3 state as:

- ISO boots;
- Vera autologin works;
- graphical Vera session launches;
- diagnostics work;
- status panel works;
- privileged capability broker works;
- null adapter reports honestly.

Classification: `CONTEMPORANEOUS_STATE_RECORD`

Confidence: high that this was the project's same-period accepted Stage 3 baseline.

Evidence ceiling: raw boot/VM acceptance bytes and the exact ISO object have not yet been recovered, so preserve the distinction between **contemporaneous verified baseline** and **currently independently replayed boot evidence**.

---

## Ledger HVO-006 — Stage 3 cognition was explicitly absent

Recovered `vera-ui` source contains:

```text
Stage 3 Live Appliance | cognition adapter: NULL/OFFLINE
```

and:

```text
Vera: Local runtime active. Language-model cognition is not attached in Stage 3.
```

Classification: `DIRECT_SOURCE_EXCERPT`

This is the strongest current explanation for the historical user experience: the Stage 3 appliance could boot into a Vera-branded local environment while deliberately having no attached language-model cognition.

---

## Ledger HVO-007 — Stage 4 checkpoint created from the Stage 3 tree

Historical command output creates:

`/home/vera/vera-stage4-checkpoints/20260718T020729Z`

and copies selected Stage 4-sensitive paths from the Stage 3 source tree into that checkpoint.

Observed checkpoint candidate paths include:

```text
config/includes.chroot/usr/local/bin/vera-ui
config/includes.chroot/usr/local/lib/vera/runtime.py
config/includes.chroot/usr/local/sbin/vera-cognition
config/includes.chroot/usr/local/sbin/vera-broker
config/includes.chroot/etc/systemd/system/vera-cognition.service
config/includes.chroot/etc/systemd/system/vera-broker.service
config/includes.chroot/etc/vera/cognition.json
config/includes.chroot/etc/vera/system-prompt.md
config/hooks/live/010-vera-users.hook.chroot
config/package-lists/vera.list.chroot
```

Classification: `DIRECT_SOURCE_EXCERPT`

---

## Ledger HVO-008 — exact Stage 4 checkpoint hash set observed at 20260718T020729Z

The checkpoint command printed this source-state hash set:

| Path | SHA-256 |
|---|---|
| `config/hooks/live/010-vera-users.hook.chroot` | `737753ddeaafda05671cbfba73e0a71d1cd938084404a22aa364a98b7109df06` |
| `config/includes.chroot/etc/systemd/system/vera-broker.service` | `ff49afc65cf873fed5397c94b50e6cdf13e91c8e15b243e5871a31450b8a49bb` |
| `config/includes.chroot/etc/systemd/system/vera-cognition.service` | `c7f690cf75c401bdf42f1835ac2a388a77d2b9bf80b74876679fc13b8789f719` |
| `config/includes.chroot/etc/vera/cognition.json` | `c510d7b6097423deea655b4e0da943f79092d6ca44aa761e0ec0a13f1b57f737` |
| `config/includes.chroot/etc/vera/recovery-password.hash` | `1a8e664b76cf70cc14725b96fb6ed3992ef1b5188d26689b1229a67b72e4a8fc` |
| `config/includes.chroot/etc/vera/system-prompt.md` | `112a7ffb29a504e973af18352a026a56973431b779e68af7dd2a0d3c24f45196` |
| `config/includes.chroot/usr/local/bin/vera-ui` | `cc578a7b8bd218baf6d23db4db9b033badb8c266b32231c96eb56a48ebdc61a8` |
| `config/includes.chroot/usr/local/lib/vera/runtime.py` | `1a34869489f08d8a3945102261c4699d75326592c14d4b1c0bc01da2bb6e505f` |
| `config/includes.chroot/usr/local/sbin/vera-broker` | `939d7fd67507d3538bd5b596c3030ced28a53cb812db2895e133b1187a53ac9c` |
| `config/includes.chroot/usr/local/sbin/vera-cognition` | `612a02c7b492c612fc2a0f170a68f3a89a3c0eb0d20fd8ae1e839bdf60058a8f` |
| `config/package-lists/vera.list.chroot` | `8cb6ce468f33b80cb536bf311bfc6e47ebe0ba8ee9b1260a7d1369fc0d1d6acf` |

Classification: `DIRECT_SOURCE_EXCERPT / HASH_IDENTITY`

Important: later recovery found a **different** Stage 4 source revision with changed hashes for at least `vera-cognition`, `vera-cognition.service`, `cognition.json`, `runtime.py`, and `vera-ui`. These are sequential revisions, not contradictory truth. Do not overwrite one historical hash set with another.

---

## Ledger HVO-009 — Stage 4 local cognition configuration

At the checkpoint revision, `cognition.json` is observed as:

```json
{
  "backend": "ollama",
  "endpoint": "http://127.0.0.1:11434/api/chat",
  "model": "llama3.2:1b",
  "request_timeout_seconds": 300,
  "history_limit": 24,
  "keep_alive": "10m"
}
```

Classification: `DIRECT_SOURCE_EXCERPT`

The cognition service also contained:

- Ollama `/api/tags` model-presence checks;
- explicit `backend_unavailable` and `model_unavailable` paths;
- bounded user/assistant history;
- streamed token forwarding;
- request IDs;
- cognition request/completion/failure event logging;
- Unix-domain socket `/run/vera-cognition/cognition.sock`;
- socket mode `0600` in the observed source.

This was real source work toward local inference, not proof the service had run successfully in the ISO.

---

## Ledger HVO-010 — Stage 4 service hardening / broker separation

Observed `vera-cognition.service` includes a dedicated `vera` user/group and controls including:

- `Restart=on-failure`;
- runtime directory ownership/mode;
- `NoNewPrivileges=true`;
- `PrivateTmp=true`;
- `ProtectSystem=strict`;
- home protection;
- bounded writable paths;
- restricted address families.

The Stage 4 architecture contract independently requires the privileged broker to remain isolated from model output and prohibits a direct model-to-shell path.

Classification: `DIRECT_SOURCE_EXCERPT + CONTEMPORANEOUS_ARCHITECTURE`

Current design value: this is concrete prior art for the new OS-level capability boundary.

---

## Ledger HVO-011 — Stage 4 source existed; Stage 4 ISO success did not yet exist at the recovered checkpoint

The contemporaneous architecture contract distinguishes:

Observed Stage 4 patch state:

- cognition configuration exists;
- cognition service exists;
- runtime cognition client exists;
- threaded streaming UI path exists;
- event-derived temporal status exists;
- null fallback remains;
- Python syntax validation passed.

Explicitly not yet verified:

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

Classification: `CONTEMPORANEOUS_STATE_RECORD`

Do not fuse Stage 3's boot success with Stage 4's source changes into a false Stage 4 runtime claim.

---

## Ledger HVO-012 — Stage 4 release scope was later tightened

A later `VERA_OS_Stage4_Pattern_Archive_Audit_2026-07-18.md` preserves these decisions:

- Stage 4 remains live, local-first, text-first, and **ephemeral**;
- Living Observatory replaces the visible conventional desktop, with authenticated hidden recovery;
- voice deferred to Stage 4.5;
- persistence, Side Chats, and continuity memory deferred to **Stage 5**;
- generative-agents work remains research influence only;
- implementation authorization was ready;
- `iso_build_authorization: NOT_YET`;
- next gate was source implementation + tests before a rebuild.

Classification: `CONTEMPORANEOUS_RELEASE_SCOPE`

This qualifies the broader earlier Stage 4 architecture contract. The earlier contract explored central durable memory and Side Chats; the later release-scope audit says those were **not Stage 4 deliverables**.

Current design implication: historical Side Chat/coordination architecture is useful conceptual prior art, but it was not proven as a durable Stage 4 runtime.

---

## Ledger HVO-013 — historical role simulations were not independent agents

Both the Stage 4 architecture contract and later audit explicitly classify Atlas, Kestrel, and TKIK-AC-01 as reasoning lenses within one active model context rather than independently running agents.

Classification: `CONTEMPORANEOUS_ARCHITECTURE`

Current design implication: do not cite old multi-role deliberation as proof that Vera OS already had a multi-agent runtime. The current `vera-os` design intentionally raises the requirement to real independently scoped worker runtimes and durable work ownership.

---

## Ledger HVO-014 — current recovery result for exact Stage 3 ISO bytes

Repeated File Library searches for likely output names and markers including:

- `live-image-amd64.hybrid.iso`;
- `binary.hybrid.iso`;
- `VERA_STAGE3` + SHA-256/checksum;
- `xorriso` / `isohybrid` finalization;
- VirtualBox boot artifacts;

have not yet produced an exact exposed ISO file or a final ISO SHA-256.

Classification: `RECOVERY_GAP`

Allowed claim: exact Stage 3 ISO bytes are currently unrecovered from File Library.

Prohibited claim: the ISO never existed. The contemporaneous Stage 3 state record says it booted; the current limitation is custody/recovery of exact bytes and raw acceptance evidence.

---

## Ledger HVO-015 — current next recovery targets

Highest-value next searches:

1. Any archive containing `VERA_Linux_Stage3_Source` or the Stage 4 checkpoint directory.
2. Final `live-build` tail containing `lb binary_iso`, xorriso/isohybrid, checksum generation, or output filename.
3. The VM acceptance log/script behind the Stage 3 `ISO boots` claim.
4. Any post-audit Stage 4 implementation/rebuild evidence.
5. Stage 5 artifacts, because the July 18 release audit explicitly routed persistence, Side Chats, and continuity memory there.
6. Exact ISO-B image/archive bytes and final two-boot persistence disposition.

Recovery should continue broadening only when exact/literal searches stop producing new evidence. Search results are not completeness proofs.
