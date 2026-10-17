"""Canonical Vera Mono task correlation exercised through ACTUAL resident HTTP.

Everything here is a disposable SOURCE fixture. No QEMU, authenticated model,
provider admission, external effects, or governed-memory writes occur.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import gc
import os
import json
import sys
import threading
import urllib.error
import urllib.request

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"tests"))
import veraos.resident as resident
import veraos.desktop as desktop
from source_only_offline_fixture import make_offline_fixture
STAGE=Path(os.environ.get("VERAOS_CANONICAL_STAGE", str(ROOT / "tests/nonexistent-source-stage")))
pytestmark=pytest.mark.skipif(
    not (STAGE/"vera_mono/packages/vera_core/src/vera_core/local_conversation.py").is_file(),
    reason="Exact Vera Mono task integration source stage not supplied",
)


@contextmanager
def running(tmp_path, *, fixture=None):
    ready=threading.Event()
    done=threading.Event()
    errors=[]
    addr={}
    previous_server=resident.open_loopback_server
    previous_status=resident.serve_status

    def loopback(provider, **kwargs):
        s=desktop.open_loopback_server(provider, port=0, **kwargs)
        addr["base"]=f"http://127.0.0.1:{s.server_port}"
        ready.set()
        return s

    def wait_status(run_root,status,stop):
        done.wait(8)

    def run():
        try:
            resident.main(
                ["--components-root",str(STAGE),
                 "--state-root",str(tmp_path/"state"),
                 "--run-root",str(tmp_path/"run")],
                source_fixture_execute=fixture,
            )
        except BaseException as exc:
            errors.append(exc)
        finally:
            ready.set()

    resident.open_loopback_server=loopback
    resident.serve_status=wait_status
    thread=threading.Thread(target=run,daemon=True)
    thread.start()
    assert ready.wait(10), "HTTP status server never started"
    assert not errors,errors
    try:
        yield addr["base"]
    finally:
        done.set()
        thread.join(12)
        resident.open_loopback_server=previous_server
        resident.serve_status=previous_status
        assert not thread.is_alive(),"resident failed to shut down"
        assert not errors,errors
        gc.collect()


def post(base,task,request_id,conversation_id="console-demo"):
    raw=json.dumps({"task":task,"request_id":request_id,
                    "conversation_id":conversation_id}).encode("utf-8")
    req=urllib.request.Request(base+"/api/conversation",data=raw,
         headers={"Origin":base,"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=6) as reply:
            return reply.status,json.loads(reply.read())
    except urllib.error.HTTPError as exc:
        return exc.code,json.loads(exc.read())


def actual_ledger(tmp_path):
    from vera_core import VeraStateDirectory
    s=VeraStateDirectory(tmp_path/"state/vera-state",
                         project_id="veraos",identity_id="VERA")
    return s.open_task_execution_ledger() if hasattr(s,"open_task_execution_ledger") else None


def test_normal_http_intake_opens_one_canonical_task_without_dispatch(tmp_path):
    with running(tmp_path) as base:
        with urllib.request.urlopen(base+"/api/status") as r:
            status=json.loads(r.read())
        assert status["conversation_intake_available"] is True
        assert status["conversation_fixture_available"] is False
        assert status["cognition_route_qualified"] is False
        assert post(base,"remember current job","m-1")[0]==202
        assert post(base,"remember current job","m-1")[0]==202
        assert post(base,"DIFFERENT job","m-1")[0]==503
        assert post(base,"independent job","m-2")[0]==202
    with running(tmp_path) as base:
        assert post(base,"remember current job","m-1")[0]==202
        assert post(base,"independent job","m-2")[0]==202
    from vera_core.local_conversation import conversation_history
    status,h=resident.compose_components(STAGE,tmp_path/"state")
    try:
        history=conversation_history(h.canonical_runtime.tasks,"console-demo")
        assert len(history)==2
        assert {x["text"] for x in history}=={"remember current job","independent job"}
        assert all(len(h.canonical_runtime.tasks.events(x["task_id"]))==1 for x in history)
    finally:
        h.close()
        del h
        gc.collect()


def test_synthetic_result_stays_source_only_and_cold_recovery_no_second_model(tmp_path):
    fixture,calls=make_offline_fixture("SYNTHETIC: verified source example")
    with running(tmp_path,fixture=fixture) as base:
        code,first=post(base,"first task","f-1","console-first")
        assert code==200,first
        assert first["final_text"].startswith("SYNTHETIC:")
        assert len(calls)==1
    with running(tmp_path,fixture=fixture) as base:
        code,again=post(base,"first task","f-1","console-first")
        assert code==200,again
        assert again["run_id"]==first["run_id"]
        assert len(calls)==1
        code,wrong=post(base,"substituted task","f-1","console-first")
        assert code==503,wrong
    status,h=resident.compose_components(STAGE,tmp_path/"state")
    try:
        from vera_core.local_conversation import open_message,recover_message
        intake=open_message(h.canonical_runtime.tasks,"console-first","f-1","first task")
        checked=recover_message(h.canonical_runtime.tasks,h.pre_active_store,intake)
        assert checked["status"]=="SOURCE_OBSERVATION_REVALIDATED"
        assert checked["accepted_as_task_result"] is False
        assert checked["display_authorized"] is False
        assert len(h.canonical_runtime.tasks.events(intake["task_id"]))==3
    finally:
        h.close()
        del h
        gc.collect()


def test_crash_after_source_commit_cold_reconcile_never_redispatches(tmp_path):
    fixture,calls=make_offline_fixture("SYNTHETIC: original")
    def lost_reply(task,message_id,store):
        fixture(task,message_id,store)
        raise OSError("simulated lost response after durable worker completion")
    with running(tmp_path,fixture=lost_reply) as base:
        assert post(base,"one interrupted work item","c-1")[0]==502
        assert len(calls)==1
    with running(tmp_path,fixture=fixture) as base:
        code,recovered=post(base,"one interrupted work item","c-1")
        assert code==200,recovered
        assert recovered["final_text"]=="SYNTHETIC: original"
        assert len(calls)==1


def test_ambiguous_run_does_not_redispatch_or_display(tmp_path):
    hits=[]
    def died(task,message_id,store):
        hits.append(message_id)
        raise OSError("crash BEFORE Pre-Active work")
    with running(tmp_path,fixture=died) as base:
        assert post(base,"uncertain task","u-1")[0]==502
    with running(tmp_path,fixture=died) as base:
        code,result=post(base,"uncertain task","u-1")
        assert code==202 and result["status"]=="BLOCKED"
        assert len(hits)==1 and hits[0].startswith("ui-")


def test_pre_active_substitution_and_task_dependency_hold(tmp_path):
    fixture,calls=make_offline_fixture("SYNTHETIC: unaltered")
    with running(tmp_path,fixture=fixture) as base:
        assert post(base,"immutable task","t-1")[0]==200
    status,h=resident.compose_components(STAGE,tmp_path/"state")
    try:
        from vera_core.local_conversation import open_message
        intake=open_message(h.canonical_runtime.tasks,"console-demo","t-1","immutable task")
        h.canonical_runtime.tasks.bind_dependency(
            intake["task_id"], "late", kind="COORDINATION_COMMAND",target_id="cmd:late",
        )
    finally:
        h.close()
        del h
        gc.collect()
    with running(tmp_path,fixture=fixture) as base:
        assert post(base,"immutable task","t-1")[0]==503
        assert len(calls)==1


def test_independent_task_cas_out_of_order_and_stale_head(tmp_path):
    from portal import PortalRouteAdvertisement
    from portal.vera_task_handoff import assess_vera_task_route
    from vera_core.portal_task_handoff import export_portal_route_request
    from vera_core.local_conversation import open_message,reserve_source_trial,ConversationError
    status,h=resident.compose_components(STAGE,tmp_path/"state")
    try:
        led=h.canonical_runtime.tasks
        first=open_message(led,"separate","a","A")
        second=open_message(led,"separate","b","B")
        ad=PortalRouteAdvertisement(
            adapter_id="pre-active-offline-fixture",route_id="offline-fixture",
            node_id="veraos",target_kind="MODEL",target_id="offline-deterministic",
            capabilities=("text",),effect_capabilities=("NO_PROTECTED_EFFECT",),
            authorized_effects=("NO_PROTECTED_EFFECT",),
            available=True,attached=True,current=True,
        )
        def advice(task):
            request=export_portal_route_request(
                led,task["task_id"],node_id="veraos",target_kind="MODEL",
                target_id="offline-deterministic",required_capabilities=("text",),
            )
            return assess_vera_task_route(request,(ad,))
        b=reserve_source_trial(led,second,advice(second),
                               target_id="offline-deterministic",route_id="offline-fixture")
        a=reserve_source_trial(led,first,advice(first),
                               target_id="offline-deterministic",route_id="offline-fixture")
        assert b["reservation_head"]!=a["reservation_head"]
        with pytest.raises(ConversationError):
            reserve_source_trial(led,first,advice(first),
                                 target_id="offline-deterministic",route_id="offline-fixture")
    finally:
        h.close()
        del h
        gc.collect()


def test_actual_pre_active_independent_tasks_finish_out_of_order(tmp_path):
    from portal import PortalRouteAdvertisement
    from portal.vera_task_handoff import assess_vera_task_route
    from vera_core.portal_task_handoff import export_portal_route_request
    from vera_core.local_conversation import (
        open_message, reserve_source_trial, seal_source_observation, recover_message,
    )
    fixture,calls=make_offline_fixture("SYNTHETIC: out-of-order")
    status,h=resident.compose_components(STAGE,tmp_path/"state")
    try:
        ledger=h.canonical_runtime.tasks
        a=open_message(ledger,"parallel","a","task-a")
        b=open_message(ledger,"parallel","b","task-b")
        route=PortalRouteAdvertisement(
            adapter_id="pre-active-offline-fixture",route_id="offline-fixture",
            node_id="veraos",target_kind="MODEL",target_id="offline-deterministic",
            capabilities=("text",),effect_capabilities=("NO_PROTECTED_EFFECT",),
            authorized_effects=("NO_PROTECTED_EFFECT",),
            available=True,attached=True,current=True,
        )
        for intake in (a,b):
            req=export_portal_route_request(
                ledger,intake["task_id"],node_id="veraos",target_kind="MODEL",
                target_id="offline-deterministic",required_capabilities=("text",),
            )
            reserve_source_trial(ledger,intake,assess_vera_task_route(req,(route,)),
                                 target_id="offline-deterministic",route_id="offline-fixture")
        # Second task actually completes first, both with real Pre-Active Store.
        fixture("task-b",b["task_id"],h.pre_active_store)
        assert seal_source_observation(ledger,h.pre_active_store,b)["status"]=="SOURCE_OBSERVATION_REVALIDATED"
        fixture("task-a",a["task_id"],h.pre_active_store)
        assert seal_source_observation(ledger,h.pre_active_store,a)["status"]=="SOURCE_OBSERVATION_REVALIDATED"
        assert len(calls)==2
    finally:
        h.close()
        del h
        gc.collect()
    status,reopened=resident.compose_components(STAGE,tmp_path/"state")
    try:
        from vera_core.local_conversation import open_message,recover_message
        for ident,text in (("a","task-a"),("b","task-b")):
            msg=open_message(reopened.canonical_runtime.tasks,"parallel",ident,text)
            record=recover_message(reopened.canonical_runtime.tasks,reopened.pre_active_store,msg)
            assert record["status"]=="SOURCE_OBSERVATION_REVALIDATED"
            assert record["display_authorized"] is False
    finally:
        reopened.close()
        del reopened
        gc.collect()


def test_persisted_store_disagreement_is_held_on_cold_restart(tmp_path):
    fixture,calls=make_offline_fixture("SYNTHETIC: good")
    with running(tmp_path,fixture=fixture) as base:
        assert post(base,"evidence must not change","s-1")[0]==200
    from pre_active import Store
    db=Store(tmp_path/"state/pre-active.sqlite3")
    try:
        db.connection.execute(
            "UPDATE runs SET final_text='FORGED DIFFERENT RESULT' WHERE task=?",
            ("evidence must not change",),
        )
        db.connection.commit()
    finally:
        db.close()
    with running(tmp_path,fixture=fixture) as base:
        code,response=post(base,"evidence must not change","s-1")
        assert code in (502,503),response
        assert response["status"]!="COMPLETED"
        assert len(calls)==1


def test_real_parallel_task_openings_use_distinct_atomic_journal_entries(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from vera_core.local_conversation import open_message
    status,h=resident.compose_components(STAGE,tmp_path/"state")
    try:
        ledger=h.canonical_runtime.tasks
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(
                lambda i:open_message(ledger,"threaded",f"message-{i}",f"text-{i}"),
                range(8),
            ))
        assert len({r["task_id"] for r in results})==8
        assert all(len(ledger.events(r["task_id"]))==1 for r in results)
        assert ledger.verify_chain() is None or ledger.verify_chain() is not False
    finally:
        h.close()
        del h
        gc.collect()

def test_same_message_id_different_conversations_have_independent_worker_receipts(tmp_path):
    fixture,calls=make_offline_fixture("SYNTHETIC: independent")
    with running(tmp_path,fixture=fixture) as base:
        first=post(base,"one context","m-1","conv-one")
        second=post(base,"another context","m-1","conv-two")
        assert first[0]==200,first
        assert second[0]==200,second
        assert first[1]["run_id"]!=second[1]["run_id"]
        assert len(calls)==2
    with running(tmp_path,fixture=fixture) as base:
        again=post(base,"another context","m-1","conv-two")
        assert again[1]["run_id"]==second[1]["run_id"]
        assert len(calls)==2


def test_cold_two_turn_history_is_evidence_not_memory_or_model_authority(tmp_path):
    from vera_core.local_conversation import recover_conversation
    with running(tmp_path) as base:
        assert post(base,"First turn original context","m-1","continual")[0]==202
        assert post(base,"Second turn follows it","m-2","continual")[0]==202
    status,h=resident.compose_components(STAGE,tmp_path/"state")
    try:
        records=recover_conversation(
            h.canonical_runtime.tasks,h.pre_active_store,"continual",
        )
        assert [x["text"] for x in records]==[
            "First turn original context","Second turn follows it"]
        assert {x["status"] for x in records}=={"PENDING_NO_ADMITTED_PROVIDER"}
        assert all(x["source_digest"] and x["task_id"] for x in records)
        assert all(x["accepted_as_task_result"] is False for x in records)
    finally:
        h.close()
        del h
        gc.collect()

def get_history(base, conversation_id):
    with urllib.request.urlopen(
        base+"/api/conversation/history?conversation_id="+conversation_id,
        timeout=8,
    ) as response:
        return response.status,json.loads(response.read())


def test_cold_resident_http_multi_turn_context_from_canonical_ledger(tmp_path):
    with running(tmp_path) as base:
        assert post(base,"First turn: calibrate spindle","one","archive")[0]==202
        assert post(base,"Second turn: report vibration","two","archive")[0]==202
    with running(tmp_path) as base:
        code,history=get_history(base,"archive")
        assert code==200 and history["model_admitted"] is False
        assert history["memory_admitted"] is False
        assert [m["message_id"] for m in history["messages"]]==["one","two"]
        assert [m["text"] for m in history["messages"]]==[
            "First turn: calibrate spindle","Second turn: report vibration"]
        assert all(m["status"]=="PENDING_NO_ADMITTED_PROVIDER" for m in history["messages"])
        assert len({m["task_id"] for m in history["messages"]})==2
        assert post(base,"Third turn: no inference","three","archive")[0]==202
        assert len(get_history(base,"archive")[1]["messages"])==3
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base+"/api/conversation/history?conversation_id=bad!id")
        assert e.value.code==400

def test_cold_history_reports_held_after_task_invalidation(tmp_path):
    with running(tmp_path) as base:
        assert post(base,"source user task","m-1","invalidated")[0]==202
    status,h=resident.compose_components(STAGE,tmp_path/"state")
    try:
        from vera_core.local_conversation import open_message
        i=open_message(h.canonical_runtime.tasks,"invalidated","m-1","source user task")
        h.canonical_runtime.tasks.bind_dependency(
            i["task_id"],"stale",kind="COORDINATION_COMMAND",target_id="cmd:stale")
    finally:
        h.close()
        del h
        gc.collect()
    with running(tmp_path) as base:
        code,payload=get_history(base,"invalidated")
        assert code==200 and payload["messages"][0]["status"]=="HELD_TASK_INVALIDATED"
        assert payload["messages"][0]["accepted_as_task_result"] is False


def test_failed_worker_event_cannot_be_recovered_as_completed_result(tmp_path):
    fixture,calls=make_offline_fixture("SYNTHETIC: original")
    with running(tmp_path,fixture=fixture) as base:
        assert post(base,"observe once","q-1","forged-event")[0]==200
    from pre_active import Store
    store=Store(tmp_path/"state/pre-active.sqlite3")
    try:
        store.connection.execute(
            "UPDATE events SET status='FAILED' WHERE dedup_key LIKE 'veraos-text:%'")
        store.connection.commit()
    finally:
        store.close()
    with running(tmp_path,fixture=fixture) as base:
        code,history=get_history(base,"forged-event")
        assert code==200
        assert history["messages"][0]["status"]=="HELD_EVIDENCE_CONTRADICTION"
        assert post(base,"observe once","q-1","forged-event")[0]!=200
        assert len(calls)==1

def test_http_rejects_text_normalization_under_existing_message_identity(tmp_path):
    with running(tmp_path) as base:
        code,_=post(base,"Exact original task","m-1","bytes")
        assert code==202
        assert post(base," Exact original task","m-1","bytes")[0]==400
        assert post(base,"Exact original task ","m-1","bytes")[0]==400
        assert post(base,"Exact original task","m-1","bytes")[0]==202
        _,history=get_history(base,"bytes")
        assert len(history["messages"])==1
        assert history["messages"][0]["text"]=="Exact original task"
