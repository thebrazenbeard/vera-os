"""Source-only actual veraos.resident.main default-HOLD and opt-in fixture path.

No PID1, QEMU, Cog, Ollama or installed host-provider qualification.
The injected verifier is explicitly synthetic and exists only in this test.
"""
from __future__ import annotations

from contextlib import contextmanager
import time

import pytest

from test_native_admitted_cognition import descriptor, model_service, staged, STAGE


@contextmanager
def stub_normal_resident_servers(monkeypatch):
    from veraos import resident
    statuses = []

    class LocalFakeServer:
        def serve_forever(self):
            return None
        def shutdown(self):
            pass
        def server_close(self):
            pass

    def open_status(provider):
        statuses.append(dict(provider()))
        return LocalFakeServer()

    def unix_status(_root, status, _stop):
        statuses.append(dict(status))

    monkeypatch.setattr(resident, "open_loopback_server", open_status)
    monkeypatch.setattr(resident, "serve_status", unix_status)
    yield statuses


def argv_for(tmp_path):
    return [
        "--components-root", str(STAGE),
        "--state-root", str(tmp_path / "resident"),
        "--run-root", str(tmp_path / "run"),
    ]


def fixture_request(base_url):
    return {
        "provider": descriptor(base_url),
        "base_url": base_url,
        "model": "resident-probe",
        "task": "Test one bounded local phrase",
        "request_id": "resident-main-fixture-1",
        "now": time.time(),
    }


def test_normal_main_default_provider_disabled_and_ui_core_ready(monkeypatch, tmp_path):
    staged()
    from veraos.resident import main
    with stub_normal_resident_servers(monkeypatch) as statuses:
        assert main(argv_for(tmp_path)) == 0
    assert len(statuses) == 2
    assert all(x["status"] == "COMPOSED_NO_COGNITION" for x in statuses)
    assert all(x["pre_active_store_open"] is True for x in statuses)
    assert all(x["cognition_route_qualified"] is False for x in statuses)
    assert all(x["protected_effect_authority"] is False for x in statuses)


def test_raw_self_declared_pass_and_forged_real_claim_hold(monkeypatch, tmp_path):
    staged()
    from veraos.resident import main
    with model_service() as (base_url, calls):
        request = fixture_request(base_url)
        with stub_normal_resident_servers(monkeypatch):
            with pytest.raises(RuntimeError, match="verifier absent"):
                main(argv_for(tmp_path), cognition_request=request)
            with pytest.raises(RuntimeError, match="real resident provider admission not installed"):
                main(
                    argv_for(tmp_path), cognition_request=request,
                    host_admission_verifier=lambda *args: "HOST_VERIFIED_REAL",
                )
            with pytest.raises(RuntimeError, match="real resident provider admission not installed"):
                main(
                    argv_for(tmp_path), cognition_request=request,
                    host_admission_verifier=lambda *args: True,
                )
        assert calls == []


def test_real_main_fixture_completion_then_restart_dedup(monkeypatch, tmp_path):
    staged()
    from veraos.resident import main, compose_components
    with model_service(response="fixture-resident-main-ok") as (base_url, calls):
        request = fixture_request(base_url)
        auth_calls = []
        def synthetic_fixture_only(provider, endpoint, model):
            auth_calls.append((provider["provider_id"],endpoint,model))
            return "SYNTHETIC_SOURCE_FIXTURE_ONLY"

        with stub_normal_resident_servers(monkeypatch) as statuses:
            assert main(
                argv_for(tmp_path),
                cognition_request=request,
                host_admission_verifier=synthetic_fixture_only,
            ) == 0
            assert len(calls) == 1
            assert "tools" not in calls[0]
            assert len(auth_calls) == 1

            # Whole resident main() process lifetime finishes, then a fresh
            # composition/PreActive Store reads the durable completed run.
            state, opened = compose_components(STAGE, tmp_path / "resident")
            try:
                rows = opened.pre_active_store.connection.execute(
                    "SELECT id FROM runs"
                ).fetchall()
                assert len(rows) == 1
                run_id = str(rows[0]["id"])
                assert opened.pre_active_store.get_run(run_id)["status"] == "COMPLETED"
                assert opened.pre_active_store.get_run(run_id)["final_text"] == "fixture-resident-main-ok"
                assert state["cognition_route_qualified"] is False
            finally:
                opened.close()

            assert main(
                argv_for(tmp_path),
                cognition_request={**request, "now": request["now"] + 1},
                host_admission_verifier=synthetic_fixture_only,
            ) == 0
            assert len(calls) == 1  # idempotent persisted replay, not another model call
            assert len(auth_calls) == 2
            assert all(x["status"] == "COMPOSED_NO_COGNITION" for x in statuses)
            assert all(x["protected_effect_authority"] is False for x in statuses)


def test_main_rejects_request_extra_authority_and_unknown_provider(monkeypatch, tmp_path):
    staged()
    from veraos.resident import main
    with model_service() as (base_url, calls):
        request = fixture_request(base_url)
        with stub_normal_resident_servers(monkeypatch):
            with pytest.raises(ValueError, match="exact resident cognition request"):
                main(
                    argv_for(tmp_path),
                    cognition_request={**request,"allow_protected_effects":True},
                    host_admission_verifier=lambda *args:"SYNTHETIC_SOURCE_FIXTURE_ONLY",
                )
            bad = {**request, "provider": descriptor(base_url, qualified=False)}
            with pytest.raises(RuntimeError, match="HELD"):
                main(
                    argv_for(tmp_path), cognition_request=bad,
                    host_admission_verifier=lambda *args:"SYNTHETIC_SOURCE_FIXTURE_ONLY",
                )
        assert calls == []
