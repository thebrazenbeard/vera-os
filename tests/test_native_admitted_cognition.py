"""Controlled local model endpoint -> P.O.R.T.A.L. -> Pre-Active durable result."""
from __future__ import annotations
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
import os
from pathlib import Path
import sys
import threading
import time

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
STAGE=Path(os.environ.get("VERAOS_CANONICAL_STAGE",
    r"D:\VeraOS\vm\resident-core-source-stage-20261012\components"))


def staged():
    from veraos.resident import component_paths
    if not STAGE.is_dir():
        pytest.skip("Pinned local staged repos are not present")
    for p in component_paths(STAGE):
        if p not in sys.path:
            sys.path.insert(0,p)
    return importlib.import_module("portal"), importlib.import_module("pre_active")


@contextmanager
def model_service(*, models=("resident-probe",), response="local-model-probe-ok"):
    log=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!="/v1/models":
                self.send_error(404)
                return
            payload={"data":[{"id":m} for m in models]}
            body=json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def do_POST(self):
            if self.path!="/v1/chat/completions":
                self.send_error(404)
                return
            data=self.rfile.read(int(self.headers.get("Content-Length","0")))
            log.append(json.loads(data))
            body=json.dumps({"choices":[{"message":{"content":response}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self,*args):
            return
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1",log
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def descriptor(base_url,*,qualified=True,kind="LOCAL_MODEL",attachment=None):
    return {
        "schema":"VERA_OS_COGNITION_PROVIDER_V1",
        "provider_id":"test:local-resident",
        "provider_kind":kind,
        "capabilities":["text"],
        "transport":{"kind":"OPENAI_COMPATIBLE_HTTP","attachment":base_url if attachment is None else attachment},
        "qualification":{"status":"PASS" if qualified else "HOLD","issuer":"thebrazenbeard/vera-os",
            "subject_sha256":"1"*64,"suite_sha256":"2"*64},
        "authority":{"identity_authority":False,"canonical_memory_write_authority":False,
            "protected_effect_authority":False,"browser_authority":False},
        "admission":{"status":"VERAOS_ROUTE_ELIGIBLE" if qualified else "HELD",
            "route_class":"COGNITION_ONLY","selector_owner":"thebrazenbeard/portal"},
    }


def test_native_pinned_portal_selects_pre_active_durable_no_tool_cognition(tmp_path):
    portal,pre_active=staged()
    from veraos.native_cognition import admit_local_text_route, execute_text_request
    with model_service() as (base,requests):
        store=pre_active.Store(tmp_path/"pre-active.sqlite3")
        try:
            admitted=admit_local_text_route(
                store=store,portal=portal,provider=descriptor(base),
                base_url=base,model="resident-probe",timeout_seconds=4,
            )
            assert admitted.binding.route_id=="test:local-resident"
            assert admitted.binding.adapter_id=="pre-active-openai-compatible"
            result=execute_text_request(admitted,task="Give one sentence",request_id="test-req-1",now=time.time())
            assert result["status"]=="COMPLETED"
            assert result["final_text"]=="local-model-probe-ok"
            assert result["route_id"]=="test:local-resident"
            assert result["provider_id"]=="test:local-resident"
            assert len(requests)==1
            assert requests[0]["model"]=="resident-probe"
            assert "tools" not in requests[0]
            assert "Give one sentence" in str(requests[0]["messages"])
            again=execute_text_request(admitted,task="Give one sentence",request_id="test-req-1",now=time.time()+1)
            assert again["run_id"]==result["run_id"]
            assert again["final_text"]==result["final_text"]
            assert len(requests)==1
            assert store.get_run(result["run_id"])["status"]=="COMPLETED"
            journal=store.list_journal(limit=75)
            assert any(x["event_type"]=="VERAOS_COGNITION_ROUTE_SELECTED" for x in journal)
        finally:
            store.close()


def test_held_or_remote_provider_never_reaches_inference(tmp_path):
    portal,pre_active=staged()
    from veraos.native_cognition import admit_local_text_route
    with model_service() as (base,requests):
        store=pre_active.Store(tmp_path/"pre.sqlite3")
        try:
            for record in (descriptor(base,qualified=False),descriptor(base,kind="REMOTE_API"),
                           descriptor(base,attachment="http://127.0.0.1:9/v1")):
                with pytest.raises((ValueError,RuntimeError)):
                    admit_local_text_route(store=store,portal=portal,provider=record,
                        base_url=base,model="resident-probe",timeout_seconds=3)
            assert requests==[]
        finally:
            store.close()


def test_probe_requires_exact_live_model_before_route_admission(tmp_path):
    portal,pre_active=staged()
    from veraos.native_cognition import admit_local_text_route
    with model_service(models=()) as (base,requests):
        store=pre_active.Store(tmp_path/"pre.sqlite3")
        try:
            with pytest.raises(RuntimeError,match="model"):
                admit_local_text_route(store=store,portal=portal,provider=descriptor(base),
                    base_url=base,model="resident-probe",timeout_seconds=3)
            assert requests==[]
        finally:
            store.close()


def test_no_automatic_model_grant_and_untrusted_effects_are_rejected(tmp_path):
    portal,pre_active=staged()
    from veraos.native_cognition import admit_local_text_route, execute_text_request
    with model_service() as (base,requests):
        store=pre_active.Store(tmp_path/"pre.sqlite3")
        try:
            bad=descriptor(base)
            bad["authority"]["protected_effect_authority"]=True
            with pytest.raises(ValueError):
                admit_local_text_route(store=store,portal=portal,provider=bad,
                    base_url=base,model="resident-probe")
            admitted=admit_local_text_route(store=store,portal=portal,provider=descriptor(base),
                    base_url=base,model="resident-probe",timeout_seconds=3)
            with pytest.raises(ValueError):
                execute_text_request(admitted,task=" ",request_id="bad",now=time.time())
            with pytest.raises(ValueError):
                execute_text_request(admitted,task="x"*2100,request_id="oversized",now=time.time())
            assert requests==[]
        finally:
            store.close()


def test_non_loopback_target_never_causes_network_probe(tmp_path):
    portal,pre_active=staged()
    from veraos.native_cognition import admit_local_text_route
    store=pre_active.Store(tmp_path/"pre.sqlite3")
    try:
        with pytest.raises(ValueError,match="loopback"):
            admit_local_text_route(
                store=store,portal=portal,
                provider=descriptor("http://169.254.169.254:11434/v1"),
                base_url="http://169.254.169.254:11434/v1",
                model="resident-probe",
            )
    finally:
        store.close()


def test_stable_id_must_not_be_reused_for_a_different_task(tmp_path):
    portal,pre_active=staged()
    from veraos.native_cognition import admit_local_text_route,execute_text_request
    with model_service() as (base,requests):
        store=pre_active.Store(tmp_path/"pre.sqlite3")
        try:
            admitted=admit_local_text_route(
                store=store,portal=portal,provider=descriptor(base),
                base_url=base,model="resident-probe",timeout_seconds=3,
            )
            first=execute_text_request(admitted,task="original",request_id="same-id",now=time.time())
            assert first["status"]=="COMPLETED"
            with pytest.raises(RuntimeError,match="dedup_key"):
                execute_text_request(admitted,task="different",request_id="same-id",now=time.time()+2)
            assert len(requests)==1
        finally:
            store.close()
