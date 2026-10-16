# Federated cognition: independent concurrent-idempotency review

**Subject:** [VeraOS Draft PR #34](https://github.com/thebrazenbeard/vera-os/pull/34), exact base commit `6b64c3fbc2e9b71934a9229e4a815ca7e7354e8b`. This is an **adjacent review branch**; the owner's PR branch is not mutated.

## Evidence
The V1 `NodeJournal.record` and `SharedOrientation.stage` implementations performed `SELECT existing` before `INSERT` without an immediate write lock. With 16 concurrent callers submitting the *same ID and identical content*, the prior journal path returned one successful write and 15 SQLite `IntegrityError` exceptions (reproduced in four independent runs on Lappy). Identical repeated delivery should be idempotent. This matters when several agents on a single node publish simultaneously and when a connected receiver gets concurrent retransmissions.

## Fix
Wrap the duplicate lookup and optional insertion inside a SQLite `BEGIN IMMEDIATE` transaction on each writer path. This serializes local SQLite writers before read/insert. The existing digest comparison, wrong-node checks, semantic collision handling, immutable event digests and staging-vs-adoption boundary remain unchanged.

## Qualification
- Existing PR #34 tests: 15/15 passed on independent Lappy (Python 3.14) and VERA-NODE-1 (Python 3.13) read-only checkouts at the exact same PR head.
- Review branch after patch: 18/18 passed (15 original + three concurrent tests), with a 16-thread barrier in each new test.
- New regressions: (1) identical local record delivered 16 times concurrently returns 16 equivalent successful receipts and exactly one durable row; (2) identical receiver stage delivered concurrently returns 16 successes and exactly one candidate; (3) conflicting content under the same ID results in one content value winning, with exactly eight matching successes and eight `FederationError` conflicts, never silently overriding the existing event.

## Real-host research rehearsal (outside the PR)
On 2026-10-16 Lappy and VN1 each independently wrote local SQLite observations/hypotheses, objections and proposals from exact PR #34. Executor manually relayed VN1's packet to Lappy, where the receiving harness verified both content digests and staged six distinct provenance-bound events. Two contradictory link hypotheses and both objections survived. The Lappy-side governed test admitted two synthetic graph edges with monotonically increasing revisions and rejected hypothesis adoption, forged digest and stale revision. One edge alone did not establish the synthetic Lappy-to-Plex path, while both admitted edges did. This demonstrates two-host **information composition** with preserved dissent, not autonomous peer networking or emergent consciousness/intelligence. Receipt on Lappy `D:\VERA\scratch\federated-realnodes-20261016\integration-receipt.json`, SHA256 `0FBD8A017A71335BC5AB299ABA5BCDA15A0F95AB8134624F0CFFBA049767FAD1`.

## Hostile reviewer
**Partially accepted:** Local SQLite transaction serialization does not authenticate a cross-host sender, prevent a second authority node from adopting a conflicting proposal, or guarantee provider effects are fenced. It is necessary for local idempotency but far from sufficient for unity across physical hosts. Similarly, a small two-edge graph join is information aggregation, not evidence of emergent cognition beyond chaining two facts. Future implementation should add an explicit derived-proposition source record that cites all admitted evidence and unresolved objections, then compare cooperative capabilities against resource-matched chaining and single-participant baselines.

## Boundary
No production runtime, external provider, Plex process, model weights, OS boot route, principal, credential or shared canonical memory changed. No branch merges requested by this review. The authorization callback in the research prototype is not a real security broker.
