# Host model observation contract (source-only)

`VERAOS_HOST_MODEL_OBSERVATION_V1` is a conservative *observation* schema for
locally probed inference hosts. It never enrolls a device, probes a network,
loads a model, selects a route, or grants inference/identity/effect authority.

The pure `veraos.host_model_readiness.classify_host_model_observation` function
accepts caller-supplied evidence fields: host ID, OS, backend, exact loopback
origin *on that host*, requested model ID, timestamp, observed process,
catalogued model IDs, resident model IDs, and one endpoint-health/model-ID
pair. It returns the strongest narrowly supported state:

| State | What it establishes if the inputs are trustworthy |
| --- | --- |
| `UNOBSERVED` | No relevant process, catalog, resident model, or exact endpoint observation was supplied |
| `PROCESS_SEEN` | The host reportedly has an inference-process name |
| `MODEL_CATALOGUED` | The requested model appeared in a local model inventory; lazy loading may still be needed |
| `MODEL_RESIDENT` | A local process reported the requested model resident; generation was not tested |
| `EXACT_MODEL_ENDPOINT_OBSERVED` | A healthy local endpoint reportedly advertised the *exact* requested model |

**No state means a successful generation, authenticated host identity, model
weights/tokenizer provenance, release qualification, or an authorized route.**
Both `inference_qualified` and `route_eligible` always remain `false`.
In particular, an Ollama `/api/tags` listing is not `/api/ps` residency;
`llama-server /health: ok` without an exact model ID is not Qwen readiness.

The loopback URL is a host-local observation address, not a phone or
cross-host transport address. Neither it nor the syntactic `host_id` binds a
cryptographic device identity. Evidence timestamps are parsed but not trusted
for freshness without a separately authenticated clock/readback contract.

Future route admission must independently verify actor/host/model origin,
exact weights and runtime receipts, permitted inference API and TLS transport,
operator approval, and current workload readiness. That policy belongs to
the governed VeraOS/P.O.R.T.A.L. owners, not this module.

Focused, offline test:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_host_model_readiness.py -v
```
