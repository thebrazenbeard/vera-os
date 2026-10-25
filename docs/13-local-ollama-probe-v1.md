# Local Ollama inference probe V1 — source-only qualification

Status: **SOURCE-ONLY / NOT INSTALLED / NO VeraOS ACTIVATION**.

The smallest independently executable local inference check in this repository
is `scripts/local_ollama_probe.py`. Python 3.11+ standard library is sufficient.
It contacts only `127.0.0.1` on one operator-selected numeric port (default
11434), never expands a URL, follows a redirect, invokes a shell, loads a
LoRA, writes a database, changes a service, or uses credentials.

```sh
python scripts/local_ollama_probe.py \
  --model 'REPLACE_WITH_EXACT_OLLAMA_TAG' \
  --manifest-digest 'REPLACE_WITH_INDEPENDENTLY_PINNED_64_HEX_DIGEST'
```

To test one real generation after the manifest pin matches, append
`--generate`. That runs a fixed prompt, `Reply with the word READY.`, with
`stream=false` and a small token budget. It does not execute model-suggested
tools or print the response contents. Exit status is zero only for
`MANIFEST_ONLY` or `MANIFEST_AND_GENERATION`, and nonzero for `HOLD`.

## Evidence boundary

| Output | What it proves | What it does **not** prove |
|---|---|---|
| `MANIFEST_ONLY` | The local HTTP endpoint returned one exact model tag with the supplied Ollama manifest digest | Model weight hashes, adapter pin, trained identity, response quality |
| `MANIFEST_AND_GENERATION` | The exact tag then returned a bounded nonempty response with `done=true` | `verad`, protected tools, memory persistence, agent authority, actual VeraOS boot |
| `HOLD` | The submitted check did not pass | An absent model or broken host is not inferred when transport fails |

Every result sets `vera_runtime_verified`, `vera_adapter_verified`, and
`activation_authorized` to `false`. The HTTP body is bounded to 128 KiB;
nonfinite/duplicate JSON keys, redirects, wrong model, ambiguous tag matches,
digest drift, and unqualified generation responses fail closed.

**Do not self-pin** by reading an arbitrary live `/api/tags` digest and then
immediately supplying that same value as a trusted reference. An exact
expected digest must come from independently reviewed source or an operator
approved artifact. Ollama's manifest digest is not the LoRA-weights SHA-256.

## Host baseline observed 2026-10-25 (read-only)

Lappy has an Ollama server and `vera-local:latest`, but its name resolves to a
Qwen3 4B Q4 model, **not** evidence of the previously pinned SmolLM Vera
adapter. `D:\VERA\local-runtime` is unversioned and its existing preflight
returned `VERA_PYTHON_ENV_MISSING`, `PINNED_ADAPTER_WEIGHTS_MISSING`, and
`PINNED_ADAPTER_CONFIG_MISSING`. The configured July 2026 adapter path uses
obsolete `C:\Vera`, and the available newer adapter digest differs from both
pinned July digests. No model substitution or local-runtime path rewrite was
authorized or performed in this source change.

Before treating a fully local Vera runtime as installed, recover the exact
pinned adapter or explicitly qualify an intentional model revision, put the
runtime implementation under canonical version control, restore its Python
environment, and demonstrate independent boot/service/authentication/state
survival. This source probe does not bypass those steps.

## Verification

```sh
python -m unittest discover -s tests -p test_local_ollama_probe.py -v
```

Tests use an injected local transport seam and no active model or network
socket. Passing tests qualify source logic only. Running the CLI against a
host is a separate real-system observation; neither implies VeraOS was built.
