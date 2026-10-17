"""Hostile source tests: no fabricated COMPLETED response from the Cog HTTP route."""
from __future__ import annotations

import json
import threading
from test_resident_conversation_http import call


def test_http_refuses_fabricated_terminal_completion():
    from veraos.desktop import open_loopback_server
    for bad in (
        {"status":"COMPLETED","run_id":None,"final_text":None},
        {"status":"COMPLETED","run_id":"fake-run","final_text":None},
        {"status":"COMPLETED","run_id":None,"final_text":"fake text"},
        {"status":"COMPLETED","run_id":"fake-run","final_text":""},
        {"status":"COMPLETED","run_id":"fake-run","final_text":"x"*8193},
    ):
        server=open_loopback_server(
            lambda:{"status":"COMPOSED_NO_COGNITION"},
            port=0,conversation_handler=lambda task,rid:bad,
        )
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        try:
            base=f"http://127.0.0.1:{server.server_port}"
            code,body,_=call(
                base,"/api/conversation",
                payload={"task":"source only","request_id":"negative-completion"},
            )
            assert code!=200,(code,bad)
            assert json.loads(body)["status"]!="COMPLETED"
        finally:
            server.shutdown();server.server_close();worker.join(3)


def test_resident_handler_fails_closed_for_invented_completion(monkeypatch,tmp_path):
    from test_native_admitted_cognition import STAGE,staged
    from veraos import resident,desktop
    staged()

    def forged(task,request_id,worker_store):
        # Fully plausible callback return with NO durable engine work.
        return {"status":"COMPLETED", "run_id":"invented-run",
                "event_id":"invented-event", "final_text":"forged output",
                "provider_id":"offline-fixture", "route_id":"offline-fixture"}

    servers=[]
    monkeypatch.setattr(resident,"open_loopback_server",lambda status_provider,**kwargs:
                        servers.append(desktop.open_loopback_server(
                            status_provider,port=0,**kwargs)) or servers[-1])
    observations=[]
    def send(_root,status,_stop):
        base=f"http://127.0.0.1:{servers[-1].server_port}"
        code,body,_=call(base,"/api/conversation",
                         payload={"task":"source only","request_id":"false-run"})
        observations.append((code,json.loads(body)))
    monkeypatch.setattr(resident,"serve_status",send)
    assert resident.main([
        "--components-root",str(STAGE),
        "--state-root",str(tmp_path/"state"),
        "--run-root",str(tmp_path/"run")],
        source_fixture_execute=forged,
    )==0
    assert len(observations)==1
    assert observations[0][0]!=200,observations
    assert observations[0][1]["status"]!="COMPLETED"
