# VeraOS cognition route — real Pre-Active source closure (Draft/HOLD)

**Reviewed inputs (2026-11-05):** VeraOS Draft PR #74 at
`048da7c59d72dbbbe718b48d1bda91460e0fda8b`, accepted VeraOS `main`
`31b66b6ff317eb981c4bd8fcc4ae6e5db1d21adf`, and actual
`thebrazenbeard/pre-active` `main` commit
`e306c251a4da44125ee58c311a35120084da8e4b`.

The test `tests/test_inference_pre_active_real_store.py` imports the **real**
Pre-Active `Store`, `Engine`, `ContextAssembler`, `ToolRegistry`, and
`ModelResponse` from that pinned source closure. It uses disposable SQLite,
an explicitly synthetic in-memory model adapter, and no external or local
HTTP listener, model weights, GPU, tools, secrets, or effect executor.

## Tested contract

1. A text request stores the exact declared provider/model/route tuple inside
   Pre-Active's durable `task.requested` payload.
2. With the real Pre-Active event claim and run-step engine, the synthetic
   model response is completed in SQLite. No tools are offered to the model.
3. After closing and reopening the **real** SQLite store, reuse of the same
   request ID and task with a different backend is rejected before execution.
   The old text cannot be silently relabeled with the new provider.
4. Retrying the identical route reuses the original event, run, and text
   without generating a second output.
5. Changing only the model alias with the same request ID is rejected.
6. A legacy event without route metadata is held on retry rather than silently
   treated as if it had been made under the newly selected route.

All five focused tests passed in the disposable research runner. The same
tests **SKIP** without an explicit `VERAOS_PRE_ACTIVE_SOURCE_ROOT` checkout;
an explicitly supplied checkout at an unexpected Git SHA **FAILS** rather than
silently using a different dependency. No package installation is required.

Reproduction from the VeraOS checkout with a separately cloned, exact
Pre-Active commit:

```bash
VERAOS_PRE_ACTIVE_SOURCE_ROOT=/absolute/path/to/pre-active \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python3 -m unittest discover -s tests \
  -p 'test_inference_pre_active_real_store.py' -v
```

## Claim ceiling and hostile challenge

This is a **real storage/engine source integration test**, not live model
inference, user identity, consent, durable host admission, or production
recovery. The fake model always returns fixed synthetic text. Pre-Active's
strict event dedup rejects a changed serialized payload, but a caller who
claims the same model alias while replacing underlying GGUF bytes is invisible
to this test. Artifact digests must be independently anchored by a trusted
host-owned source before making model-provenance claims.

The test uses the current Pre-Active source checkout; it does **not** prove
that the exact dependencies are installed or accessible in the authoritative
`D:\VERA` runtime, or that a future Pre-Active release retains this contract.
The VeraOS cognition adapter remains optional/manual-admission; model output
cannot grant protected effects. The ordinary VeraOS host gates and $0 rule
remain in force. No merge, service startup, model load, or credential change
follows from this source test.
