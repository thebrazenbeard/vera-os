"""Hostile HTTP test: completed run cannot override non-DONE source event.

Offline synthetic source only, genuine resident.main ThreadingHTTPServer
and existing Pre-Active Engine / SQLite; no QEMU, Ollama or effects.
"""
from __future__ import annotations

import json
import pytest

from source_only_offline_fixture import make_offline_fixture
from test_native_admitted_cognition import STAGE, staged
from test_resident_conversation_http import call


@pytest.mark.parametrize("event_status", ["FAILED", "CLAIMED"])
def test_source_event_must_be_done_before_http_completion(
    monkeypatch, tmp_path, event_status,
):
    staged()
    from veraos import resident, desktop

    run_fixture, calls = make_offline_fixture(
        f"offline-done-guard-{event_status}",
    )

    def corrupted_fixture(task, request_id, worker_store):
        result = run_fixture(task, request_id, worker_store)
        assert result["status"] == "COMPLETED"
        source_event = result["event_id"]
        worker_store.connection.execute(
            "UPDATE events SET status=? WHERE id=?",
            (event_status, source_event),
        )
        saved = worker_store.connection.execute(
            "SELECT status FROM events WHERE id=?", (source_event,),
        ).fetchone()
        assert saved["status"] == event_status
        return result

    servers = []
    observations = []

    def bind_loopback(provider, **kwargs):
        server = desktop.open_loopback_server(
            provider, port=0, **kwargs,
        )
        servers.append(server)
        return server

    def send(_run_root, status, _stop):
        base = f"http://127.0.0.1:{servers[-1].server_port}"
        code, body, _ = call(
            base, "/api/conversation",
            payload={
                "task": "one source event consistency task",
                "request_id": "source-event-check",
            },
        )
        observations.append((code, json.loads(body)))
        assert not status["cognition_route_qualified"]
        assert not status["protected_effect_authority"]

    monkeypatch.setattr(resident, "open_loopback_server", bind_loopback)
    monkeypatch.setattr(resident, "serve_status", send)
    result = resident.main(
        [
            "--components-root", str(STAGE),
            "--state-root", str(tmp_path / "state"),
            "--run-root", str(tmp_path / "run"),
        ],
        source_fixture_execute=corrupted_fixture,
    )
    assert result == 0
    assert len(calls) == 1
    assert observations, "HTTP callback never executed"
    code, body = observations[0]
    assert code == 502, (code, body)
    assert body["status"] == "OUTCOME_UNKNOWN"
