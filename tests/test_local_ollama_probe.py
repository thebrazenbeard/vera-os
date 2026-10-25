"""Contract tests for the deliberately narrow local Ollama source probe."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import local_ollama_probe as probe

DIGEST = "a" * 64
OTHER = "b" * 64
MODEL = "vera-local:latest"


class LocalProbeTests(unittest.TestCase):
    def _transport(self, port, method, path, body):
        self.assertEqual(port, 11434)
        if method == "GET":
            self.assertEqual(path, "/api/tags")
            self.assertIsNone(body)
            return {"models": [{"name": MODEL, "digest": DIGEST}]}
        self.assertEqual((method, path), ("POST", "/api/generate"))
        self.assertEqual(body["model"], MODEL)
        self.assertIs(body["stream"], False)
        self.assertLessEqual(body["options"]["num_predict"], 32)
        return {"model": MODEL, "done": True, "response": "READY."}

    def test_manifest_only_is_not_vera_identity(self):
        calls = []

        def read(*args):
            calls.append(args)
            return self._transport(*args)

        result = probe.qualify(MODEL, DIGEST, request_json=read)
        self.assertEqual("MANIFEST_ONLY", result["status"])
        self.assertTrue(result["manifest_digest_verified"])
        self.assertFalse(result["bounded_generation_verified"])
        self.assertFalse(result["vera_adapter_verified"])
        self.assertFalse(result["vera_runtime_verified"])
        self.assertFalse(result["activation_authorized"])
        self.assertEqual(1, len(calls))

    def test_generation_has_fixed_bounded_prompt(self):
        result = probe.qualify(MODEL, DIGEST, generate=True,
                               request_json=self._transport)
        self.assertEqual("MANIFEST_AND_GENERATION", result["status"])
        self.assertTrue(result["bounded_generation_verified"])
        self.assertFalse(result["vera_runtime_verified"])

    def test_digest_mismatch_does_not_generate(self):
        result = probe.qualify(MODEL, OTHER, generate=True,
                               request_json=self._transport)
        self.assertEqual("HOLD", result["status"])
        self.assertFalse(result["bounded_generation_verified"])

    def test_duplicate_model_name_holds(self):
        def duplicate(port, method, path, body):
            return {"models": [{"name": MODEL, "digest": DIGEST},
                               {"name": MODEL, "digest": DIGEST}]}

        self.assertEqual("HOLD", probe.qualify(
            MODEL, DIGEST, request_json=duplicate)["status"])

    def test_wrong_listing_type_holds(self):
        self.assertEqual("HOLD", probe.qualify(
            MODEL, DIGEST, request_json=lambda *args: {"models": {}})["status"])

    def test_generation_model_drift_holds(self):
        def drift(port, method, path, body):
            if method == "GET":
                return self._transport(port, method, path, body)
            return {"model": "other:latest", "done": True, "response": "READY"}

        result = probe.qualify(MODEL, DIGEST, generate=True, request_json=drift)
        self.assertEqual("HOLD", result["status"])
        self.assertTrue(result["manifest_digest_verified"])
        self.assertFalse(result["bounded_generation_verified"])

    def test_generation_done_must_be_boolean(self):
        def false_done(port, method, path, body):
            if method == "GET":
                return self._transport(port, method, path, body)
            return {"model": MODEL, "done": 1, "response": "READY"}

        result = probe.qualify(MODEL, DIGEST, generate=True,
                               request_json=false_done)
        self.assertEqual("HOLD", result["status"])

    def test_network_error_holds(self):
        def unavailable(*args):
            raise OSError("connection denied")

        self.assertEqual("HOLD", probe.qualify(
            MODEL, DIGEST, request_json=unavailable)["status"])

    def test_malformed_http_status_line_fails_closed(self):
        def malformed(*args):
            raise probe.http.client.BadStatusLine("garbled local response")

        result = probe.qualify(MODEL, DIGEST, request_json=malformed)
        self.assertEqual("HOLD", result["status"])
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["manifest_digest_verified"])

    def test_invalid_input_never_opens_network(self):
        for model, digest, port in [
            ("http://other", DIGEST, 11434), (MODEL, "not-a-digest", 11434),
            (MODEL, DIGEST, 0), (MODEL, DIGEST, True),
        ]:
            with self.subTest(model=model, digest=digest, port=port), self.assertRaises(ValueError):
                probe.qualify(model, digest, port, request_json=self._transport)

    def test_nonfinite_and_duplicate_json_rejected(self):
        for raw in [b'{"a":1,"a":2}', b'{"score":NaN}',
                    b'{"v":Infinity}', b'{"v":1e9999}']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                probe._decode_json(raw)

    def test_redirect_rejected_and_loopback_fixed(self):
        class Response:
            status = 302

            def getheader(self, key):
                return None

        class Connection:
            def __init__(self, host, port, timeout):
                self_host.assertEqual("127.0.0.1", host)
                self_host.assertEqual(11434, port)

            def request(self, *args, **kwargs):
                pass

            def getresponse(self):
                return Response()

            def close(self):
                pass

        self_host = self
        with patch.object(probe.http.client, "HTTPConnection", Connection), self.assertRaises(probe.ProbeError):
            probe._request_json(11434, "GET", "/api/tags", None)

    def test_http_response_budget(self):
        class Response:
            status = 200

            def getheader(self, key):
                return str(probe._MAX_RESPONSE + 1)

        class Connection:
            def __init__(self, *args, **kwargs):
                pass

            def request(self, *args, **kwargs):
                pass

            def getresponse(self):
                return Response()

            def close(self):
                pass

        with patch.object(probe.http.client, "HTTPConnection", Connection), self.assertRaises(probe.ProbeError):
            probe._request_json(11434, "GET", "/api/tags", None)


if __name__ == "__main__":
    unittest.main()
