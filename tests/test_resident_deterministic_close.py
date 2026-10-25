"""Windows native handle closure and cold-reopen tests on exact selected Mono."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
from test_native_admitted_cognition import STAGE, staged


def _rename_roundtrip(path: Path):
    assert path.is_file(), path
    moved = path.with_name(path.name + ".released")
    os.replace(path, moved)
    os.replace(moved, path)


def _observe_cross_process(path: Path):
    code = subprocess.run(
        [sys.executable, "-c",
         "import sqlite3,sys; db=sqlite3.connect(sys.argv[1]);"
         "print(db.execute('SELECT count(*) FROM sqlite_master').fetchone()[0]);db.close()",
         str(path)],
        capture_output=True, text=True, timeout=20,
    )
    assert code.returncode == 0, code.stderr
    assert int(code.stdout.strip()) > 0


def test_real_resident_handles_close_without_gc_and_reopen(tmp_path):
    staged()
    from veraos.resident import compose_components
    state_root = tmp_path/"state"
    status,handles = compose_components(STAGE,state_root)
    attestation = state_root/"vera-state/behavior/attestation.sqlite"
    worker = state_root/"pre-active.sqlite3"
    assert status["canonical_runtime_open"] and handles.canonical_runtime.tasks is not None
    handles.close()
    handles.close()
    # Keep strong references alive; Windows refuses replacing open SQLite files.
    _rename_roundtrip(attestation)
    _rename_roundtrip(worker)
    _observe_cross_process(attestation)
    status2,handles2 = compose_components(STAGE,state_root)
    assert status2["status"] == "COMPOSED_NO_COGNITION"
    handles2.close()
    _rename_roundtrip(attestation)
    _rename_roundtrip(worker)


def test_main_exception_closes_pre_active_and_mono_on_windows(monkeypatch,tmp_path):
    staged()
    from veraos import resident, desktop
    state_root = tmp_path/"state"
    def injected(*args,**kwargs):
        raise RuntimeError("forced runtime failure")
    monkeypatch.setattr(resident,"serve_status",injected)
    monkeypatch.setattr(resident,"open_loopback_server",
        lambda provider, **kwargs: desktop.open_loopback_server(provider,port=0,**kwargs))
    with pytest.raises(RuntimeError,match="forced runtime failure"):
        resident.main(["--components-root",str(STAGE),"--state-root",str(state_root),
                       "--run-root",str(tmp_path/"run")])
    _rename_roundtrip(state_root/"vera-state/behavior/attestation.sqlite")
    _rename_roundtrip(state_root/"pre-active.sqlite3")
    _observe_cross_process(state_root/"vera-state/behavior/attestation.sqlite")
