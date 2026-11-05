# Full-state recovery witness transition — SOURCE ONLY / HOLD

**Exact input:** VeraOS Draft PR #74 at `048da7c59d72dbbbe718b48d1bda91460e0fda8b`.
This proposal extends the source-only witness comparator; it does **not**
create or verify an issuer, change a host ACL, or enter task admission.

## Gap reproduced

The earlier keyed submission witness `ExternalCheckpoint` fingerprints only
`ipc_submissions` mappings. An unkeyed task, cancellation, denied-effect
receipt, task body change, or other event can alter SQLite without changing
that keyed digest. A complete SQLite rollback restoring an old keyed mapping
therefore cannot be detected by a keyed-only comparison when the lost work
did not touch the mapping table.

`full_pilot_state_digest(db)` covers the known source pilot tables `meta`,
`tasks`, `events`, `ipc_submissions`, and `sqlite_sequence`, plus tables,
indexes and trigger DDL from `sqlite_master`. It requires keyed-ledger schema,
foreign-key integrity, and append-only event trigger names, rejects unknown
tables, and caps each source query at 10,000 rows. All of this is a **local
fingerprint** and does not authenticate an external record or prevent a writer
from forging both the DB and a same-UID claim.

## Proposed two-stage issuer contract

An independent Windows/VM/host-owned issuer would need to durably publish
`FullStateTransition(owner_uid, schema, version, generation, phase,
before_digest, after_digest)` with authenticated transport, monotonically
retained generations, and a protection principal inaccessible to same-UID
WSL workers. The Python dataclass is forgeable and is **not** an issuer API.

Candidate ordering, **not implemented**:

1. Quiesce all pilot writers; prove active schema and owner; capture a single
   SQLite snapshot of the current full state and intended next state.
2. Ask the separate issuer to durably write a `PREPARED` generation containing
   both digests before starting the SQLite write. The issuer must refuse stale
   generations or alteration by the guest.
3. Commit SQLite; then separately ask the issuer to durably mark the same
   generation `COMMITTED`. A caller must not acknowledge a protected effect
   until both states agree under authenticated readback. Actual cross-store
   atomicity does not exist here; a crash creates a reconciliation HOLD.
4. On recovery, obtain the latest authenticated issuer record before opening
   admission. A `PREPARED` record **always holds**, whether SQLite equals the
   before or after digest. A `COMMITTED` record is consistency-compatible only
   if the owner/schema are exact and SQLite equals the recorded after digest.
   Never auto-roll back, replay protected effects, or rewrite an issuer to
   fit an old database.

`assert_full_state_transition_consistent` implements step 4 as a **read-only
comparison only**. It cannot validate who supplied the record, whether its
generation is newest, or whether a WSL guest substituted both values. Nothing
calls this helper in the pilot's production/admission path.

## Falsifiers

> Restoring both SQLite and an adjacent same-user `checkpoint.json` after
> task A, then forging a `COMMITTED` record at the restored hash, passes the
> consistency comparison while silently losing task B. Authentication and
> independent monotonic custody are necessary; a hash or counter alone fails.

> A host issuer can publish `PREPARED` but crash before SQLite commit, or
> SQLite can commit while issuer remains `PREPARED`. Neither state is safe to
> auto-admit without explicit reconciliation. The comparer holds both.

> An attacker can add a new mutable table, delete an append-only trigger, or
> race guest writes while hashing. The source rejects unexpected tables and
> trigger absence; a future issuer must lock/serialize the entire database
> and obtain a consistent snapshot. Source tests are not OS isolation.

## Evidence

- Nine new deterministic POSIX/SQLite tests cover exact committed match,
  full rollback, database ahead, both prepared crash windows, unkeyed tasks
  and denial receipts, unkeyed rollback detection, malformed claims,
  unknown-table refusal and same-UID forged-witness counterexample.
- Existing nine keyed witness fixtures and adjacent rollback/denial/Pilot
  suites remain green; this does **not** imply cross-store durability.
- No native Windows/WSL host issuer, cryptographic signature verification,
  OS-separated ACL, task-admission hook, or real restart/cold-boot recovery.

**HOLD** until exact host principal custody, issuer sequence/provenance,
cross-store ordering, current owner/session binding and authorized receipt
readback have been implemented and independently tested. D:\\VERA remains
the Windows authority root, with $0 costs and no protected effects.
