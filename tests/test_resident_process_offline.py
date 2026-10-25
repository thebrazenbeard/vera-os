"""Two REAL child-process resident lifetimes with a no-network Pre-Active fixture.

The child replaces AF_UNIX wait and chooses an ephemeral console port only
for this source test. It does not boot QEMU, run Ollama, or install VeraOS.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from test_native_admitted_cognition import STAGE, staged


def _child(argv):
    import veraos.resident as resident
    import veraos.desktop as desktop
    from source_only_offline_fixture import make_offline_fixture

    state_root, run_root, port_file, stop_file, calls_file = map(Path, argv)
    fixture, calls = make_offline_fixture("offline-real-process-reply")
    def local_console(provider, **kwargs):
        server = desktop.open_loopback_server(provider, port=0, **kwargs)
        port_file.write_text(str(server.server_port), encoding="ascii")
        return server
    resident.open_loopback_server = local_console
    def wait_for_stop(root, status, stop):
        assert status["protected_effect_authority"] is False
        deadline = time.monotonic() + 16
        while time.monotonic() < deadline and not stop_file.exists():
            time.sleep(0.03)
        if not stop_file.exists():
            raise RuntimeError("test process stop timeout")
    resident.serve_status = wait_for_stop
    try:
        resident.main(
            ["--components-root", str(STAGE), "--state-root", str(state_root),
             "--run-root", str(run_root)], source_fixture_execute=fixture,
        )
    finally:
        calls_file.write_text(str(len(calls)), encoding="ascii")


def test_two_real_resident_processes_replay_without_second_model_call(tmp_path):
    staged()
    port_file=tmp_path/"port.txt"
    stop_file=tmp_path/"stop.txt"
    calls_file=tmp_path/"calls.txt"
    state_root=tmp_path/"state"
    run_root=tmp_path/"run"
    completed=[]
    env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"}
    script=str(Path(__file__).resolve())

    for attempt in range(2):
        for p in (port_file,stop_file,calls_file):
            p.unlink(missing_ok=True)
        cmd=[sys.executable,"-B",script,"--child",
             str(state_root),str(run_root),str(port_file),
             str(stop_file),str(calls_file)]
        process=subprocess.Popen(
            cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
        )
        try:
            until=time.monotonic()+12
            while time.monotonic()<until and not port_file.exists():
                if process.poll() is not None:
                    break
                time.sleep(0.05)
            assert port_file.exists(),f"resident exited={process.poll()}"
            port=int(port_file.read_text())
            base=f"http://127.0.0.1:{port}"
            data=json.dumps({
                "task":"one durable offline process task",
                "request_id":"source-process-stable-1",
            }).encode()
            request=urllib.request.Request(
                base+"/api/conversation",data=data,headers={
                    "Origin":base,"Content-Type":"application/json",
                },
            )
            with urllib.request.urlopen(request,timeout=10) as reply:
                assert reply.status==200
                completed.append(json.loads(reply.read()))
        finally:
            stop_file.touch()
            stdout,stderr=process.communicate(timeout=12)
            assert process.returncode==0,(stdout,stderr)
        assert calls_file.exists()
        assert int(calls_file.read_text())==(1 if attempt==0 else 0)
    assert completed[0]["run_id"]==completed[1]["run_id"]
    assert completed[0]["final_text"]=="offline-real-process-reply"
    assert completed[1]["final_text"]=="offline-real-process-reply"
    from veraos.resident import compose_components
    status,handle=compose_components(STAGE,state_root)
    try:
        record=handle.pre_active_store.get_run(completed[0]["run_id"])
        assert record["status"]=="COMPLETED"
        assert record["final_text"]=="offline-real-process-reply"
        assert status["protected_effect_authority"] is False
    finally:
        handle.close()


if __name__=="__main__":
    if len(sys.argv)<2 or sys.argv[1]!="--child":
        raise SystemExit("child entry only")
    _child(sys.argv[2:])
