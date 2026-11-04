# Synthetic lease fixture — source-only HOLD

This standalone, in-memory, single-writer state machine handles synthetic test
fixtures only. It is not wired into VeraOS, a provider, training, a tool, or a
runtime. Production admission unconditionally returns false. Do not submit real,
personal, confidential or private data: field restrictions do not prove origin or
privacy. Action names and digest references are inert caller declarations; they
are never dereferenced, invoked, authenticated, or proven read-only.

Each exact lease configuration has a deterministic SHA-256 of its sorted compact
JSON representation. Decisions and outcomes bind to this declared configuration,
its generation digest and lease ID; the digest proves no provider, artifact or
authority. Separate instances do not coordinate or detect reuse of an ID. There is
no JSON input parser, persistence, restore, crash recovery, concurrency safety,
authentication, consent, actual verifier independence, or external outcome truth.
Only trusted fixture callers may use it; in-process callers can mutate internals.

Precommit declares the whole probability vector as integer parts per million in
allowlist order, with exact sum 1,000,000 and positive selected propensity equal
to its vector entry. These are caller claims, not evidence a model chose anything.
The distribution exploration cap is `1,000,000 - max(vector)` in ppm. A second
cap counts selected non-greedy actions; the first allowlist entry wins any tie for
highest probability. One total step and query and, when applicable, one exploration
are charged at precommit, even if feedback never arrives. Steps are total across
episodes; episodes start at 1 and steps start at 1 for each episode. Sequence is
contiguous per instance. Only one decision can await an outcome. A separately
supplied outcome must match the pending event, sequence, episode, step, action,
generation and lease configuration, and declare the exact evaluator/reward refs
and `DECLARED_EXTERNAL_VERIFIER` source. That source is metadata, not proof: a
malicious caller can forge it or supply the prediction as the outcome.

Identical replays return false and do not consume budget; divergent IDs fail.
Expiry and revocation take precedence even over identical replays. Time is a
caller-supplied nonnegative integer; backward movement during this instance is
rejected, and expiry is exclusive (`now >= expiry` denies). This cannot establish
real time or detect an initially false clock, restart, process crash, or manipulation
of instance state. No receipt, successful join, or test establishes eligibility for
production, actual learning, provider state, durable ordering, or a real-world event.
