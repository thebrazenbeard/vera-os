"""VeraOS resident component host: real local IPC and crash-aware PID1 supervision."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import pytest
import sys
import threading
import time
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_component_source_paths_include_all_staged_mono_packages(tmp_path):
    from veraos.resident import component_paths
    base = tmp_path / "components"
    for pkg in ("vera_core", "portfolio_runtime", "vera_assurance"):
        (base / "vera_mono/packages" / pkg / "src").mkdir(parents=True)
    for other in ("portal", "pre_active", "volition"):
        (base / other / "src").mkdir(parents=True)
    roots = component_paths(base)
    assert str(base / "vera_mono/packages/portfolio_runtime/src") in roots
    assert str(base / "vera_mono/packages/vera_assurance/src") in roots
    assert str(base / "vera_mono/packages/vera_core/src") in roots
    assert str(base / "pre_active/src") in roots


@pytest.mark.skipif(not hasattr(socket, 'AF_UNIX'), reason='Unix socket only available in Linux guest')
def test_service_socket_answers_local_status_without_effect_authority(tmp_path):
    from veraos.resident import serve_status
    run_root = tmp_path / "run"
    run_root.mkdir()
    stop = threading.Event()
    ready = threading.Event()
    info = {
        "schema": "VERAOS_RESIDENT_STATUS_V1",
        "status": "COMPOSED_NO_COGNITION",
        "components": ["vera_core", "portal", "pre_active", "volition"],
        "canonical_runtime_qualified": False,
        "cognition_route_qualified": False,
        "protected_effect_authority": False,
    }
    worker = threading.Thread(
        target=serve_status,
        args=(run_root, info, stop, ready),
        daemon=True,
    )
    worker.start()
    assert ready.wait(3), "IPC listener never became ready"
    sock_path = run_root / "resident.sock"
    assert sock_path.exists()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        client.connect(str(sock_path))
        client.sendall(b"status\n")
        payload = client.recv(8192)
    result = json.loads(payload)
    assert result == info
    assert result["protected_effect_authority"] is False
    stop.set()
    worker.join(3)
    assert not worker.is_alive()
    assert not sock_path.exists()


def test_supervisor_never_duplicates_live_child_and_blocks_crash_loop():
    from veraos.resident import ResidentSupervisor
    child = Mock()
    child.poll.return_value = None
    create = Mock(return_value=child)
    controller = ResidentSupervisor(["/usr/bin/python3", "-m", "veraos.resident"], launch=create)
    assert controller.tick(0.0) == "STARTING"
    assert controller.tick(1.0) == "RUNNING_UNVERIFIED"
    assert create.call_count == 1
    child.poll.return_value = 2
    assert controller.tick(2.0) == "STARTING"
    assert controller.tick(3.0) == "STARTING"
    assert controller.tick(4.0) == "BLOCKED_RESTART_LIMIT"
    assert create.call_count == 3


def test_supervisor_health_requires_live_process_and_fresh_local_ipc():
    from veraos.resident import ResidentSupervisor
    child = Mock()
    child.poll.return_value = None
    child.pid = 4321
    create = Mock(return_value=child)
    # A bare status and matching PID do not establish healthy unqualified
    # resident state. Require exact schema and all explicit hold gates.
    health = {"schema": "VERAOS_RESIDENT_STATUS_V1",
              "status": "COMPOSED_NO_COGNITION", "pid": 4321,
              "canonical_runtime_qualified": False,
              "cognition_route_qualified": False,
              "protected_effect_authority": False}
    controller = ResidentSupervisor(["python"], launch=create, health=lambda: health)
    assert controller.tick(10.0) == "STARTING"
    assert controller.tick(11.0) == "COMPOSED_NO_COGNITION"
    child.poll.return_value = 1
    assert controller.tick(12.0) != "COMPOSED_NO_COGNITION"


def test_stale_or_spoofed_status_from_different_pid_never_marks_child_healthy():
    from veraos.resident import ResidentSupervisor
    child = Mock()
    child.pid = 4321
    child.poll.return_value = None
    controller = ResidentSupervisor(
        ["python"], launch=Mock(return_value=child),
        health=lambda: {"status": "COMPOSED_NO_COGNITION", "pid": 8888},
    )
    assert controller.tick(0.0) == "STARTING"
    assert controller.tick(1.0) == "RUNNING_UNVERIFIED"
