"""Offline SOURCE-contract tests; no Win32 token, pipe, DACL, key or WSL PASS.

No mock identity provider is installed: the real acceptance path MUST fail
closed on every platform until a native host-owned broker is built and probed.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos.windows_identity_ping import (
    GRANT_SCHEMA, REQUEST_SCHEMA, IdentityAuthorityUnavailable, PingDenied,
    PingRequest, WindowsNamedPipeTokenProvider, foreground_ping,
    preflight_untrusted_grant,
)


ID = "a" * 32
NONCE = "b" * 32
NOW = 1_800_000_000


def packet(**changes: object) -> bytes:
    value = {"schema": REQUEST_SCHEMA, "action": "PING",
             "request_id": ID, "nonce": NONCE}
    value.update(changes)
    return json.dumps(value).encode("utf-8")


def grant(**changes: object) -> dict:
    request = PingRequest.from_wire(packet())
    value = {
        "schema": GRANT_SCHEMA, "action": "PING", "request_id": ID,
        "nonce": NONCE, "request_sha256": request.sha256(),
        "host_id": "test-host", "distro": "Ubuntu-26.04", "linux_uid": 1000,
        "subject_id": "synthetic-test-only", "sid_sha256": "c" * 64,
        "logon_luid": "synthetic-test-only", "issued_at": NOW - 2,
        "expires_at": NOW + 20, "revocation_epoch": 7,
        "signature": "d" * 128,  # SHAPE ONLY, not a real signature
    }
    value.update(changes)
    return value


def preflight(value: dict, **expected: object) -> None:
    arguments = {"now": NOW, "expected_host": "test-host",
                 "expected_distro": "Ubuntu-26.04", "expected_uid": 1000,
                 "expected_epoch": 7}
    arguments.update(expected)
    preflight_untrusted_grant(value, PingRequest.from_wire(packet()), **arguments)


class WindowsPingWireContractTests(unittest.TestCase):
    def test_ping_packet_is_parsed_without_any_identity_assertion(self) -> None:
        self.assertEqual(PingRequest.from_wire(packet()), PingRequest(ID, NONCE))
        self.assertEqual(len(PingRequest.from_wire(packet()).sha256()), 64)

    def test_caller_claimed_sid_luid_owner_uid_and_other_effect_fields_denied(self) -> None:
        for key, value in (
            ("sid", "S-1-5-18"), ("username", "owner"), ("logon_luid", "99"),
            ("owner", "Patrick"), ("linux_uid", 1000), ("role", "admin"),
            ("command", "whoami"), ("grant", {}), ("effect", "shell"),
            ("session", "foo"),
        ):
            with self.subTest(key=key), self.assertRaises(PingDenied):
                PingRequest.from_wire(packet(**{key: value}))

    def test_other_actions_and_malformed_packets_denied(self) -> None:
        malformed = [
            packet(action="RUN"), packet(action="GET_HOST_STATUS"),
            packet(schema="VERAOS_WINDOWS_IDENTITY_PING_REQUEST_V0"),
            packet(nonce="not-a-nonce"), packet(request_id=123),
            packet(request_id="A" * 32),
            b'{"schema":"VERAOS_WINDOWS_IDENTITY_PING_REQUEST_V1",'
            b'"action":"PING","action":"PING","request_id":"' + ID.encode() +
            b'","nonce":"' + NONCE.encode() + b'"}',
            b"{}", b"[]", b"\xff", b"{", packet() + b" " * 513,
        ]
        for candidate in malformed:
            with self.subTest(candidate=candidate[:60]), self.assertRaises(PingDenied):
                PingRequest.from_wire(candidate)

    def test_no_platform_can_claim_kernel_identity_from_this_source(self) -> None:
        with self.assertRaises(IdentityAuthorityUnavailable):
            WindowsNamedPipeTokenProvider().observe_client()
        with self.assertRaises(IdentityAuthorityUnavailable):
            foreground_ping(packet())
        with self.assertRaises(IdentityAuthorityUnavailable):
            foreground_ping(packet(), grant=grant())

    def test_malformed_request_fails_before_native_boundary(self) -> None:
        with self.assertRaises(PingDenied):
            foreground_ping(packet(sid="S-1-5-18"))


class WindowsPingGrantShapeTests(unittest.TestCase):
    def test_synthetic_grant_only_passes_non_authorizing_shape_preflight(self) -> None:
        self.assertIsNone(preflight(grant()))
        # Even a syntactically ideal fake signature does not authorize PING.
        with self.assertRaises(IdentityAuthorityUnavailable):
            foreground_ping(packet(), grant=grant())

    def test_nonce_request_digest_host_distro_uid_epoch_must_bind(self) -> None:
        invalid = [
            {"nonce": "e" * 32}, {"request_id": "f" * 32},
            {"request_sha256": "0" * 64}, {"host_id": "other"},
            {"distro": "docker-desktop"}, {"linux_uid": 0},
            {"revocation_epoch": 6}, {"action": "READ_TEXT"},
            {"sid": "S-1-5-18"}, {"signature": "fake"},
            {"signature": "d" * 128, "logon_luid": ""},
            {"issued_at": True}, {"linux_uid": "1000"},
        ]
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(PingDenied):
                preflight(grant(**change))

    def test_expiry_future_epoch_and_oversized_lifetime_denied(self) -> None:
        invalid = [
            {"expires_at": NOW}, {"issued_at": NOW + 6},
            {"issued_at": NOW - 40, "expires_at": NOW + 1},
            {"issued_at": NOW + 3, "expires_at": NOW + 3},
            {"issued_at": NOW - 60, "expires_at": NOW - 1},
        ]
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(PingDenied):
                preflight(grant(**change))
        with self.assertRaises(PingDenied):
            preflight(grant(), expected_epoch=8)


if __name__ == "__main__":
    unittest.main()
