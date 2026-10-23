# Cricket dual-model comparison (research only)

This experiment evaluates an existing Cricket deterministic baseline and optionally an Ollama-served semantic critic. It does not install Cricket into VeraOS or demonstrate a dedicated independent Cricket Micro model.

Pinned reference used in the first run: `thebrazenbeard/cricket@0bae95bc45db55d78001ee9c492681834191ec0b`. Run with Python 3.10+ and the research checkout's `src` on `PYTHONPATH`. No runtime dependency on an external repository is introduced in VeraOS.

Commands (PowerShell; set `$env:PYTHONPATH` to the pinned Cricket checkout's `src`):
```powershell
python -B -m unittest discover -s experiments/cricket_dual_model -p "test_*.py" -v
python -B experiments/cricket_dual_model/benchmark.py --cases experiments/cricket_dual_model/cases.json --mode kernel --output ./cricket-kernel-results.json
```

Optional local semantic model experiment requires a running, authorized local Ollama inference server and a specific pinned model name:
```powershell
python -B experiments/cricket_dual_model/benchmark.py --cases experiments/cricket_dual_model/cases.json --mode ollama --model qwen3:4b-instruct --output ./cricket-semantic-results.json
```
This run is model-assisted Cricket, **not** proof of a distinct Cricket Micro. Compare a primary-model critic with a different, genuinely distinct model using the **same** cases and reviewer interface. Passing `--core-digest` rejects an identical reviewer artifact digest; different digest alone does not establish training independence.

Additional CPU-only training and simulated node-lease classification (both research-only):
```powershell
python -B experiments/cricket_dual_model/train_cpu_probe.py --output-dir ./fresh-toy-training-output
python -B -m unittest discover -s experiments/cricket_dual_model -p "test_*.py" -v
```
See `TRAINING_AND_NODE_PILOT_20261016.md` and `docs/07-node-resident-agency-and-model-locality.md` for measured false-challenge rates and lease boundary semantics. This toy CPU classifier is **not** Cricket Micro, not independently reviewed, and not accepted for live routing. The `node_contract.py` implementation is pure advisory validation without signature verification or effect execution.

Results contain only synthetic case IDs, labels, finding IDs, per-case status, timing and model digest. They intentionally exclude raw model completions. The harness fails when any case is unresolved and separately reports errors; a zero-result or malformed model reply is never treated as a clean PASS. No protected effects or tools are executed in the fixture.
