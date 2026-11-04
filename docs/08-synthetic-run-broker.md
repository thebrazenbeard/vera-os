# Synthetic run fixture

This is a trusted, single-process, in-memory fixture, not a production broker.
Construct a validated immutable `Lease` and `RunSpec`, then create one
`SyntheticRun`. Its `a` and `b` facades share one lease, event budget,
policy and receipt chain. A request supplies a fixture event identifier, the
unchanging declared generation digest, and the current policy digest from
`snapshot()`. The caller supplies an integer monotonic time. Steps are
serialized under one lock. No public outcome or reducer input exists.

The broker picks the first untried action; then it picks the highest empirical
reward mean, using integer comparisons and allowlist-order tie breaks. It
precommits a one-hot decision through the lease before looking up its fixed
binary fixture reward. It records that internally constructed outcome and
updates counts and sums exactly once. This is not model training or evidence
of general learning.

Config, policy and receipt identities are SHA-256 of ASCII canonical JSON
(sorted keys, compact separators, ASCII escapes) containing `domain` and
`value`. The domains are `synthetic-run-config-v1`,
`synthetic-run-policy-v1`, and `synthetic-run-receipt-v1`. The initial
prior-receipt value is 64 zeroes. The receipt digest excludes only its own
digest field. Generation is immutable declared artifact identity; policy is
separate mutable state. These hashes are lineage identifiers, not signatures.

Identical same-facade event replay returns the original receipt without an
update, including after subsequent events. A conflicting request or facade
for the same event is rejected. Time validation, revocation, expiry and fault
checks precede replay; expiry at `now >= expiry` denies replay. Valid forward
time is retained even if the rest of a call is rejected. After root
reservation, any exception faults the broker permanently and consumes the
reservation; it is not refunded. A fault can occur before the underlying
lease precommit succeeds. There is no restart or recovery API.

The `DECLARED_EXTERNAL_VERIFIER` label satisfies the prior fixture contract;
it does not establish an independent or authenticated verifier. Another
instance may reuse IDs and budgets; the caller can lie about time; Python
private fields are accessible. There is no durable global lease, process or
host isolation, crash recovery, real verifier identity, local model training,
actual weights, causal generalization, runtime wiring, host probing, external
effect adapter or private-data ingestion. The prior production admission hook
remains unconditionally false. Do not use this as a cross-host security
protocol or a production authorization mechanism.
