"""VeraOS local-only resident component host, not a cognition/effect grant."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from typing import Callable

from .desktop import open_loopback_server


DEFAULT_COMPONENTS = Path("/opt/veraos/components")
DEFAULT_RUN_ROOT = Path("/run/veraos")
DEFAULT_STATE_ROOT = Path("/var/lib/veraos/resident")
COMPONENT_NAMES = ("vera_core", "portal", "pre_active", "volition")


def component_paths(base: Path) -> list[str]:
    roots = sorted((base / "vera_mono" / "packages").glob("*/src"))
    return [str(p) for p in roots if p.is_dir()] + [
        str(base / "portal"),
        str(base / "pre_active" / "src"),
        str(base / "volition" / "src"),
    ]



@dataclass
class ResidentHandles:
    """Hold the actual Vera Mono composition for the lifetime of this process."""

    pre_active_store: object
    canonical_runtime: object

    def close(self) -> None:
        self.pre_active_store.close()


def compose_components(base: Path, state_root: Path) -> tuple[dict, object]:
    """Import exact staged packages; open PreActive's actual durable Store.

    Importing the core does not instantiate a QualifiedVeraRuntime or
    authorize any cognition/effects. Report that distinction explicitly.
    """
    if not (base / "vera_mono/packages/vera_core/src/vera_core/__init__.py").is_file():
        raise FileNotFoundError("No staged vera_core package")
    sys.path[:0] = component_paths(base)
    core, portal, pre_active, volition = (
        importlib.import_module(name) for name in COMPONENT_NAMES
    )
    if not hasattr(core, "QualifiedVeraRuntime"):
        raise RuntimeError("Actual Vera runtime API missing")
    if not hasattr(portal, "resolve_portal_route"):
        raise RuntimeError("P.O.R.T.A.L. route API missing")
    state_root.mkdir(parents=True, exist_ok=True)
    # Open the source-bound Vera Mono composition root first. Its native effect
    # fence and trust registry stay fail-closed without injected authorities.
    state = core.VeraStateDirectory(
        state_root / "vera-state", project_id="veraos", identity_id="VERA",
    )
    canonical_runtime = core.QualifiedVeraRuntime.from_state_directory(state)
    store = pre_active.Store(state_root / "pre-active.sqlite3")
    engine = volition.VolitionEngine()
    assert engine is not None
    status = {
        "schema": "VERAOS_RESIDENT_STATUS_V1",
        "status": "COMPOSED_NO_COGNITION",
        "pid": os.getpid(),
        "components": list(COMPONENT_NAMES),
        "pre_active_store_open": True,
        "volition_engine_initialized": True,
        "portal_route_api_present": True,
        "canonical_runtime_open": True,
        "canonical_runtime_qualified": False,
        "cognition_route_qualified": False,
        "conversation_fixture_available": False,
        "conversation_intake_available": True,
        "protected_effect_authority": False,
    }
    return status, ResidentHandles(store, canonical_runtime)


def serve_status(
    run_root: Path,
    status: dict,
    stop: threading.Event,
    ready: threading.Event | None = None,
) -> None:
    """Read-only status on a UNIX socket; no TCP/listening remote effects."""
    run_root.mkdir(parents=True, exist_ok=True)
    path = run_root / "resident.sock"
    if path.exists():
        # An existing live owner must never be displaced.
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.15)
            try:
                probe.connect(str(path))
            except (ConnectionRefusedError, FileNotFoundError, OSError):
                path.unlink(missing_ok=True)
            else:
                raise RuntimeError("Resident socket is already owned by a live process")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(path))
        if os.name != "nt":
            os.chmod(path, 0o600)
        server.listen(3)
        server.settimeout(0.25)
        if ready is not None:
            ready.set()
        try:
            while not stop.is_set():
                try:
                    client, _ = server.accept()
                except socket.timeout:
                    continue
                with client:
                    client.settimeout(1.0)
                    request = client.recv(80)
                    if request.strip() == b"status":
                        data = json.dumps(status, sort_keys=True).encode("utf-8") + b"\n"
                    else:
                        data = b'{"status":"UNSUPPORTED_READ_ONLY_REQUEST"}\n'
                    client.sendall(data)
        finally:
            path.unlink(missing_ok=True)


def read_health(run_root: Path = DEFAULT_RUN_ROOT) -> dict | None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.25)
            client.connect(str(run_root / "resident.sock"))
            client.sendall(b"status\n")
            result = json.loads(client.recv(4096))
        if result.get("schema") == "VERAOS_RESIDENT_STATUS_V1":
            return result
    except (OSError, ValueError, TypeError):
        pass
    return None


class ResidentSupervisor:
    """Single child, no duplicate launch and bounded rapid restart loop."""

    def __init__(
        self,
        command: list[str],
        *,
        launch: Callable = subprocess.Popen,
        health: Callable[[], dict | None] | None = None,
    ) -> None:
        self.command = command
        self.launch = launch
        self.health = health
        self.child = None
        self.launch_times: list[float] = []

    def tick(self, now: float) -> str:
        if self.child is not None and self.child.poll() is None:
            info = self.health() if self.health else None
            if (info and info.get("schema") == "VERAOS_RESIDENT_STATUS_V1"
                    and info.get("pid") == self.child.pid
                    and info.get("status") == "COMPOSED_NO_COGNITION"
                    and info.get("canonical_runtime_qualified") is False
                    and info.get("cognition_route_qualified") is False
                    and info.get("protected_effect_authority") is False):
                return str(info["status"])
            return "RUNNING_UNVERIFIED"
        self.child = None
        self.launch_times = [t for t in self.launch_times if now - t < 60.0]
        if len(self.launch_times) >= 3:
            return "BLOCKED_RESTART_LIMIT"
        self.child = self.launch(self.command)
        self.launch_times.append(now)
        return "STARTING"

    def close(self) -> None:
        if self.child is not None and self.child.poll() is None:
            self.child.terminate()
            try:
                self.child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.child.kill()
                self.child.wait(timeout=3)


def main(
    argv: list[str] | None = None,
    *,
    source_fixture_execute: Callable[[str, str, object], dict] | None = None,
) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--components-root", type=Path, default=DEFAULT_COMPONENTS)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    args = parser.parse_args(argv)
    status, store = compose_components(args.components_root, args.state_root)
    stop = threading.Event()
    server = None
    http_thread = None
    try:
        # The normal resident ALWAYS owns task intake. No admitted provider
        # means a durable HELD task, never a model dispatch or a fake answer.
        from vera_core.local_conversation import (
            ConversationError, SourceObservationConflict, open_message, recover_message,
            reserve_source_trial, seal_source_observation,
        )
        from vera_core.portal_task_handoff import export_portal_route_request
        from portal.vera_task_handoff import assess_vera_task_route
        from portal import PortalRouteAdvertisement

        class SourceReadbackContradiction(Exception):
            """Persisted source evidence disagrees; HTTP must report UNKNOWN."""

        def verify_source_readback(operation, ledger, worker_store, intake):
            try:
                return operation(ledger, worker_store, intake)
            except SourceObservationConflict as exc:
                # Persisted event/run/route contradiction is UNKNOWN, not
                # a normal provider hold or a retryable task.
                raise SourceReadbackContradiction("source evidence inconsistent") from exc

        fixture_lock = threading.Lock()
        if source_fixture_execute is not None:
            status["conversation_fixture_available"] = True

        def handle_text(task: str, request_id: str,
                        conversation_id: str = "veraos-local-console") -> dict:
            # The client locator identifies a conversation, NOT a user,
            # permission, model, trusted origin, or authenticated principal.
            with fixture_lock:
                pre_active = importlib.import_module("pre_active")
                worker_store = pre_active.Store(args.state_root / "pre-active.sqlite3")
                try:
                    intake = open_message(
                        store.canonical_runtime.tasks,
                        conversation_id, request_id, task,
                    )
                    if source_fixture_execute is None:
                        return {"status": "BLOCKED", "task_id": intake["task_id"]}

                    current = verify_source_readback(
                        recover_message,
                        store.canonical_runtime.tasks, worker_store, intake,
                    )
                    if current["status"] == "SOURCE_COMPLETED_UNSEALED_NO_REDISPATCH":
                        current = verify_source_readback(
                            seal_source_observation,
                            store.canonical_runtime.tasks, worker_store, intake,
                        )
                    if current["status"] == "SOURCE_OBSERVATION_REVALIDATED":
                        # Only an explicitly injected test fixture may return
                        # a synthetic result; no production admitted model.
                        return {
                            "status": "COMPLETED",
                            "run_id": current["source"]["run_id"],
                            "final_text": current["source"]["text"],
                            "task_id": intake["task_id"], "synthetic": True,
                        }
                    if current["status"] != "PENDING_NO_ADMITTED_PROVIDER":
                        return {"status": "BLOCKED", "task_id": intake["task_id"]}

                    # A test-only advertisement cannot authenticate a host.
                    # PORTAL supplies advisory routing; Mono task owns its CAS.
                    advisory = PortalRouteAdvertisement(
                        adapter_id="pre-active-offline-fixture",
                        route_id="offline-fixture", node_id="veraos",
                        target_kind="MODEL", target_id="offline-deterministic",
                        capabilities=("text",),
                        effect_capabilities=("NO_PROTECTED_EFFECT",),
                        authorized_effects=("NO_PROTECTED_EFFECT",),
                        available=True, attached=True, current=True,
                    )
                    request = export_portal_route_request(
                        store.canonical_runtime.tasks, intake["task_id"],
                        node_id="veraos", target_kind="MODEL",
                        target_id="offline-deterministic",
                        required_capabilities=("text",),
                    )
                    assessment = assess_vera_task_route(request, (advisory,))
                    reserve_source_trial(
                        store.canonical_runtime.tasks, intake, assessment,
                        target_id="offline-deterministic",
                        route_id="offline-fixture",
                    )
                    # Source-only deterministic injected callback. The reservation
                    # is durable BEFORE invocation. Any crash/no outcome never
                    # causes a second invocation on subsequent HTTP retries.
                    result = source_fixture_execute(task, intake["task_id"], worker_store)
                    if type(result) is not dict or result.get("status") != "COMPLETED":
                        return {"status": "BLOCKED", "task_id": intake["task_id"]}
                    checked = verify_source_readback(
                        seal_source_observation,
                        store.canonical_runtime.tasks, worker_store, intake,
                    )
                    if checked["status"] != "SOURCE_OBSERVATION_REVALIDATED":
                        return {"status": "BLOCKED", "task_id": intake["task_id"]}
                    if (result.get("run_id") != checked["source"]["run_id"]
                            or result.get("event_id") != checked["source"]["event_id"]
                            or result.get("final_text") != checked["source"]["text"]
                            or result.get("route_id") != "offline-fixture"
                            or result.get("provider_id") != "offline-fixture"):
                        raise ConversationError("injected callback disagrees with persisted source")
                    return {
                        "status": "COMPLETED",
                        "run_id": checked["source"]["run_id"],
                        "final_text": checked["source"]["text"],
                        "task_id": intake["task_id"], "synthetic": True,
                    }
                finally:
                    worker_store.close()

        def handle_history(conversation_id: str) -> list[dict]:
            # Read-only cold context from canonical task + source stores.
            # No new task, model execution, memory admission or redispatch.
            from vera_core.local_conversation import recover_conversation
            with fixture_lock:
                pre_active = importlib.import_module("pre_active")
                worker_store = pre_active.Store(args.state_root / "pre-active.sqlite3")
                try:
                    return recover_conversation(
                        store.canonical_runtime.tasks, worker_store, conversation_id,
                    )
                finally:
                    worker_store.close()

        server = open_loopback_server(
            lambda: status, conversation_handler=handle_text,
            history_handler=handle_history,
        )
        http_thread = threading.Thread(target=server.serve_forever, daemon=True)
        http_thread.start()
        print("VERAOS_RESIDENT_COMPONENTS_COMPOSED_V1", flush=True)
        serve_status(args.run_root, status, stop)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if http_thread is not None:
            http_thread.join(timeout=3.0)
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
