"""The resident must instantiate Vera Mono's actual canonical composition root."""
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))


def test_qualified_vera_runtime_is_opened_and_retained_not_just_imported(monkeypatch,tmp_path):
    from veraos import resident
    calls=[]
    root=tmp_path/"components"
    (root/"vera_mono/packages/vera_core/src/vera_core").mkdir(parents=True)
    (root/"vera_mono/packages/vera_core/src/vera_core/__init__.py").touch()
    canonical=object()
    class FakeStateDirectory:
        def __init__(self, path, *, project_id, identity_id):
            calls.append(("state",Path(path),project_id,identity_id))
    class FakeRuntime:
        @staticmethod
        def from_state_directory(state):
            calls.append(("runtime",type(state).__name__))
            return canonical
    class FakeStore:
        def __init__(self, path):
            calls.append(("preactive",Path(path)))
        def close(self):
            calls.append(("close",))
    fake={
        "vera_core":SimpleNamespace(QualifiedVeraRuntime=FakeRuntime,VeraStateDirectory=FakeStateDirectory),
        "portal":SimpleNamespace(resolve_portal_route=lambda *a:None),
        "pre_active":SimpleNamespace(Store=FakeStore),
        "volition":SimpleNamespace(VolitionEngine=lambda:object()),
    }
    monkeypatch.setattr(resident.importlib,"import_module",lambda name:fake[name])
    state,handles=resident.compose_components(root,tmp_path/"state")
    assert state["status"]=="COMPOSED_NO_COGNITION"
    assert state["canonical_runtime_open"] is True
    assert state["canonical_runtime_qualified"] is False
    assert state["cognition_route_qualified"] is False
    assert state["protected_effect_authority"] is False
    assert handles.canonical_runtime is canonical
    assert calls[0] == ("state",tmp_path/"state"/"vera-state","veraos","VERA")
    assert calls[1]==("runtime","FakeStateDirectory")
    assert calls[2]==("preactive",tmp_path/"state"/"pre-active.sqlite3")
    handles.close()
    assert calls[-1]==("close",)


def test_unopenable_canonical_runtime_must_fail_closed(monkeypatch,tmp_path):
    from veraos import resident
    root=tmp_path/"components"
    (root/"vera_mono/packages/vera_core/src/vera_core").mkdir(parents=True)
    (root/"vera_mono/packages/vera_core/src/vera_core/__init__.py").touch()
    class Core:
        QualifiedVeraRuntime=SimpleNamespace(from_state_directory=lambda _state: (_ for _ in ()).throw(RuntimeError("invalid ledger")))
        VeraStateDirectory=staticmethod(lambda *a,**k:object())
    fake={
        "vera_core":Core,
        "portal":SimpleNamespace(resolve_portal_route=lambda *a:None),
        "pre_active":SimpleNamespace(Store=lambda path: (_ for _ in ()).throw(AssertionError("must not start"))),
        "volition":SimpleNamespace(VolitionEngine=lambda:object()),
    }
    monkeypatch.setattr(resident.importlib,"import_module",lambda name:fake[name])
    with pytest.raises(RuntimeError,match="invalid ledger"):
        resident.compose_components(root,tmp_path/"state")
