"""Host direct Mono composition versus actual VeraOS resident, one state contract.

'Host' here is QualifiedVeraRuntime as available to PORTAL Desktop; no claim
that ChatGPT PORTAL Desktop itself is running this Python instance.
No QEMU, provider, model, effects, memory admission, or external connections.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from test_resident_canonical_task import STAGE, running, post, get_history
from veraos import resident

pytestmark = pytest.mark.skipif(
    not (STAGE/"vera_mono/packages/vera_core/src/vera_core/local_conversation.py").is_file(),
    reason="Exact pinned Mono + PORTAL source is not staged",
)


def host_runtime(state_root):
    from vera_core import QualifiedVeraRuntime, VeraStateDirectory
    state = VeraStateDirectory(
        state_root/"vera-state", project_id="veraos", identity_id="VERA")
    runtime = QualifiedVeraRuntime.from_state_directory(state)
    assert runtime.tasks.path == state.paths.tasks
    return runtime, state


def test_direct_host_task_is_identically_visible_in_resident_http_and_cold_reentry(tmp_path):
    # True shared canonical state root; no intermediate/sibling task DB.
    state_root = tmp_path/"state"
    resident.component_paths(STAGE)
    sys.path[:0] = resident.component_paths(STAGE)
    runtime, state = host_runtime(state_root)
    from vera_core.local_conversation import open_message, recover_conversation
    original = open_message(runtime.tasks, "portal-desktop-demo", "message-7",
                            "Original source text kept intact")
    assert len(runtime.tasks.events(original["task_id"])) == 1
    with running(tmp_path) as base:
        code, replay = post(base, "Original source text kept intact",
                            "message-7", "portal-desktop-demo")
        assert code == 202 and replay["task_id"] == original["task_id"]
        assert post(base, "substituted input", "message-7", "portal-desktop-demo")[0] == 503
        code, previous = get_history(base, "portal-desktop-demo")
        assert code == 200 and len(previous["messages"]) == 1
        row = previous["messages"][0]
        assert row["task_id"] == original["task_id"]
        assert row["source_digest"] == original["source_digest"]
        assert row["status"] == "PENDING_NO_ADMITTED_PROVIDER"
        assert row["accepted_as_task_result"] is False
    # No GC: a second independently constructed runtime sees the same evidence.
    after, _ = host_runtime(state_root)
    assert after.tasks.read(original["task_id"]).packet.subject == original["text"]
    assert len(after.tasks.events(original["task_id"])) == 1
    status, handles = resident.compose_components(STAGE, state_root)
    try:
        assert handles.canonical_runtime.tasks.path == state.paths.tasks
        rows = recover_conversation(handles.canonical_runtime.tasks,
                                    handles.pre_active_store,"portal-desktop-demo")
        assert len(rows) == 1 and rows[0]["task_id"] == original["task_id"]
        assert rows[0]["memory_admitted"] is False
    finally:
        handles.close()
        handles.close()


def test_sqlite_task_writer_contention_is_transaction_scoped_not_root_lease(tmp_path):
    state_root=tmp_path/"state"
    status,handles=resident.compose_components(STAGE,state_root)
    from vera_core.local_conversation import open_message
    ledger=handles.canonical_runtime.tasks
    # Existing task SQLite provides a single active write transaction.
    # We do NOT claim this prevents two host processes from both opening
    # the broader lifecycle root or writing disjoint stores.
    direct = sqlite3.connect(ledger.path, timeout=0.1, isolation_level=None)
    try:
        direct.execute("BEGIN IMMEDIATE")
        code = (
            "import sqlite3,sys; db=sqlite3.connect(sys.argv[1],timeout=0.05,"
            "isolation_level=None); db.execute('BEGIN IMMEDIATE')"
        )
        outcome=subprocess.run([sys.executable,"-c",code,str(ledger.path)],
                               text=True,capture_output=True,timeout=12)
        assert outcome.returncode != 0
        assert "database is locked" in outcome.stderr.lower()
    finally:
        direct.rollback()
        direct.close()
        handles.close()
    next_status,next_handles=resident.compose_components(STAGE,state_root)
    try:
        original=open_message(next_handles.canonical_runtime.tasks,
                              "lock-demo","only-one","Write after release")
        assert len(next_handles.canonical_runtime.tasks.events(original["task_id"]))==1
    finally:
        next_handles.close()


def test_host_and_resident_strict_duplicate_content_under_separate_process(tmp_path):
    state_root=tmp_path/"state"
    status,handles=resident.compose_components(STAGE,state_root)
    from vera_core.local_conversation import open_message, ConversationError
    owner=handles.canonical_runtime.tasks
    first=open_message(owner,"process-join","stable-message","Exact original")
    handles.close()
    env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1",
         "PYTHONPATH":os.pathsep.join(resident.component_paths(STAGE))}
    program=(
       "from vera_core import QualifiedVeraRuntime,VeraStateDirectory\n"
       "from vera_core.local_conversation import open_message,ConversationError\n"
       "import sys\n"
       "s=VeraStateDirectory(sys.argv[1],project_id='veraos',identity_id='VERA')\n"
       "r=QualifiedVeraRuntime.from_state_directory(s)\n"
       "try:\n"
       " i=open_message(r.tasks,'process-join','stable-message',sys.argv[2]);"
       " print(i['task_id'])\n"
       "except ConversationError:\n"
       " print('REJECTED');sys.exit(13)\n"
    )
    path=str(state_root/"vera-state")
    same=subprocess.run([sys.executable,"-c",program,path,"Exact original"],
                        text=True,capture_output=True,env=env,timeout=25)
    assert same.returncode==0,same.stderr
    assert same.stdout.strip()==first["task_id"]
    conflicting=subprocess.run([sys.executable,"-c",program,path,"Not original"],
                               text=True,capture_output=True,env=env,timeout=25)
    assert conflicting.returncode==13,(conflicting.stdout,conflicting.stderr)
    status,after=resident.compose_components(STAGE,state_root)
    try:
        assert len(after.canonical_runtime.tasks.events(first["task_id"]))==1
    finally:
        after.close()


def test_complete_resident_sqlite_ownership_release_without_gc(tmp_path):
    # Hostile Windows regression: before the owning-store close repair,
    # 20/23 SQLite files remained locked even after ResidentHandles.close().
    state_root=tmp_path/"state"
    _,handles=resident.compose_components(STAGE,state_root)
    held_reference=handles.canonical_runtime
    handles.close()
    handles.close()
    files=sorted(state_root.rglob("*.sqlite"))+sorted(state_root.rglob("*.sqlite3"))
    assert len(files)>=20
    for path in files:
        moved=path.with_name(path.name+".release-check")
        os.replace(path,moved)
        os.replace(moved,path)
    assert held_reference.tasks.path.is_file()
    _,reopened=resident.compose_components(STAGE,state_root)
    reopened.close()
    for path in files:
        moved=path.with_name(path.name+".reopened-check")
        os.replace(path,moved)
        os.replace(moved,path)


def test_portal_desktop_and_veraos_logical_roots_are_not_silently_conflated(tmp_path):
    # Exact observed PORTAL Desktop source (2026-10-15 install):
    # VeraStateDirectory(state_root / "vera", project_id="VERA_MONO",
    #                    identity_id="VERA_PROJECT_IDENTITY_V1")
    # Resident OS #38 owns state_root / "vera-state" with veraos/VERA.
    # Source interoperability does not authorize a memory/identity migration.
    sys.path[:0]=resident.component_paths(STAGE)
    from vera_core import QualifiedVeraRuntime, VeraStateDirectory
    root=tmp_path/"state"
    host_state=VeraStateDirectory(root/"vera",
        project_id="VERA_MONO",identity_id="VERA_PROJECT_IDENTITY_V1")
    host=QualifiedVeraRuntime.from_state_directory(host_state)
    os_status,os_handles=resident.compose_components(STAGE,root)
    try:
        assert host_state.paths.root != root/"vera-state"
        assert host.tasks.path != os_handles.canonical_runtime.tasks.path
        assert host_state.project_id != "veraos"
        assert host_state.identity_id != "VERA"
        assert os_status["canonical_runtime_qualified"] is False
    finally:
        os_handles.close()
