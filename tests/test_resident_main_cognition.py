"""Source-only normal resident main() tests; source fixture has NO network model."""
from __future__ import annotations
import json
import pytest
from test_native_admitted_cognition import STAGE, staged
from source_only_offline_fixture import make_offline_fixture


def argv_for(tmp_path):
    return ["--components-root",str(STAGE),"--state-root",str(tmp_path/"resident"),
            "--run-root",str(tmp_path/"run")]


def test_normal_main_default_no_provider_healthy_ui(monkeypatch,tmp_path):
    staged()
    from veraos import resident
    statuses=[]
    class StubServer:
        def serve_forever(self): pass
        def shutdown(self): pass
        def server_close(self): pass
    monkeypatch.setattr(resident,"open_loopback_server",lambda fn,**kw: statuses.append(fn()) or StubServer())
    monkeypatch.setattr(resident,"serve_status",lambda root,status,stop:statuses.append(dict(status)))
    assert resident.main(argv_for(tmp_path))==0
    assert len(statuses)==2
    assert all(s["status"]=="COMPOSED_NO_COGNITION" for s in statuses)
    assert all(s["conversation_fixture_available"] is False for s in statuses)
    assert all(s["cognition_route_qualified"] is False for s in statuses)
    assert all(s["protected_effect_authority"] is False for s in statuses)


def test_removed_live_callback_and_provider_injection_are_not_accepted(tmp_path):
    from veraos.resident import main, ResidentHandles
    with pytest.raises(TypeError):
        main(argv_for(tmp_path),conversation_template={"model":"qwen3:4b-instruct"})
    with pytest.raises(TypeError):
        main(argv_for(tmp_path),cognition_request={"task":"test"})
    assert not hasattr(ResidentHandles,"execute_cognition_fixture")


def test_main_offline_fixture_completed_and_persistent_cold_reopen(monkeypatch,tmp_path):
    staged()
    from veraos import resident,desktop
    from test_resident_conversation_http import call
    fixture,calls=make_offline_fixture("fixture-resident-main-ok")
    seen=[]
    servers=[]
    monkeypatch.setattr(resident,"open_loopback_server",lambda f,**kw:
        servers.append(desktop.open_loopback_server(f,port=0,**kw)) or servers[-1])
    def submit(_root,status,_stop):
        base=f"http://127.0.0.1:{servers[-1].server_port}"
        code,body,_=call(base,"/api/conversation",
            payload={"task":"One exact task","request_id":"stable-main-1"})
        seen.append((code,json.loads(body),dict(status)))
    monkeypatch.setattr(resident,"serve_status",submit)
    assert resident.main(argv_for(tmp_path),source_fixture_execute=fixture)==0
    assert len(calls)==1
    assert resident.main(argv_for(tmp_path),source_fixture_execute=fixture)==0
    assert len(calls)==1
    assert [x[0] for x in seen]==[200,200]
    assert seen[1][1]["run_id"]==seen[0][1]["run_id"]
    assert all(x[2]["cognition_route_qualified"] is False for x in seen)
    assert all(x[2]["protected_effect_authority"] is False for x in seen)
    status,handles=resident.compose_components(STAGE,tmp_path/"resident")
    try:
        row=handles.pre_active_store.get_run(seen[0][1]["run_id"])
        assert row["status"]=="COMPLETED"
        assert row["final_text"]=="fixture-resident-main-ok"
    finally:
        handles.close()


def test_main_live_model_adapter_not_constructed(monkeypatch,tmp_path):
    staged()
    from veraos import resident
    from pre_active.providers import openai_compatible
    from pre_active import model_targets
    def network_forbidden(*a,**k):
        raise AssertionError("No network model adapter/probe is permitted")
    monkeypatch.setattr(openai_compatible,"OpenAICompatibleAdapter",network_forbidden)
    monkeypatch.setattr(model_targets,"probe_model_target",network_forbidden)
    class StubServer:
        def serve_forever(self): pass
        def shutdown(self): pass
        def server_close(self): pass
    monkeypatch.setattr(resident,"open_loopback_server",lambda fn,**kw:StubServer())
    fixture,calls=make_offline_fixture()
    monkeypatch.setattr(resident,"serve_status",lambda root,status,stop:None)
    assert resident.main(argv_for(tmp_path),source_fixture_execute=fixture)==0
    assert not calls
