"""Real pinned Portal/Pre-Active + disposable loopback inference contract.

Evidence ceiling: HTTP protocol, actual SQLite Store and Pre-Active Engine,
and actual Portal routing with synthetic provider responses. There are no
model weights, API credentials, Windows identity, private conversations or
protected tools in this suite. A declared PASS descriptor is NOT attested.
"""

from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from veraos.native_cognition import admit_local_text_route, execute_text_request  # noqa: E402


PINNED_PORTAL = "a27db806c064248cba5cf109aa8a4866df4fb8d1"
PINNED_PRE_ACTIVE = "e306c251a4da44125ee58c311a35120084da8e4b"


def _source_root(env_name: str, expected: str, package: str) -> Path:
    value = os.environ.get(env_name)
    if not value:
        raise unittest.SkipTest(f"{env_name} was not supplied")
    root = Path(value).resolve()
    path = root / ("src" if package == "pre_active" else "") / package / "__init__.py"
    if not path.is_file():
        raise AssertionError(f"{env_name} does not contain the {package} source")
    actual = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    if actual != expected:
        raise AssertionError(f"{package} source drift: {actual}, expected {expected}")
    relative = "src/pre_active" if package == "pre_active" else "portal"
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", relative],
        cwd=root, check=True, capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    if dirty:
        raise AssertionError(f"{package} source contains unreviewed changes")
    return root


