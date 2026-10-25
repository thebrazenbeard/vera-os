"""Resident composition + existing native route -> durable local text, fixture only.

No normal PID1 service, actual model, real provider admission or external effect.
The PR32 source modules and the existing pinned component stage do the work.
"""
from __future__ import annotations
import time
import pytest

from test_native_admitted_cognition import staged, model_service, descriptor, STAGE


def test_composed_resident_existing_route_completes_and_reopens(tmp_path):
    portal, _pre_active = staged()
    from veraos.resident import compose_components
    from veraos.native_cognition import admit_local_text_route, execute_text_request

    root = tmp_path / "resident-state"
    health, handles = compose_components(STAGE, root)
    assert health["status"] == "COMPOSED_NO_COGNITION"
    assert health["canonical_runtime_open"] is True
    assert health["canonical_runtime_qualified"] is False
    assert health["cognition_route_qualified"] is False
    assert health["protected_effect_authority"] is False

    with model_service(response="fixture-local-reply") as (base_url, calls):
        try:
            admitted = admit_local_text_route(
                store=handles.pre_active_store,
                portal=portal,
                provider=descriptor(base_url),
                base_url=base_url,
                model="resident-probe",
                timeout_seconds=4,
            )
            first = execute_text_request(
                admitted,
                task="Say one test-only phrase",
                request_id="resident-fixture-1",
                now=time.time(),
            )
            assert first["status"] == "COMPLETED"
            assert first["final_text"] == "fixture-local-reply"
            assert len(calls) == 1
            assert "tools" not in calls[0]
            assert health["cognition_route_qualified"] is False

            with pytest.raises(RuntimeError, match="dedup_key"):
                execute_text_request(
                    admitted,
                    task="different task, reused request id",
                    request_id="resident-fixture-1",
                    now=time.time() + 1,
                )
            assert len(calls) == 1
        finally:
            handles.close()

        # This is an actual VeraStateDirectory + PreActive Store cold reopen,
        # not a copy of an in-memory result or a claimed model completion.
        reopened_health, reopened = compose_components(STAGE, root)
        try:
            run = reopened.pre_active_store.get_run(first["run_id"])
            assert run["status"] == "COMPLETED"
            assert run["final_text"] == "fixture-local-reply"
            again_route = admit_local_text_route(
                store=reopened.pre_active_store,
                portal=portal,
                provider=descriptor(base_url),
                base_url=base_url,
                model="resident-probe",
                timeout_seconds=4,
            )
            again = execute_text_request(
                again_route,
                task="Say one test-only phrase",
                request_id="resident-fixture-1",
                now=time.time() + 2,
            )
            assert again["run_id"] == first["run_id"]
            assert again["final_text"] == first["final_text"]
            assert len(calls) == 1  # no second fake model request
            assert reopened_health["cognition_route_qualified"] is False
            assert reopened_health["protected_effect_authority"] is False
        finally:
            reopened.close()
