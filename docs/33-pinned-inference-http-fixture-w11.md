# Pinned Portal + Pre-Active loopback inference fixture (Wave 11)

**TEST/SOURCE ONLY — inference admission and identity remain HOLD.**
This is not VeraOS deployed, not a loaded GGUF/KoboldCPP/llama.cpp backend,
not a Windows/WSL identity issuer and not a private memory experiment.
No model weights, credentials, network egress, protected effects or paid
services are required or authorized.

## Exact externally owned source inputs

- VeraOS Draft #74 base `a2645c4d0962a472807021ad306ac4faf7818cb1`;
  accepted VeraOS `main` remained `31b66b6ff317eb981c4bd8fcc4ae6e5db1d21adf`
  when this fixture was prepared. No inference feature has been merged.
- P.O.R.T.A.L. accepted source `a27db806c064248cba5cf109aa8a4866df4fb8d1`.
  The test loads the **real** `portal/route_resolver.py` and
  `portal/adapters.py` from this exact, clean Git checkout. It does not
  import/run the entire optional coordinator stack.
- Pre-Active accepted source
  `e306c251a4da44125ee58c311a35120084da8e4b`.
  The test uses its **real** SQLite Store, Engine, context assembler,
  empty ToolRegistry, model target probe and OpenAI-compatible HTTP adapter.

## Exact fixture

`tests/test_inference_pinned_http_replay.py` creates two disposable
`127.0.0.1` HTTP *test servers* that claim fixed synthetic model IDs
(`fixture-kobold`, `fixture-llama`). They implement only `GET /v1/models`
and `POST /v1/chat/completions`; no model generation or host service is
involved. The admitted descriptor is deliberately syntactically `PASS`
with fixture hashes: this **does not cryptographically establish an issuer**.

The four tests verify:

1. Two different backend endpoints produce different synthetic text, exact
   route/provider/model fields in durable SQLite events and two route journal
   receipts; HTTP calls contain neither tools nor authorization headers.
2. Reopening the *real* SQLite Store retains request-id deduplication: a
   different provider/model with the same request ID is rejected before a
   second HTTP completion, while an identical retry returns the original run.
3. A model not advertised by the exact endpoint is held before HTTP completion.
4. Model language pretending to authorize a protected effect remains mere
   unverified text. It produces no tool call or effect authority.

Run on a $0 disposable development host with clean local checkouts:

```sh
VERAOS_PORTAL_SOURCE_ROOT=/exact/portal-checkout \
VERAOS_PRE_ACTIVE_SOURCE_ROOT=/exact/pre-active-checkout \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python3 -m unittest discover -s tests -p 'test_inference_pinned_http_replay.py' -v
```

Absent explicit roots, the suite skips. Supplied source drift, dirty imported
source, endpoint mismatch and exact-model absence fail rather than borrowing
unreviewed interfaces. A passing fixture proves HTTP/SQLite/selection
integration for these exact versions and synthetic inputs, **not** GGUF
compatibility, actual token decoding, artifact provenance, host-owned consent,
Vera Mono state continuity or production security.

> **Hostile challenge:** `admit_local_text_route` delegates authentication of
> the declared `PASS` qualification to its caller. A caller-controlled
> descriptor can satisfy syntax validation and invoke a loopback model
> without any independently verified producer or owner grant. This test
> demonstrates that exact source execution does not close the host-owned
> admission gap. Do not connect the route to untrusted browser/WSL inputs
> until the separate issuer, context-privacy and protected-effect brokers
> are installed and independently qualified.