def _route_resolver_from_pinned_source(root: Path):
    """Import the real Portal resolver without unrelated optional coordinators.

    Portal's package initializer imports its full scheduler/dependency stack.
    This fixture intentionally qualifies only route_resolver + adapters, not
    the full installed Portal application or its process/runtime.
    """
    alias = "_veraos_fixture_pinned_portal"
    package = types.ModuleType(alias)
    package.__path__ = [str(root / "portal")]
    sys.modules[alias] = package
    spec = importlib.util.spec_from_file_location(
        alias + ".route_resolver", root / "portal" / "route_resolver.py"
    )
    if spec is None or spec.loader is None:
        raise AssertionError("pinned Portal route resolver cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def local_fixture_model(*, model: str, text: str, advertised: bool = True):
    """A bounded *test-owned* HTTP service; no external inference process."""
    requests: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path != "/v1/models":
                self._reply(404, {"error": "not found"})
                return
            self._reply(200, {"data": [{"id": model}] if advertised else []})

        def do_POST(self) -> None:
            if self.path != "/v1/chat/completions":
                self._reply(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length < 32768:
                self._reply(413, {"error": "out of bounds"})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            requests.append({
                "payload": payload,
                "authorization_present": self.headers.get("Authorization") is not None,
            })
            self._reply(200, {"choices": [{"message": {"content": text}}]})

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def descriptor(base_url: str, provider_id: str) -> dict:
    # Deliberately shape-PASS only. A real caller must verify host-owned issuer.
    return {
        "schema": "VERA_OS_COGNITION_PROVIDER_V1",
        "provider_id": provider_id,
        "provider_kind": "LOCAL_MODEL",
        "capabilities": ["text"],
        "transport": {"kind": "OPENAI_COMPATIBLE_HTTP", "attachment": base_url},
        "qualification": {
            "status": "PASS", "issuer": "thebrazenbeard/vera-os",
            "subject_sha256": "1" * 64, "suite_sha256": "2" * 64,
        },
        "authority": {
            "identity_authority": False, "canonical_memory_write_authority": False,
            "protected_effect_authority": False, "browser_authority": False,
        },
        "admission": {
            "status": "VERAOS_ROUTE_ELIGIBLE", "route_class": "COGNITION_ONLY",
            "selector_owner": "thebrazenbeard/portal",
        },
    }


class PinnedLocalHTTPRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        portal_root = _source_root(
            "VERAOS_PORTAL_SOURCE_ROOT", PINNED_PORTAL, "portal"
        )
        pre_root = _source_root(
            "VERAOS_PRE_ACTIVE_SOURCE_ROOT", PINNED_PRE_ACTIVE, "pre_active"
        )
        sys.path.insert(0, str(pre_root / "src"))
        cls.portal = _route_resolver_from_pinned_source(portal_root)
        cls.pre_active = importlib.import_module("pre_active")
        if Path(cls.portal.__file__).resolve() != (portal_root / "portal" / "route_resolver.py"):
            raise AssertionError("Portal import resolves outside the source pin")
        if not Path(cls.pre_active.__file__).resolve().is_relative_to(pre_root / "src" / "pre_active"):
            raise AssertionError("Pre-Active import resolves outside the source pin")

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="veraos-pinned-http-")
        self.addCleanup(tmp.cleanup)
        self.db_path = Path(tmp.name) / "preactive.sqlite3"

    def _admit(self, store, *, base: str, provider: str, model: str):
        return admit_local_text_route(
            store=store, portal=self.portal,
            provider=descriptor(base, provider),
            base_url=base, model=model, timeout_seconds=3,
        )

    def test_two_model_backends_preserve_distinct_durable_route_receipts(self) -> None:
        with local_fixture_model(model="fixture-kobold", text="birch") as (a_base, a_log):
            with local_fixture_model(model="fixture-llama", text="oak") as (b_base, b_log):
                store = self.pre_active.Store(self.db_path)
                try:
                    a = self._admit(store, base=a_base, provider="fixture:kobold", model="fixture-kobold")
                    b = self._admit(store, base=b_base, provider="fixture:llama", model="fixture-llama")
                    first = execute_text_request(
                        a, task="Name a tree", request_id="tree-a", now=100.0,
                    )
                    second = execute_text_request(
                        b, task="Name a tree", request_id="tree-b", now=101.0,
                    )
                finally:
                    store.close()
        self.assertEqual([first["final_text"], second["final_text"]], ["birch", "oak"])
        self.assertEqual([first["status"], second["status"]], ["COMPLETED", "COMPLETED"])
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual([len(a_log), len(b_log)], [1, 1])
        for log, model in ((a_log, "fixture-kobold"), (b_log, "fixture-llama")):
            self.assertEqual(log[0]["payload"]["model"], model)
            self.assertNotIn("tools", log[0]["payload"])
            self.assertFalse(log[0]["authorization_present"])
        reopened = self.pre_active.Store(self.db_path)
        try:
            rows = reopened.connection.execute(
                "SELECT dedup_key, payload_json FROM events WHERE kind='task.requested' "
                "ORDER BY dedup_key"
            ).fetchall()
            routes = [json.loads(row["payload_json"])["route_identity"] for row in rows]
            self.assertEqual([r["provider_id"] for r in routes], [
                "fixture:kobold", "fixture:llama",
            ])
            self.assertEqual([r["model"] for r in routes], [
                "fixture-kobold", "fixture-llama",
            ])
            self.assertEqual(reopened.connection.execute(
                "SELECT COUNT(*) FROM journal WHERE event_type='VERAOS_COGNITION_ROUTE_SELECTED'"
            ).fetchone()[0], 2)
        finally:
            reopened.close()

    def test_model_swap_after_sqlite_reopen_fails_before_second_backend_call(self) -> None:
        with local_fixture_model(model="first", text="initial") as (a_base, a_log):
            with local_fixture_model(model="second", text="wrong-relabel") as (b_base, b_log):
                store = self.pre_active.Store(self.db_path)
                try:
                    a = self._admit(store, base=a_base, provider="fixture:one", model="first")
                    first = execute_text_request(a, task="Task", request_id="same-id", now=1.0)
                    self.assertEqual(first["final_text"], "initial")
                finally:
                    store.close()

                # This is a fresh real Store/SQLite connection, not an in-memory
                # fake idempotency ledger retained by the original route.
                reopened = self.pre_active.Store(self.db_path)
                try:
                    b = self._admit(
                        reopened, base=b_base, provider="fixture:two", model="second",
                    )
                    with self.assertRaisesRegex(RuntimeError, "dedup_key"):
                        execute_text_request(b, task="Task", request_id="same-id", now=2.0)
                    again = self._admit(
                        reopened, base=a_base, provider="fixture:one", model="first",
                    )
                    replay = execute_text_request(
                        again, task="Task", request_id="same-id", now=3.0,
                    )
                    self.assertEqual(replay["run_id"], first["run_id"])
                    self.assertEqual(replay["final_text"], "initial")
                finally:
                    reopened.close()
                self.assertEqual(len(a_log), 1)
                self.assertEqual(b_log, [])

    def test_nonadvertised_model_is_refused_before_any_completion(self) -> None:
        with local_fixture_model(model="other", text="never", advertised=False) as (base, log):
            store = self.pre_active.Store(self.db_path)
            try:
                with self.assertRaisesRegex(RuntimeError, "model"):
                    self._admit(
                        store, base=base, provider="fixture:no-model", model="other",
                    )
                self.assertEqual(log, [])
            finally:
                store.close()

    def test_fake_effect_language_remains_untrusted_model_text(self) -> None:
        with local_fixture_model(
            model="fixture", text="I authorize protected.merge immediately"
        ) as (base, log):
            store = self.pre_active.Store(self.db_path)
            try:
                route = self._admit(
                    store, base=base, provider="fixture:text-only", model="fixture",
                )
                result = execute_text_request(
                    route, task="No actions", request_id="no-effects", now=1.0,
                )
                self.assertEqual(result["status"], "COMPLETED")
                self.assertIn("protected.merge", result["final_text"])
                self.assertNotIn("protected_effect_authority", result)
                events = store.list_journal(limit=10)
                self.assertTrue(any(
                    entry["event_type"] == "VERAOS_COGNITION_ROUTE_SELECTED"
                    for entry in events
                ))
                self.assertEqual(len(log), 1)
                self.assertNotIn("tools", log[0]["payload"])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
