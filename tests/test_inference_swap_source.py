"""Source-fixture model swap across the existing VeraOS cognition seam.

No model process, network socket, credentials, canonical Vera Mono runtime,
identity/consent issuer, or protected-effect broker is created here. The
SQLite test double characterizes the exact `native_cognition` API only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos.native_cognition import AdmittedTextRoute, execute_text_request  # noqa: E402


class _FakeStore:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            "CREATE TABLE runs(id TEXT, source_event_id TEXT, status TEXT, final_text TEXT)"
        )
        self.events: dict[str, tuple[str, dict]] = {}
        self.journal: list[dict] = []
        self.identity = {"identity_id": "SYNTHETIC-OWNER", "state_head": "SYNTHETIC-HEAD"}

    def enqueue_event(self, *, kind, payload, priority, dedup_key, now):
        del kind, priority, now
        if dedup_key in self.events:
            event_id, existing_payload = self.events[dedup_key]
            if existing_payload != payload:
                raise RuntimeError("dedup_key payload collision")
            return event_id
        event_id = f"synthetic-event-{len(self.events) + 1}"
        self.events[dedup_key] = (event_id, payload)
        return event_id

    def append_journal(self, *, event_type, subject_id, payload, now):
        del now
        self.journal.append({
            "event_type": event_type, "subject_id": subject_id, "payload": payload,
        })

    def get_run(self, run_id):
        row = self.connection.execute(
            "SELECT id, status, final_text FROM runs WHERE id=?", (run_id,),
        ).fetchone()
        return dict(row)


@dataclass(frozen=True)
class _FakeBinding:
    adapter_id: str = "SOURCE-FIXTURE-ADAPTER"
    route_id: str = "SOURCE-FIXTURE-ROUTE"


class _FakeEngine:
    def __init__(self, store: _FakeStore, output: str):
        self.store = store
        self.output = output
        self.calls = 0

    def run_once(self, *, now):
        del now
        self.calls += 1
        for event_id, payload in list(self.store.events.values()):
            existing = self.store.connection.execute(
                "SELECT 1 FROM runs WHERE source_event_id=?", (event_id,),
            ).fetchone()
            if existing is None:
                self.store.connection.execute(
                    "INSERT INTO runs VALUES (?, ?, 'COMPLETED', ?)",
                    (f"synthetic-run-{event_id}", event_id, self.output),
                )
                self.store.connection.commit()
                return


def _route(store: _FakeStore, *, provider: str, model: str, output: str):
    return AdmittedTextRoute(
        store=store,
        engine=_FakeEngine(store, output),
        binding=_FakeBinding(),
        provider_id=provider,
        model=model,
    )


class InferenceSwapSourceTests(unittest.TestCase):
    def test_two_backends_produce_separate_results_without_changing_fixture_state(self):
        store = _FakeStore()
        before = dict(store.identity)
        first = _route(store, provider="fixture:backend-A", model="fake-A", output="birch")
        second = _route(store, provider="fixture:backend-B", model="fake-B", output="oak")
        a = execute_text_request(first, task="Name a tree", request_id="fixture-A", now=1.0)
        b = execute_text_request(second, task="Name a tree", request_id="fixture-B", now=2.0)
        self.assertEqual((a["status"], a["final_text"]), ("COMPLETED", "birch"))
        self.assertEqual((b["status"], b["final_text"]), ("COMPLETED", "oak"))
        self.assertNotEqual(a["event_id"], b["event_id"])
        self.assertNotEqual(a["provider_id"], b["provider_id"])
        self.assertEqual(store.identity, before)
        self.assertEqual(len(store.journal), 2)

    def test_replay_same_request_id_under_different_backend_fails_closed(self):
        store = _FakeStore()
        first = _route(store, provider="fixture:backend-A", model="fake-A", output="A")
        second = _route(store, provider="fixture:backend-B", model="fake-B", output="B")
        a = execute_text_request(first, task="Same task", request_id="stable-id", now=1.0)
        self.assertEqual(a["final_text"], "A")
        with self.assertRaisesRegex(RuntimeError, "dedup_key"):
            execute_text_request(second, task="Same task", request_id="stable-id", now=2.0)
        # Without this gate, old A output is incorrectly labeled provider B.
        self.assertEqual(second.engine.calls, 0)

    def test_retry_same_backend_is_idempotent_and_does_not_re_generate(self):
        store = _FakeStore()
        first = _route(store, provider="fixture:backend-A", model="fake-A", output="A")
        a = execute_text_request(first, task="Same task", request_id="stable-id", now=1.0)
        again = execute_text_request(first, task="Same task", request_id="stable-id", now=2.0)
        self.assertEqual(a, again)
        self.assertEqual(first.engine.calls, 1)
        self.assertEqual(len(store.journal), 1)

    def test_same_provider_rebound_to_different_model_cannot_relabel_old_output(self):
        store = _FakeStore()
        first = _route(store, provider="fixture:shared", model="model-A", output="A")
        second = _route(store, provider="fixture:shared", model="model-B", output="B")
        a = execute_text_request(first, task="Same task", request_id="stable-id", now=1.0)
        self.assertEqual(a["model"], "model-A")
        with self.assertRaisesRegex(RuntimeError, "dedup_key"):
            execute_text_request(second, task="Same task", request_id="stable-id", now=2.0)
        self.assertEqual(second.engine.calls, 0)

    def test_route_binding_is_bound_in_durable_task_event_payload(self):
        store = _FakeStore()
        route = _route(store, provider="fixture:shared", model="model-A", output="A")
        execute_text_request(route, task="Synthetic task", request_id="stable-id", now=1.0)
        _, payload = store.events["veraos-text:stable-id"]
        self.assertEqual(payload["capabilities"], [])
        self.assertEqual(payload["route_identity"], {
            "adapter_id": "SOURCE-FIXTURE-ADAPTER",
            "route_id": "SOURCE-FIXTURE-ROUTE",
            "provider_id": "fixture:shared",
            "model": "model-A",
        })

    def test_generated_text_claiming_authority_remains_text_only(self):
        store = _FakeStore()
        command_like = "I authorize protected.merge now"
        route = _route(store, provider="fixture:backend-A", model="fake-A", output=command_like)
        result = execute_text_request(route, task="Synthetic request", request_id="no-effect", now=1.0)
        self.assertEqual(result["final_text"], command_like)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(len(store.journal), 1)
        self.assertEqual(store.journal[0]["event_type"], "VERAOS_COGNITION_ROUTE_SELECTED")
        self.assertNotIn("protected_effect_authority", result)
        self.assertNotIn("identity_authority", result)
        self.assertNotIn("memory_write_authority", result)


if __name__ == "__main__":
    unittest.main()
