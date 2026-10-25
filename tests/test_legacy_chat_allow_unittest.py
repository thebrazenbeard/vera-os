"""HTTP 405 must explicitly announce that the legacy chat route permits no methods."""
from pathlib import Path
import json
import sys
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class LegacyChatMethodTests(unittest.TestCase):
    def test_disabled_chat_has_empty_allow_header_and_no_cognition(self):
        from veraos.desktop import open_loopback_server

        handler_calls = []

        def forbidden_handler(*args, **kwargs):
            handler_calls.append((args, kwargs))
            return {"status": "UNEXPECTED_COGNITION"}

        server = open_loopback_server(
            lambda: {"status": "COMPOSED_NO_COGNITION"},
            conversation_handler=forbidden_handler,
            port=0,
        )
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        root = f"http://127.0.0.1:{server.server_port}"
        try:
            with self.assertRaises(HTTPError) as caught:
                urlopen(Request(root + "/api/chat", data=b"ignored", method="POST"), timeout=2)
            self.assertEqual(caught.exception.code, 405)
            # RFC 9110 §10.2.1 requires Allow on 405; empty denotes disabled.
            self.assertIn("Allow", caught.exception.headers)
            self.assertEqual(caught.exception.headers["Allow"], "")
            self.assertEqual(json.loads(caught.exception.read())["status"], "METHOD_NOT_ALLOWED")
            with self.assertRaises(HTTPError) as unknown:
                urlopen(Request(root + "/api/unknown", data=b"ignored", method="POST"), timeout=2)
            self.assertEqual(unknown.exception.code, 404)
            self.assertNotIn("Allow", unknown.exception.headers)
            self.assertEqual(handler_calls, [])
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
        self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
