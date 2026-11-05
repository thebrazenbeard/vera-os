# External recovery witness: comparison code, not an installed authority

Source checkpoint: VeraOS Draft PR #74 `fb14d5ce470abdc2f04bb21e5db7a7c7e3e69cd7`.
Wave 8 isolated addition: `src/veraos/wsl_recovery_witness.py` and
`tests/test_wsl_external_recovery_checkpoint_source.py`.

## Narrow outcome

`assert_matches_external_checkpoint(db, checkpoint)` checks an already
authenticated *claim* against the owner UID, schema, keyed-ledger version,
mapping count, current mapping digest, and in-database digest. If any required
field or keyed schema is missing, or the states disagree, the comparison holds.
It does **not** replace `_submit_keyed`'s separate payload, task ownership,
foreign-key and `SUBMITTED`-receipt checks: task-body edits are invisible to
the mapping-only digest.
This check has no side effects, reads no host secrets and runs no network or
Windows API. It is intentionally **not called from the production/pilot task
path** because there is currently no trusted Windows-issued checkpoint.

The nine SQLite fixture tests show both how a separately retained newer claim
reveals a complete older SQLite restore **and** how an attacker can forge a
matching replacement claim if its provenance is not authenticated. They also
show that a database committed ahead of a delayed witness must hold. A green
comparison test does not qualify automatic recovery.

## Required trust and persistence contract before any enforcement

1. A **different host-owned protection principal** must issue and durably
   store checkpoints outside WSL's mutable pilot tree. WSL same-UID code must
   have no write/delete authority over the issuer's records, version, or
   keying material. An ordinary file next to SQLite is not such an anchor.
2. The bridge must bind the checkpoint to a verified Windows logon/session,
   intended WSL owner, pilot instance, and monotonically increasing issuer
   sequence. Callers cannot assert identity by JSON fields, loopback, or a
   valid-looking SHA-256. The current source-only claim carries no issuer ID,
   sequence, signature, or proof; it is **data, not trust**.
3. All relevant state-mutating operations, including legacy unkeyed submits,
   cancellation, run/recovery receipts and old-version writers, must either
   enter a revised coordinated witness protocol or be disabled. This toy
   comparison fingerprints **only keyed mapping rows**; it does not protect
   the complete task/event history.
4. A reviewed cross-store crash protocol must enforce a single writer and
   define a durable order. One candidate: lock SQLite writer, construct the
   intended next digest without commit, ask the protected issuer to durably
   advance its checkpoint, then commit SQLite and acknowledge. A crash between
   issuer advance and SQLite commit creates an expected mismatch and a hard
   reconciliation hold. The opposite order (DB commits before issuer advances)
   also needs a hard hold on DB-ahead; no client may be told an effect is final
   without a durable host receipt. Never blindly overwrite a newer issuer
   checkpoint to make an older DB appear current.
5. Reopen/recovery must retrieve the issuer record through a separately
   authenticated channel and verify before accepting tasks. Missing channel,
   stale/missing record, issuer rollback, mismatch, concurrent downgrade writer,
   or owner/principal ambiguity means **HOLD**, not automatic repair/replay.

> **Hostile counterexample:** Backup both the SQLite file and a same-UID
> `checkpoint.json` sidecar after request A; complete and acknowledge B;
> restore both backups; the checker accepts the two matching old values.
> Merely duplicating a SHA-256 or incrementing a counter under one mutable
> protection principal cannot create independent rollback evidence.

> **Further counterexample:** A trusted external anchor covers only the keyed
> mapping ledger. An unkeyed task advances `tasks/events` but not the mapping
> digest. A complete DB rollback removing that task may still match the latest
> keyed checkpoint. The current helper must not be marketed as whole-state
> rollback protection.

## Evidence and stop condition

- TEST: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover
   -s tests -p 'test_wsl_external_recovery_checkpoint_source.py' -v` runs nine
  source/SQLite fixtures on an isolated Linux runner.
- SOURCE: immutable, validated checkpoint value type + read-only comparer.
- UNKNOWN: native Windows issuer, DACL/tokens, trusted monotonic persistence,
  crash transaction protocol, proof of non-root WSL acceptance, and recovery
  from real host power loss or VM snapshot restore.

Status is **DRAFT/HOLD**. No authorized change to Lappy/VN1/VN2/NAS, GitHub
main, OS users, filesystem ACLs, service startup, or model artifacts follows
from this source exercise.
