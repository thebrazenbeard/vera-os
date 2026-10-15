from __future__ import annotations
import json
from pathlib import Path
import sys
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen, Request
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_dashboard_served_only_via_local_http_with_truthful_runtime_state():
    from veraos.desktop import open_loopback_server
    state = {
        "schema": "VERAOS_RESIDENT_STATUS_V1",
        "status": "COMPOSED_NO_COGNITION",
        "canonical_runtime_qualified": False,
        "cognition_route_qualified": False,
        "protected_effect_authority": False,
    }
    server = open_loopback_server(lambda: state, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert server.server_address[0] == "127.0.0.1"
        root = f"http://127.0.0.1:{server.server_port}"
        with urlopen(root + "/", timeout=2) as res:
            assert res.status == 200
            assert res.headers.get_content_type() == "text/html"
            page = res.read().decode()
        assert "VeraOS" in page
        assert "COMPOSED_NO_COGNITION" in page
        assert "No local cognition route" in page
        assert "https://" not in page and "http://" not in page
        with urlopen(root + "/api/status", timeout=2) as res:
            assert res.headers.get_content_type() == "application/json"
            assert json.load(res) == state
        with pytest.raises(HTTPError) as caught:
            urlopen(Request(root + "/api/chat", data=b"hello", method="POST"), timeout=2)
        assert caught.value.code == 405
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert not thread.is_alive()


def test_resident_main_starts_and_closes_local_desktop_server(monkeypatch, tmp_path):
    from veraos import resident
    store = Mock()
    state = {"status": "COMPOSED_NO_COGNITION"}
    monkeypatch.setattr(resident, "compose_components", lambda base, root: (state, store))
    server = Mock()
    monkeypatch.setattr(resident, "open_loopback_server", Mock(return_value=server))
    monkeypatch.setattr(resident, "serve_status", lambda run, state, stop: None)
    result = resident.main([
        "--components-root", str(tmp_path),
        "--run-root", str(tmp_path / "run"),
        "--state-root", str(tmp_path / "state"),
    ])
    assert result == 0
    resident.open_loopback_server.assert_called_once()
    server.shutdown.assert_called_once()
    server.server_close.assert_called_once()
    store.close.assert_called_once()
