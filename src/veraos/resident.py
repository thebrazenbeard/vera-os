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

    def execute_cognition_fixture(
        self,
        request: dict,
        *,
        host_admission_verifier: Callable[[dict, str, str], str] | None = None,
    ) -> dict:
        """One explicit host-injected, source-fixture-only cognition turn.

        Normal CLI never configures this hook. No real-host verifier is
        installed: even a purported 'VERIFIED_REAL' answer remains HOLD.
        Structural provider PASS is never sufficient to invoke inference.
        """
        required = {"provider", "base_url", "model", "task", "request_id", "now"}
        if type(request) is not dict or set(request) != required:
            raise ValueError("invalid exact resident cognition request")
        if host_admission_verifier is None:
            raise RuntimeError("resident host admission verifier absent: HELD")
        if not callable(host_admission_verifier):
            raise TypeError("host admission verifier must be callable")
        # Host injection is in-process Python only, never CLI/env/HTTP input.
        # This source cut admits only a synthetic development fixture. A real
        # issuer/host verifier MUST be implemented before a real provider route.
        decision = host_admission_verifier(
            request["provider"], request["base_url"], request["model"],
        )
        if decision != "SYNTHETIC_SOURCE_FIXTURE_ONLY":
            raise RuntimeError("real resident provider admission not installed: HELD")
        from .native_cognition import admit_local_text_route, execute_text_request
        portal = importlib.import_module("portal")
        route = admit_local_text_route(
            store=self.pre_active_store, portal=portal,
            provider=request["provider"], base_url=request["base_url"],
            model=request["model"],
        )
        return execute_text_request(
            route, task=request["task"], request_id=request["request_id"],
            now=request["now"],
        )

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
            if (info and info.get("schema", "VERAOS_RESIDENT_STATUS_V1") == "VERAOS_RESIDENT_STATUS_V1"
                    and info.get("pid") == self.child.pid and info.get("status")):
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
    cognition_request: dict | None = None,
    host_admission_verifier: Callable[[dict, str, str], str] | None = None,
    conversation_template: dict | None = None,
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
        if cognition_request is not None:
            store.execute_cognition_fixture(
                cognition_request,
                host_admission_verifier=host_admission_verifier,
            )
        if conversation_template is not None:
            # This is a source-only, in-process fixture injection; normal CLI
            # cannot configure it. No model path is admitted from HTTP input.
            if type(conversation_template) is not dict or set(conversation_template) != {
                "provider", "base_url", "model",
            }:
                raise ValueError("invalid resident conversation template")
            if host_admission_verifier is None:
                raise RuntimeError("resident host admission verifier absent: HELD")
            fixture_lock = threading.Lock()
            status["conversation_fixture_available"] = True

            def handle_text(task: str, request_id: str) -> dict:
                # Serialize all Pre-Active/SQLite writes from HTTP worker
                # threads; stable IDs are durable and replay-safe once terminal.
                with fixture_lock:
                    # ThreadingHTTPServer processes each POST in a worker.
                    # SQLite's main-thread Store connection is NOT transferable.
                    # Reopen the same persistent Pre-Active DB in this worker,
                    # then close its connection in that same worker.
                    pre_active = importlib.import_module("pre_active")
                    worker_store = pre_active.Store(
                        args.state_root / "pre-active.sqlite3",
                    )
                    try:
                        worker_handles = ResidentHandles(
                            worker_store, store.canonical_runtime,
                        )
                        result = worker_handles.execute_cognition_fixture(
                            {
                                **conversation_template,
                                "task": task,
                                "request_id": request_id,
                                "now": time.time(),
                            },
                            host_admission_verifier=host_admission_verifier,
                        )
                        if type(result) is dict and result.get("status") == "COMPLETED":
                            # Reconcile the exact source-only response against
                            # the same durable SQLite event, run, and route.
                            # Mere callback completion is never display proof.
                            run_id = result.get("run_id")
                            event_id = result.get("event_id")
                            text = result.get("final_text")
                            if (type(run_id) is not str or not run_id
                                or type(event_id) is not str or not event_id
                                or type(text) is not str or not text.strip()):
                                return {"status": "OUTCOME_UNKNOWN"}
                            row = worker_store.connection.execute(
                                """
                                SELECT r.id, r.task, r.status, r.final_text,
                                       r.capabilities_json, r.source_event_id,
                                       e.kind, e.payload_json, e.dedup_key
                                FROM runs AS r JOIN events AS e
                                  ON e.id=r.source_event_id
                                WHERE r.id=? AND e.id=?
                                """,
                                (run_id, event_id),
                            ).fetchone()
                            route = worker_store.connection.execute(
                                """
                                SELECT payload_json FROM journal
                                WHERE subject_id=?
                                  AND event_type='VERAOS_COGNITION_ROUTE_SELECTED'
                                ORDER BY seq DESC LIMIT 1
                                """,
                                (event_id,),
                            ).fetchone()
                            try:
                                route_data = json.loads(route["payload_json"]) if route else None
                                event_data = json.loads(row["payload_json"]) if row else None
                                capabilities = json.loads(row["capabilities_json"]) if row else None
                            except (ValueError, TypeError):
                                return {"status": "OUTCOME_UNKNOWN"}
                            if (row is None or row["task"] != task
                                or row["status"] != "COMPLETED"
                                or row["final_text"] != text
                                or row["source_event_id"] != event_id
                                or row["kind"] != "task.requested"
                                or row["dedup_key"] != f"veraos-text:{request_id}"
                                or event_data != {"task": task, "capabilities": []}
                                or capabilities != []
                                or type(route_data) is not dict
                                or route_data.get("provider_id") != conversation_template["provider"]["provider_id"]
                                or route_data.get("model") != conversation_template["model"]
                                or route_data.get("route_id") != result.get("route_id")
                                or route_data.get("effect_class") != "COGNITION_ONLY"
                                or result.get("provider_id") != conversation_template["provider"]["provider_id"]):
                                return {"status": "OUTCOME_UNKNOWN"}
                        return result
                    finally:
                        worker_store.close()

            server = open_loopback_server(
                lambda: status, conversation_handler=handle_text,
            )
        else:
            server = open_loopback_server(lambda: status)
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
