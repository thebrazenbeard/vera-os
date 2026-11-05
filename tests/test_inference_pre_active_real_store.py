"""Real Pre-Active SQLite store closure for VeraOS inference idempotency.

The storage implementation is real; the execution engine and text are synthetic.
No model, API server, network operation, identity issuer, or effect broker runs.
Run with VERAOS_PRE_ACTIVE_SOURCE_ROOT at the pinned Git checkout below.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos.native_cognition import AdmittedTextRoute, execute_text_request  # noqa: E402


# SOURCE baseline checked against GitHub main, 2026-11-05. A future update
# requires re-review; a supplied different checkout must not pass silently.
PINNED_PRE_ACTIVE_COMMIT = "e306c251a4da44125ee58c311a35120084da8e4b"


@dataclass(frozen=True)
class _Binding:
    adapter_id: str = "synthetic-preactive-binding"
    route_id: str = "synthetic-local-text"


class _SyntheticEngine:
    """Fixture executor using real Store.create_run, never a model/backend."""

    def __init__(self, store, text: str) -> None:
        self.store = store
        self.text = text
        self.calls = 0

    def run_once(self, *, now: float) -> None:
        self.calls += 1
        event = self.store.connection.execute(
            "SELECT id, payload_json FROM events "
            "WHERE kind='task.requested' AND status='PENDING' "
            "ORDER BY created_at LIMIT 1"
        ).fetchone()
        if event is None:
            return
        payload = json.loads(event["payload_json"])
        run_id = self.store.create_run(
            task=payload["task"], capabilities=set(payload["capabilities"]),
            now=now, source_event_id=event["id"],
        )
        self.store.connection.execute(
            "UPDATE runs SET status='COMPLETED', final_text=?, updated_at=? WHERE id=?",
            (self.text, now, run_id),
        )
        self.store.connection.execute(
            "UPDATE events SET status='COMPLETED', updated_at=? WHERE id=?",
            (now, event["id"]),
        )


class _NoNetworkModel:
    """The real Pre-Active engine invokes this in-memory test double only."""

    def __init__(self, response_cls) -> None:
        self.response_cls = response_cls
        self.calls = 0

    def respond(self, *, messages, tools):
        self.calls += 1
        assert isinstance(messages, list)
        assert tools == [], "test must never expose an effect-capable tool"
        return self.response_cls(final_text="fixed-synthetic-no-network")


class RealPreActiveStoreRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        raw = os.environ.get("VERAOS_PRE_ACTIVE_SOURCE_ROOT")
        if not raw:
            raise unittest.SkipTest("pinned Pre-Active source checkout not supplied")
        root = Path(raw).resolve()
        if not (root / "src" / "pre_active" / "store.py").is_file():
            raise AssertionError("explicit Pre-Active source root lacks store.py")
        got = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True,
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if got != PINNED_PRE_ACTIVE_COMMIT:
            raise AssertionError(f"Pre-Active source drift: {got}, not reviewed pin")
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", "src/pre_active"],
            cwd=root, check=True, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if dirty:
            raise AssertionError("Pre-Active source checkout differs from pinned commit")
        sys.path.insert(0, str(root / "src"))
        imported = importlib.import_module("pre_active")
        if not Path(imported.__file__).resolve().is_relative_to((root / "src" / "pre_active").resolve()):
            raise AssertionError("Pre-Active module was already imported from another checkout")
        cls.Store = imported.Store

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="veraos-inference-store-")
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "preactive.sqlite3"

    @contextmanager
    def real_store(self):
        store = self.Store(self.path)
        try:
            yield store
        finally:
            store.close()

    @staticmethod
    def route(store, *, provider: str, model: str, text: str):
        engine = _SyntheticEngine(store, text)
        admitted = AdmittedTextRoute(
            store=store, engine=engine, binding=_Binding(),
            provider_id=provider, model=model,
        )
        return admitted, engine

    def test_cross_process_style_reopen_replay_cannot_relabel_old_backend(self):
        with self.real_store() as store:
            a, engine_a = self.route(store, provider="local:A", model="fake-A", text="A-text")
            first = execute_text_request(a, task="Name a tree", request_id="stable-1", now=1.0)
            self.assertEqual((first["status"], first["final_text"]), ("COMPLETED", "A-text"))
            self.assertEqual(engine_a.calls, 1)

        with self.real_store() as store:
            b, engine_b = self.route(store, provider="local:B", model="fake-B", text="B-text")
            with self.assertRaisesRegex(RuntimeError, "dedup_key"):
                execute_text_request(b, task="Name a tree", request_id="stable-1", now=2.0)
            self.assertEqual(engine_b.calls, 0)
            self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)
            self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)

        with self.real_store() as store:
            a_retry, replay_engine = self.route(store, provider="local:A", model="fake-A", text="BAD_SECOND_OUTPUT")
            retried = execute_text_request(a_retry, task="Name a tree", request_id="stable-1", now=3.0)
            self.assertEqual(retried["run_id"], first["run_id"])
            self.assertEqual(retried["final_text"], "A-text")
            self.assertEqual(replay_engine.calls, 0)
            self.assertEqual(store.connection.execute(
                "SELECT COUNT(*) FROM journal WHERE event_type='VERAOS_COGNITION_ROUTE_SELECTED'"
            ).fetchone()[0], 1)

    def test_model_swap_on_same_provider_and_key_is_rejected(self):
        with self.real_store() as store:
            first, _ = self.route(store, provider="local:stable", model="alias-v1", text="old")
            execute_text_request(first, task="Same task", request_id="stable-2", now=1.0)
        with self.real_store() as store:
            changed, engine = self.route(store, provider="local:stable", model="alias-v2", text="new")
            with self.assertRaisesRegex(RuntimeError, "dedup_key"):
                execute_text_request(changed, task="Same task", request_id="stable-2", now=2.0)
            self.assertEqual(engine.calls, 0)

    def test_old_unbound_event_is_held_on_new_route_retry(self):
        with self.real_store() as store:
            store.enqueue_event(
                kind="task.requested", payload={"task": "Legacy", "capabilities": []},
                priority=0, dedup_key="veraos-text:legacy-id", now=1.0,
            )
        with self.real_store() as store:
            current, engine = self.route(store, provider="local:A", model="alias-v1", text="generated")
            with self.assertRaisesRegex(RuntimeError, "dedup_key"):
                execute_text_request(current, task="Legacy", request_id="legacy-id", now=2.0)
            self.assertEqual(engine.calls, 0)
            self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 0)

    def test_distinct_requests_keep_exact_route_payloads_in_durable_sqlite(self):
        with self.real_store() as store:
            first, _ = self.route(store, provider="local:A", model="alias-v1", text="A")
            second, _ = self.route(store, provider="local:B", model="alias-v2", text="B")
            a = execute_text_request(first, task="Tree", request_id="A-1", now=1.0)
            b = execute_text_request(second, task="Tree", request_id="B-1", now=2.0)
            self.assertNotEqual(a["event_id"], b["event_id"])
            rows = store.connection.execute(
                "SELECT dedup_key, payload_json FROM events "
                "WHERE kind='task.requested' ORDER BY dedup_key"
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(
                [json.loads(row["payload_json"])["route_identity"]["provider_id"] for row in rows],
                ["local:A", "local:B"],
            )

    def test_actual_pre_active_engine_consumes_route_payload_without_tools(self):
        # Unlike the other tests this uses the real Pre-Active event claim,
        # run-step engine, context assembly, journaling, and SQLite store.
        # Only the model response is synthetic; no HTTP service or model runs.
        from pre_active.engine import Engine, ModelResponse
        from pre_active.context import ContextAssembler
        from pre_active.tools import ToolRegistry
        with self.real_store() as store:
            model = _NoNetworkModel(ModelResponse)
            engine = Engine(
                store=store, model=model, tools=ToolRegistry(store),
                context=ContextAssembler(store, max_chars=4096),
                system_prompt="Fixture only. No tools.",
                worker_id="fixture-local-preactive", max_steps=2,
                max_autonomous_turns_per_run=0, max_consecutive_endogenous_turns=0,
            )
            admitted = AdmittedTextRoute(
                store=store, engine=engine, binding=_Binding(),
                provider_id="synthetic:local", model="synthetic-no-weights",
            )
            result = execute_text_request(
                admitted, task="Give a synthetic response", request_id="real-engine-fixture",
                now=100.0,
            )
            self.assertEqual(result["status"], "COMPLETED")
            self.assertEqual(result["final_text"], "fixed-synthetic-no-network")
            self.assertEqual(model.calls, 1)
            self.assertEqual(store.get_run(result["run_id"])["status"], "COMPLETED")
            payload = json.loads(store.connection.execute(
                "SELECT payload_json FROM events WHERE id=?", (result["event_id"],)
            ).fetchone()[0])
            self.assertEqual(payload["route_identity"]["model"], "synthetic-no-weights")
            self.assertEqual(payload["capabilities"], [])


if __name__ == "__main__":
    unittest.main()
