# Synthetic learning boundary — source-only draft

This standalone seam quarantines a tiny bounded synthetic event shape in local
SQLite, identifies candidate/evaluation references by declared digests, and
constructs a request-bound immutable value. Production admission always denies.
There is no model training, retrieval, routing, activation, deployment, actor
authentication, consent verification, revocation, TTL, encryption, replication,
or integration with VeraOS runtime. No implementation here establishes learning,
provider qualification, model identity, or authority.

Only deliberately generated test fixtures belong in this journal. The schema
limits fields but cannot establish synthetic origin or prevent an adversarial
caller encoding sensitive information in allowed values. It is not a security
boundary against untrusted callers. Never pass personal or confidential data;
SQLite and its filesystem are not encrypted by this module. Caller manages the
local file and deletion. Do not use a shared network filesystem as the database.
Stored hashes are unverified declarations, not attestations of actual bytes.
Event generation is caller-provided; this source does not prove an action was
chosen before feedback. Snapshots bind declared references within a local value,
not provider state, in-flight requests, or cluster-wide atomicity.

Future admission requires separately authenticated and scoped actor, explicit
consent and revocation, provenance/retention, verified artifact and evaluation
lineage, independent tests, and exact operator authorization. A claimed PASS,
issuer string or approval field cannot promote a candidate. Keep governed identity,
permissions and personal memory outside model weights. Future real-data work is
HOLD until its privacy and deletion guarantees are established; revocation cannot
be represented as guaranteed erasure of trained weights.

## Multi-model design forum

- Astra proposed a governed sidecar with quarantined candidates, prospective
  evaluation, and rollback. Terra challenged claims of distributed atomicity and
  read-only retrieval safety: retrieval can alter behavior, and a pointer is not
  a cluster-wide transaction. This draft implements neither live retrieval nor
  distributed activation.
- Terra proposed a preregistered causal experiment against frozen and independently
  shuffled-feedback baselines with disjoint held-out task rules, equal budgets and
  uncertainty reporting. This seam does not implement that experiment; it is a
  prerequisite boundary, not evidence of improvement.
- Labyrinth specialist evidence supplied to this design: PR #117 persisted toy
  appraisal; PR #118's strongest shuffled-online null criterion failed on all
  three reported seeds; PR #119 is prospective design, not a completed result.
  These are reported inputs, not independently reproduced by this source change.
  The specialist distinguishes observation, candidate, evaluation, admission,
  and release as separate subjects. This module has no release implementation.
- Unresolved: whether an external-state learner can meet the causal criterion;
  feasible training on available hardware; trusted provenance, privacy lifecycle,
  real evaluator independence, and safe deployment. No hardware, provider or
  runtime claims follow from source tests.
