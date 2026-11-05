"""Linux-safe SOURCE tests; no Win32 call, Windows issuer, WSL or grants."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos.windows_identity_ping import PingDenied, REQUEST_SCHEMA  # noqa: E402
from veraos.windows_pipe_host import ObservedWindowsToken  # noqa: E402
from veraos.windows_ping_source_bridge import (  # noqa: E402
    ClaimedCompleteFrame, SourceOnlyDeniedPing, SourcePingBoundaryDenied,
    pair_untrusted_ping, source_read_then_observe_denied,
)


def packet(nonce: str = "b" * 32, **injection: object) -> bytes:
    obj = {"schema": REQUEST_SCHEMA, "action": "PING",
           "request_id": "a" * 32, "nonce": nonce}
    obj.update(injection)
    return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("ascii")


OBSERVED_SHAPE = ObservedWindowsToken(user_sid="S-1-5-21-1-2-3-1001",
                                      logon_luid="0000000000000444")


class SourceOnlyPingBridgeTests(unittest.TestCase):
    def test_valid_pair_is_unconditionally_denied_and_domain_separated(self) -> None:
        result = pair_untrusted_ping(packet(), OBSERVED_SHAPE)
        self.assertIs(type(result), SourceOnlyDeniedPing)
        self.assertEqual(result.admission, "DENIED")
        self.assertEqual(result.authority, "SOURCE_ONLY_UNTRUSTED_CALLBACKS")
        self.assertEqual(len(result.request_sha256), 64)
        self.assertEqual(result.user_sid_claim_sha256, hashlib.sha256(
            b"VERAOS_UNTRUSTED_SID_V1\0S-1-5-21-1-2-3-1001").hexdigest())
        self.assertEqual(result.claimed_logon_luid_sha256, hashlib.sha256(
            b"VERAOS_UNTRUSTED_LUID_V1\0" +
            OBSERVED_SHAPE.logon_luid.encode("ascii")).hexdigest())
        self.assertNotIn(OBSERVED_SHAPE.user_sid, repr(result))
        self.assertNotIn(OBSERVED_SHAPE.logon_luid, repr(result))

    def test_one_bounded_complete_frame_then_token_observation(self) -> None:
        calls = []

        def read_once(max_bytes: int) -> ClaimedCompleteFrame:
            calls.append(("read", max_bytes))
            return ClaimedCompleteFrame(packet(), True)

        def observe_after() -> ObservedWindowsToken:
            calls.append(("observe",))
            return OBSERVED_SHAPE

        result = source_read_then_observe_denied(read_once, observe_after)
        self.assertEqual(calls, [("read", 512), ("observe",)])
        self.assertEqual(result.admission, "DENIED")

    def test_replay_and_changed_nonce_remain_denied_not_host_authenticated(self) -> None:
        first = pair_untrusted_ping(packet(), OBSERVED_SHAPE)
        replayed = pair_untrusted_ping(packet(), OBSERVED_SHAPE)
        other = pair_untrusted_ping(packet(nonce="c" * 32), OBSERVED_SHAPE)
        self.assertEqual(first, replayed)  # deterministic, NOT a replay guard
        self.assertNotEqual(first.request_sha256, other.request_sha256)
        self.assertEqual({r.admission for r in (first, replayed, other)}, {"DENIED"})

    def test_duplicate_keys_and_asserted_authority_never_reach_observer(self) -> None:
        bad = [
            b'{"schema":"' + REQUEST_SCHEMA.encode() + b'","action":"PING",'
            b'"action":"PING","request_id":"' + b"a" * 32 +
            b'","nonce":"' + b"b" * 32 + b'"}',
            packet(sid="S-1-5-18"),
            packet(logon_luid="0000000000000444"),
            packet(grant={"signature": "fake"}),
            packet(action="RUN"),
            packet(effect="delete"),
            b"PING",
        ]
        for body in bad:
            with self.subTest(body=body[:70]):
                count = []

                def reader(_max: int) -> ClaimedCompleteFrame:
                    return ClaimedCompleteFrame(body, True)

                def observer() -> ObservedWindowsToken:
                    count.append(1)
                    return OBSERVED_SHAPE

                with self.assertRaises(PingDenied):
                    source_read_then_observe_denied(reader, observer)
                self.assertEqual(count, [])

    def test_incomplete_oversized_wrong_type_are_denied_before_observer(self) -> None:
        invalid = [
            ClaimedCompleteFrame(packet(), False),
            ClaimedCompleteFrame(b"", True),
            ClaimedCompleteFrame(packet() + b" " * 513, True),
            ClaimedCompleteFrame("str instead of bytes", True),  # type: ignore[arg-type]
            {"payload": packet(), "complete": True},
        ]
        for frame in invalid:
            called = []
            with self.subTest(frame=type(frame)), self.assertRaises(SourcePingBoundaryDenied):
                source_read_then_observe_denied(
                    lambda n: frame, lambda: called.append(1))  # type: ignore[arg-type]
            self.assertEqual(called, [])

    def test_token_shape_is_untrusted_and_malformed_claims_are_rejected(self) -> None:
        bad = [
            None,
            {"user_sid": OBSERVED_SHAPE.user_sid,
             "logon_luid": OBSERVED_SHAPE.logon_luid},
            ObservedWindowsToken("not-SID", OBSERVED_SHAPE.logon_luid),
            ObservedWindowsToken(OBSERVED_SHAPE.user_sid, "not-luid"),
            ObservedWindowsToken("S-1-5-18\n", OBSERVED_SHAPE.logon_luid),
        ]
        for token in bad:
            with self.subTest(token=token), self.assertRaises(SourcePingBoundaryDenied):
                pair_untrusted_ping(packet(), token)  # type: ignore[arg-type]
        # Even a syntactically convincing forged SYSTEM claim stays denied.
        self.assertEqual(pair_untrusted_ping(
            packet(), ObservedWindowsToken("S-1-5-18", "0000000000000001")
        ).admission, "DENIED")

    def test_observer_failure_is_not_swallowed_or_converted_to_admission(self) -> None:
        def fail() -> ObservedWindowsToken:
            raise RuntimeError("native observation unavailable")

        with self.assertRaisesRegex(RuntimeError, "native observation unavailable"):
            source_read_then_observe_denied(
                lambda _max: ClaimedCompleteFrame(packet(), True), fail)

    def test_no_authority_or_runtime_effect_entrypoint(self) -> None:
        import veraos.windows_ping_source_bridge as bridge
        for name in ("authorize", "issue_grant", "verify_grant", "admit_task",
                     "serve", "connect", "run_wsl", "protected_effect"):
            self.assertFalse(hasattr(bridge, name))
        self.assertEqual(SourceOnlyDeniedPing("a" * 64, "b" * 64,
                                              "c" * 64).admission, "DENIED")
        with self.assertRaises(TypeError):
            SourceOnlyDeniedPing("a" * 64, "b" * 64, "c" * 64,
                                 admission="GRANTED")  # type: ignore[call-arg]


if __name__ == "__main__":
    unittest.main()
