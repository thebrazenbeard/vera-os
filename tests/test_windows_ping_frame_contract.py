"""Linux-safe source fixtures only; never call Win32, WSL or a live host."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veraos.windows_identity_ping import PingDenied, PingRequest, REQUEST_SCHEMA
from veraos.windows_pipe_host import ObservedWindowsToken
from veraos.windows_ping_frame_contract import (
    ERROR_MORE_DATA, UntrustedReadFileResult, canonical_ping_bytes,
    checked_complete_message, observe_checked_read_untrusted_denied,
    SourcePingBoundaryDenied,
)


def canonical() -> bytes:
    return canonical_ping_bytes(PingRequest("a" * 32, "b" * 32))


TOKEN_SHAPE = ObservedWindowsToken("S-1-5-21-1-2-3-1001", "0000000000000444")


class WindowsPingFrameContractTests(unittest.TestCase):
    def test_exact_canonical_frame_has_one_deterministic_digest(self):
        body = canonical()
        self.assertLessEqual(len(body), 512)
        self.assertEqual(checked_complete_message(UntrustedReadFileResult(
            True, body, len(body))), body)
        self.assertEqual(PingRequest.from_wire(body).sha256(),
                         PingRequest("a" * 32, "b" * 32).sha256())

    def test_parseable_but_noncanonical_encodings_are_denied(self):
        request = {"schema": REQUEST_SCHEMA, "action": "PING",
                   "request_id": "a" * 32, "nonce": "b" * 32}
        noncanonical = [
            json.dumps(request).encode("ascii"),
            json.dumps(request, sort_keys=False, separators=(",", ":")).encode("ascii"),
            canonical() + b" ",
            b" " + canonical(),
        ]
        for payload in noncanonical:
            with self.subTest(body=payload[:40]), self.assertRaisesRegex(
                SourcePingBoundaryDenied, "noncanonical"
            ):
                checked_complete_message(UntrustedReadFileResult(
                    True, payload, len(payload)))

    def test_false_read_more_data_or_any_failure_never_observes(self):
        for err in (ERROR_MORE_DATA, 5, 109, None):
            result = UntrustedReadFileResult(False, canonical()[:20], 20, err)
            calls = []
            with self.subTest(err=err), self.assertRaises(SourcePingBoundaryDenied):
                observe_checked_read_untrusted_denied(
                    lambda _cap: result, lambda: calls.append("observed"))
            self.assertEqual(calls, [])

    def test_mismatched_reported_bytes_truncation_oversize_and_bad_types(self):
        body = canonical()
        invalid = [
            UntrustedReadFileResult(True, body, len(body) - 1),
            UntrustedReadFileResult(True, body, len(body) + 1),
            UntrustedReadFileResult(True, body + b" " * 600, len(body) + 600),
            UntrustedReadFileResult(True, body, 0),
            UntrustedReadFileResult(1, body, len(body)),  # type: ignore[arg-type]
            UntrustedReadFileResult(True, body, True),  # type: ignore[arg-type]
            UntrustedReadFileResult(True, body.decode(), len(body)),  # type: ignore[arg-type]
            UntrustedReadFileResult(True, body, len(body), ERROR_MORE_DATA),
            {"success": True, "payload": body, "bytes_read": len(body)},
        ]
        for read in invalid:
            with self.subTest(result=read), self.assertRaises(SourcePingBoundaryDenied):
                checked_complete_message(read)  # type: ignore[arg-type]

    def test_caller_claimed_sid_action_and_duplicate_keys_rejected_before_observe(self):
        bad_frames = [
            canonical()[:-1] + b',"sid":"S-1-5-18"}',
            canonical()[:-1] + b',"action":"PING"}',
            canonical().replace(b'"PING"', b'"RUN"'),
        ]
        for payload in bad_frames:
            calls = []
            with self.subTest(payload=payload[:30]), self.assertRaises(PingDenied):
                observe_checked_read_untrusted_denied(
                    lambda _cap: UntrustedReadFileResult(True, payload, len(payload)),
                    lambda: calls.append(1))
            self.assertEqual(calls, [])

    def test_observe_is_after_exact_read_validation_and_never_grants(self):
        calls = []

        def reader(cap: int) -> UntrustedReadFileResult:
            calls.append(("read", cap))
            return UntrustedReadFileResult(True, canonical(), len(canonical()))

        def observer() -> ObservedWindowsToken:
            calls.append(("observe",))
            return TOKEN_SHAPE

        result = observe_checked_read_untrusted_denied(reader, observer)
        self.assertEqual(calls, [("read", 512), ("observe",)])
        self.assertEqual(result.admission, "DENIED")
        self.assertEqual(result.authority, "SOURCE_ONLY_UNTRUSTED_CALLBACKS")

    def test_replays_and_nonce_changes_do_not_upgrade_source_evidence(self):
        body = canonical()

        def run(frame: bytes):
            return observe_checked_read_untrusted_denied(
                lambda _cap: UntrustedReadFileResult(True, frame, len(frame)),
                lambda: TOKEN_SHAPE)

        same1, same2 = run(body), run(body)
        changed = run(canonical_ping_bytes(PingRequest("a" * 32, "c" * 32)))
        self.assertEqual(same1, same2)  # No replay control in this module
        self.assertNotEqual(same1.request_sha256, changed.request_sha256)
        self.assertEqual({x.admission for x in (same1, same2, changed)}, {"DENIED"})

    def test_public_dataclass_cannot_bypass_outbound_validation(self):
        for request in (PingRequest("A" * 32, "b" * 32),
                        PingRequest("a" * 32, "wrong"),
                        PingRequest("a" * 32, None)):
            with self.subTest(request=request), self.assertRaises(PingDenied):
                canonical_ping_bytes(request)


if __name__ == "__main__":
    unittest.main()
