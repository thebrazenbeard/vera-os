"""Ensure PID1 actually monitors a child, rather than merely claiming it in metadata."""
from pathlib import Path
import json
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_pid1_heartbeat_reflects_live_child_and_closes_on_shutdown(tmp_path, monkeypatch):
    from veraos import pid1
    monkeypatch.setattr(pid1, "_install_signal_handlers", lambda stop: None)
    monkeypatch.setattr(pid1, "_reap_children", lambda: None)
    worker = Mock()
    worker.tick.side_effect = ["STARTING", "COMPOSED_NO_COGNITION"]
    observed = []

    class Finished(Exception):
        pass

    def pause(_duration):
        observed.append(json.loads((tmp_path / "heartbeat.json").read_text()))
        if len(observed) == 2:
            raise Finished()

    with pytest.raises(Finished):
        pid1.run_supervisor(run_root=tmp_path, sleep=pause, resident_supervisor=worker)
    assert observed[0]["resident_state"] == "STARTING"
    assert observed[1]["resident_state"] == "COMPOSED_NO_COGNITION"
    assert worker.tick.call_count == 2
    worker.close.assert_called_once()


def test_guest_resident_command_is_explicit_and_has_no_shell_or_network():
    from veraos import pid1
    command = pid1.resident_child_command()
    assert command[:3] == [sys.executable, "-m", "veraos.resident"]
    assert "--components-root" in command
    assert "--run-root" in command
    assert "--state-root" in command
    assert "sh" not in command


def test_resident_subprocess_uses_pinned_veraos_python_path_not_host_imports(monkeypatch):
    from veraos import pid1
    created = []
    def launch(command, **kwargs):
        created.append((command, kwargs))
        return Mock()
    monkeypatch.setattr(pid1.subprocess, "Popen", launch)
    pid1.launch_resident(pid1.resident_child_command())
    assert len(created) == 1
    command, kwargs = created[0]
    assert command[:3] == [sys.executable, "-m", "veraos.resident"]
    assert kwargs["env"]["PYTHONPATH"] == "/opt/veraos/src"
    assert kwargs["close_fds"] is True


def test_cog_launch_requires_live_resident_local_loopback_and_drm(monkeypatch,tmp_path):
    from veraos import pid1
    monkeypatch.setattr(pid1, "_install_signal_handlers", lambda stop: None)
    monkeypatch.setattr(pid1, "_reap_children", lambda: None)
    resident = Mock()
    resident.tick.side_effect = ["STARTING", "COMPOSED_NO_COGNITION"]
    browser = Mock()
    browser.tick.return_value = "STARTING"
    seen = []
    class End(Exception):
        pass
    def sleep(_):
        seen.append(json.loads((tmp_path / "heartbeat.json").read_text()))
        if len(seen) == 2:
            raise End()
    with pytest.raises(End):
        pid1.run_supervisor(
            run_root=tmp_path, sleep=sleep, resident_supervisor=resident,
            browser_supervisor=browser, drm_available=lambda: True,
            local_ui_network_available=True,
        )
    assert seen[0]["browser_state"] == "WAITING_FOR_RESIDENT"
    assert seen[1]["browser_state"] == "STARTING"
    assert browser.tick.call_count == 1
    browser.close.assert_called_once()


def test_no_drm_means_browser_never_launched(monkeypatch,tmp_path):
    from veraos import pid1
    monkeypatch.setattr(pid1, "_install_signal_handlers", lambda stop: None)
    monkeypatch.setattr(pid1, "_reap_children", lambda: None)
    resident = Mock()
    resident.tick.return_value = "COMPOSED_NO_COGNITION"
    browser = Mock()
    class End(Exception):
        pass
    def sleep(_):
        status = json.loads((tmp_path / "heartbeat.json").read_text())
        assert status["browser_state"] == "BLOCKED_NO_DRM"
        raise End()
    with pytest.raises(End):
        pid1.run_supervisor(
            run_root=tmp_path, sleep=sleep, resident_supervisor=resident,
            browser_supervisor=browser, drm_available=lambda: False,
            local_ui_network_available=True,
        )
    browser.tick.assert_not_called()
    browser.close.assert_called_once()


def test_loopback_only_network_preparation(monkeypatch):
    from veraos import pid1
    captured = []
    def run(args, **kwargs):
        captured.append((args,kwargs))
        return Mock(returncode=0)
    monkeypatch.setattr(pid1.subprocess, "run", run)
    assert pid1.prepare_loopback() is True
    assert captured[0][0] == ["/sbin/ip", "link", "set", "lo", "up"]
    assert captured[0][1]["check"] is False
