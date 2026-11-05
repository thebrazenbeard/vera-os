# WSL IPC recovery rollback and downgrade boundary — independent Wave 7

**Evidence:** exact Draft PR #74 head `db7243915c0089310bb4ea986677c105b9ba4c0a`; fresh isolated checkout tests in `tests/test_wsl_ipc_recovery_rollback.py`. This is a source/SQLite investigation only. No actual non-root Lappy WSL run, trusted Windows SID bridge, hardware root of trust, or VeraOS service qualification is implied.

## What survives local consistency checks

Keyed IPC commits a task, `SUBMITTED` event, request mapping, and a versioned SHA-256 fingerprint in one SQLite database. Under intact committed state, a post-commit lost reply can be retried without adding a second task. The code holds on a missing row/table, broken FK, altered task payload, missing matching submission receipt, or inconsistent version/digest metadata. These are meaningful, testable protections against several *partial* restore failures.

## What they cannot prove

> **Hostile falsifier — whole-database rollback:** Write request A; capture a complete SQLite backup; write request B and observe its task ID; restore the A-only backup; retry B with exactly the same key. The database's internally consistent fingerprint matches its restored mapping ledger, so the service admits B again and generates a different task ID. The earlier B existed outside this restored history. No hash and counter stored solely in that rollback-able database can recognize the missing interval.

> **Downgrade-writer falsifier:** A client/server running older #73 code can still perform a legitimate SQL task/event/mapping commit against the same SQLite database without updating #74's fingerprint. After upgrading, #74 detects the stale fingerprint and holds keyed operations. That is fail-closed upon *re-upgrade*; it does not undo, block, or retrospectively authorize what the older writer already did.

> **Mixed keyed/unkeyed history:** Legacy unkeyed `Pilot.submit` remains legal after a keyed marker exists, creating tasks not represented in `ipc_submissions`. The current marker describes **the keyed ledger**, not all tasks. Automatic reconciliation cannot assume every unmapped task is an attack: legacy unkeyed V1 work is expressly supported. After both markers are lost, this ambiguity requires a hold and human review.

## Outcome categories

| Scenario | Local #74 behavior | Evidence class |
|---|---|---|
| Exact keyed replay, intact DB | Original task ID | Source + SQLite test |
| Missing event for a mapped task | Hold | Source + fixture tamper test |
| Corrupt version/digest | Hold | Source + fixture tamper test |
| Complete consistent rollback | Re-issues later lost key with **new task ID** | Direct SQLite falsifier; **unresolved** |
| Older #73 writer adds mapping but not digest | Old code's commit stands; #74 later holds | Simulated legacy SQL shape, not old executable run |
| New unkeyed task after marker | Accepted; not fingerprinted | Source + SQLite test; intentional opt-in compatibility |
| Markers missing with unmapped tasks | Hold | Source + fixture test |

## One justified source change proposal, not yet implementable safely

Add an optional **host-owned monotonic recovery checkpoint** contract, verified *before* admitting any post-restart keyed write. Each successful task commit needs a corresponding durable receipt/sequence outside `pilot.sqlite3`, controlled by a principal the WSL UID cannot modify. If the live database presents an older sequence or hash than the externally sealed checkpoint, **hold** and reconcile; never silently replay. The checkpoint write ordering, rollback protocol, and crash window must be designed with the protected-effect broker: simply writing another file beside SQLite under the same UID offers no integrity upgrade and introduces split-brain commits.

This is the minimum defensible *architecture* change for rollback detection, not a claim that an unauthenticated sidecar counter can fix it. An actual Windows-side receipt issuer, identity binding, cross-resource commit protocol and restart verification are not installed or authorized. Until these exist, classify whole-DB rollback as **UNRESOLVED**, retain `DRAFT/HOLD`, and qualify only disposable pilot behavior.

## Run and limitations

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -p 'test_wsl_ipc_recovery_rollback.py' -v`

The `expectedFailure` test expresses the *future* externally anchored hold contract. A successful expected failure means the missing guarantee is reproduced, **not** that rollback recovery passes. Root-owned scratch runners mock the pilot UID check solely for isolated fixture execution; qualify non-root identity and AF_UNIX transport separately on actual Lappy WSL. No host deployment, auto-start, credential changes, GPU model, protected effects, paid resources, or GitHub merge is authorized by this note.
