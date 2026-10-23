# 2026-10-16: node-residency contract and CPU reviewer training pilot

**Scope:** Isolated, synthetic, bounded research. No Vera Core weights were modified; neither the Pre-Active Qwen model server nor the resident VeraOS image was restarted. No new workstation was activated. Lappy was the only Executor-connected device; VERA-NODE-1 could not be probed live.

## Semantic outcome
Patrick's "one Vera-agent/model/whatever per node" separates into three independent layers: the **model** doing inference, the **worker/agent** with a task lifecycle, and the **Vera identity/authority** mediated through the governed runtime. A machine may host an agent with a remote model, a local model with no autonomous tools, several workers, or no inference model at all. Duplicating weights or persona is not the creation or continuity of a second Vera.

See `docs/07-node-resident-agency-and-model-locality.md` for explicit online/offline, capability and stale-lease semantics. The small `node_contract.py` is a pure classifier: it does not cryptographically verify grants, control tools, issue authority or execute tasks. Eleven unit checks reject wrong nodes, stale generations, replay, protected effects, canonical memory writes, wrong scope, bad expiry and disconnected effects. Production would require authenticated transport, non-forgeable signed leases, broker reconciliation, revocation, durable state and live dual-device testing.

## Training continuation — what actually trained
A tiny, reproducible CPU-only **character TF-IDF + logistic regression** reviewer was fitted in an isolated Lappy scratch directory, with no private corpus, GPU usage, downloads or model-service mutation. Its code is `train_cpu_probe.py` and synthetic source templates are embedded in that code. It is a deliberately weak *training-pipeline probe*, not a standalone neural Cricket Micro or a valid VeraOS critic.

The classifier trained on **320 synthetic paired examples** across eight phrase/template families. It was evaluated without further tuning on **160 paired examples from four disjoint withheld template families** (referent swap, scope over-broadening, motive attribution, and historical-to-current promotion). Training and testing use different template families, but share arbitrary synthetic entity vocabulary; this is **not** a blind real-world test.

| Metric | Observed |
|---|---:|
| Train examples | 320 |
| Grouped-template holdout examples | 160 |
| True positives | 54 |
| False negatives | 26 |
| False positives | 55 |
| True negatives | 25 |
| Held-out recall | 67.5% |
| Held-out precision | 49.5% |
| False challenge rate on benign inputs | **68.75%** |

These results **reject** this checkpoint for any review or veto route. A classifier that incorrectly objects to more than two thirds of clean statements would be actively harmful as Vera's conscience. The test code deliberately does not choose an optimal threshold on the held-out cases.

The exact saved model artifact is a local research-only `joblib` file at `D:\VERA\scratch\veraos-cricket-dual-20261016\cpu-probe-training-20261016\toy_cpu_reviewer.joblib`, SHA256 `7f1fbdab1798ccaca20655c75b149d764759f768e935a5a42101b6fd40a6110d`, 17,070 bytes. Its neighboring `receipt.json` binds algorithm, template families, seed, metrics and digest. **Do not load untrusted joblib files**, deploy this artifact, treat a separate classifier as an independent conscience, or train on private material.

## Test and effect evidence
After adding this pilot, all **24 Python unit tests** in `experiments/cricket_dual_model` passed. They include Cricket host-kernel authority and malformed-critic handling, three CPU model training checks, and eleven node lease classification checks. Prior Cricket kernel 14-case comparison, local Ollama 4-case critic pilot and their negative outcomes remain unchanged.

The inference service `C:\ProgramData\PreActive\python\python.exe ... qwen_http.py` stayed running throughout. VN1 remains disconnected from Executor; no actual multiple-node runtime, distributed identity protocol, or test of network-failure recovery is claimed.

**Next evidence frontier:** first test signed lease/fencing semantics in two-node simulation; then independent node agents with offline-safe idempotent work and guarded reconciliation. For Cricket Micro, collect blinded nonprivate labeled cases and a genuinely independent lightweight checkpoint; compare against existing deterministic Cricket and shared-model self-review. The current CPU toy and two local 4B Ollama critics have failed to qualify for adoption.
