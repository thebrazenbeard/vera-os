"""Actual normal VeraOS resident console -> Pre-Active synthetic source roundtrip.

No QEMU, Cog process, external provider or installed real model used.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from test_native_admitted_cognition import staged, model_service, descriptor, STAGE


def call(base, path, *, payload=None, origin=True, content_type="application/json"):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {}
    if data is not None:
        headers["Content-Type"] = content_type
        if origin:
            headers["Origin"] = base
    req = urllib.request.Request(base + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def test_disabled_console_is_still_usable_and_never_dispatches():
    from veraos.desktop import open_loopback_server
    server = open_loopback_server(
        lambda: {"status": "COMPOSED_NO_COGNITION",
                 "cognition_route_qualified": False,
                 "protected_effect_authority": False,
                 "conversation_fixture_available": False},
        port=0,
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        code, html, head = call(base, "/")
        assert code == 200 and b'id="message"' in html
        assert b'id="send"' in html and b'sendMessage()' in html
        assert b"textContent=payload.final_text" in html
        assert b'disabled' in html
        assert b"Content-Security-Policy" not in html
        assert "Content-Security-Policy" in head
        code, status, _ = call(base, "/api/status")
        assert code == 200 and json.loads(status)["conversation_fixture_available"] is False
        code, denied, _ = call(
            base, "/api/conversation",
            payload={"task": "Are you here?", "request_id": "disabled-1"},
        )
        assert code == 503
        assert json.loads(denied)["status"] == "HELD_NO_ADMITTED_PROVIDER"
    finally:
        server.shutdown();server.server_close();worker.join(3)


def test_actual_resident_main_http_request_persistence_and_fails_closed(monkeypatch, tmp_path):
    staged()
    from veraos import resident, desktop
    seen = []
    servers = []

    def bind_local(status_provider, **kwargs):
        # Test-only ephemeral port. Production remains 127.0.0.1:18765.
        server = desktop.open_loopback_server(status_provider, port=0, **kwargs)
        servers.append(server)
        return server

    def collect(_run_root, status, _stop):
        server = servers[-1]
        base = f"http://127.0.0.1:{server.server_port}"
        assert status["cognition_route_qualified"] is False
        assert status["protected_effect_authority"] is False
        assert status["status"] == "COMPOSED_NO_COGNITION"
        code, health, _ = call(base, "/api/status")
        assert code == 200
        assert json.loads(health)["conversation_fixture_available"] is True
        task = {"task": "One bounded test question", "request_id": "gui-test-1"}
        for kwargs in (
            {"origin": False},
            {"payload": {**task, "provider": {"qualification": {"status": "PASS"}}}},
            {"content_type": "text/plain"},
        ):
            bad = kwargs.pop("payload", task)
            code, result, _ = call(base, "/api/conversation", payload=bad, **kwargs)
            assert code in {400, 403, 415}
            assert json.loads(result)["status"] != "COMPLETED"
        code, result, _ = call(base, "/api/conversation", payload=task)
        assert code == 200
        parsed = json.loads(result)
        assert parsed["status"] == "COMPLETED"
        assert parsed["request_id"] == "gui-test-1"
        assert parsed["final_text"] == "fixture-console-response"
        assert isinstance(parsed["run_id"], str)
        seen.append(parsed)
        code, result, _ = call(base, "/api/conversation", payload=task)
        assert code == 200
        assert json.loads(result)["run_id"] == parsed["run_id"]
        code, result, _ = call(base, "/api/conversation",
                               payload={**task, "task": "Altered task"})
        assert code == 503 and json.loads(result)["status"] == "HELD_OR_UNAVAILABLE"

    monkeypatch.setattr(resident, "open_loopback_server", bind_local)
    monkeypatch.setattr(resident, "serve_status", collect)
    args = ["--components-root", str(STAGE),
            "--state-root", str(tmp_path / "persistent"),
            "--run-root", str(tmp_path / "run")]
    with model_service(response="fixture-console-response") as (base_url, calls):
        template = {"provider": descriptor(base_url),
                    "base_url": base_url, "model": "resident-probe"}
        verifier = lambda *args: "SYNTHETIC_SOURCE_FIXTURE_ONLY"
        assert resident.main(args, conversation_template=template,
                             host_admission_verifier=verifier) == 0
        assert len(calls) == 1
        assert "tools" not in calls[0]
        # The first instance is fully shut down, then recreated from disk.
        assert resident.main(args, conversation_template=template,
                             host_admission_verifier=verifier) == 0
        assert len(calls) == 1
        assert seen[1]["run_id"] == seen[0]["run_id"]
        from veraos.resident import compose_components
        status, handles = compose_components(STAGE, tmp_path / "persistent")
        try:
            assert handles.pre_active_store.get_run(seen[0]["run_id"])["status"] == "COMPLETED"
            assert handles.pre_active_store.get_run(seen[0]["run_id"])["final_text"] == "fixture-console-response"
            assert status["cognition_route_qualified"] is False
            assert status["protected_effect_authority"] is False
        finally:
            handles.close()


def test_main_rejects_unverified_conversation_template(monkeypatch, tmp_path):
    staged()
    from veraos import resident
    args = ["--components-root", str(STAGE),
            "--state-root", str(tmp_path / "persistent"),
            "--run-root", str(tmp_path / "run")]
    with model_service() as (base_url, calls):
        template = {"provider": descriptor(base_url),
                    "base_url": base_url, "model": "resident-probe"}
        with pytest.raises(RuntimeError, match="verifier absent"):
            resident.main(args, conversation_template=template)
        with pytest.raises(ValueError, match="invalid resident conversation template"):
            resident.main(args, conversation_template={**template, "effects": True},
                          host_admission_verifier=lambda *_: "SYNTHETIC_SOURCE_FIXTURE_ONLY")
        assert calls == []