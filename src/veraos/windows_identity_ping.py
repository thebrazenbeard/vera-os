"""Fail-closed source contract for a future *foreground* Windows identity PING.

This module does not create a named pipe, impersonate a Windows client, issue a
grant, launch WSL, or admit a task. It is deliberately *not* a working broker.
No user-supplied SID, LUID, username or Linux UID is identity evidence.

Graduation requires a Windows-owned CreateNamedPipeW endpoint with an explicit
logon-SID DACL and PIPE_REJECT_REMOTE_CLIENTS; per-request
ImpersonateNamedPipeClient + OpenThreadToken + GetTokenInformation(TokenUser,
TokenStatistics), and RevertToSelf on *every* exit path. No injectable/mocked
provider is accepted as deployment evidence. The host-owned mapping, protected
signer, WSL verifier and durable replay ledger are also not implemented.

Microsoft API contracts:
https://learn.microsoft.com/en-us/windows/win32/ipc/impersonating-a-named-pipe-client
https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights
https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-createnamedpipew
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import sys
from typing import Any, Mapping


REQUEST_SCHEMA = "VERAOS_WINDOWS_IDENTITY_PING_REQUEST_V1"
GRANT_SCHEMA = "VERAOS_WINDOWS_IDENTITY_PING_GRANT_V1"
MAX_REQUEST_BYTES = 512
MAX_GRANT_SECONDS = 30
CLOCK_SKEW_SECONDS = 5
_HEX32 = re.compile(r"[0-9a-f]{32}\Z", re.ASCII)
_HEX64 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_HEX128 = re.compile(r"[0-9a-f]{128}\Z", re.ASCII)
_REQUEST_KEYS = frozenset({"schema", "action", "request_id", "nonce"})
_GRANT_KEYS = frozenset({
    "schema", "action", "request_id", "nonce", "request_sha256", "host_id",
    "distro", "linux_uid", "subject_id", "sid_sha256", "logon_luid",
    "issued_at", "expires_at", "revocation_epoch", "signature",
})


class PingDenied(ValueError):
    """Untrusted packet fails its public, non-authorizing shape checks."""


class IdentityAuthorityUnavailable(RuntimeError):
    """A native Windows authority boundary has not been established."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise PingDenied("duplicate JSON field")
        value[key] = item
    return value


@dataclass(frozen=True)
class PingRequest:
    request_id: str
    nonce: str

    @classmethod
    def from_wire(cls, raw: bytes) -> "PingRequest":
        if type(raw) is not bytes or len(raw) > MAX_REQUEST_BYTES or not raw:
            raise PingDenied("invalid request length")
        try:
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
        except (UnicodeError, ValueError) as exc:
            raise PingDenied("invalid request JSON") from exc
        # Exact keys are essential: caller-supplied SID, owner, role, UID,
        # action parameters and even apparently harmless fields are denied.
        if (type(value) is not dict or value.keys() != _REQUEST_KEYS
                or value["schema"] != REQUEST_SCHEMA or value["action"] != "PING"):
            raise PingDenied("PING-only exact request schema required")
        request_id, nonce = value["request_id"], value["nonce"]
        if (type(request_id) is not str or not _HEX32.fullmatch(request_id)
                or type(nonce) is not str or not _HEX32.fullmatch(nonce)):
            raise PingDenied("invalid request ID or nonce")
        return cls(request_id, nonce)

    def sha256(self) -> str:
        canonical = json.dumps({"schema": REQUEST_SCHEMA, "action": "PING",
                                "request_id": self.request_id, "nonce": self.nonce},
                               sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


def preflight_untrusted_grant(
    value: Mapping[str, Any], request: PingRequest, *, now: int,
    expected_host: str, expected_distro: str, expected_uid: int,
    expected_epoch: int,
) -> None:
    """Check claims only. A passing result NEVER authenticates a grant.

    Signature verification, trusted token→subject mapping and durable nonce
    replay admission are absent. This function is intentionally not an auth API.
    """
    if (type(value) is not dict or value.keys() != _GRANT_KEYS
            or value["schema"] != GRANT_SCHEMA or value["action"] != "PING"):
        raise PingDenied("PING-only exact grant schema required")
    for key in ("request_id", "nonce", "host_id", "distro", "subject_id",
                "sid_sha256", "logon_luid", "request_sha256", "signature"):
        if type(value[key]) is not str:
            raise PingDenied("invalid grant string field")
    for key in ("linux_uid", "issued_at", "expires_at", "revocation_epoch"):
        if type(value[key]) is not int:
            raise PingDenied("invalid grant integer field")
    if (not _HEX64.fullmatch(value["request_sha256"])
            or not _HEX64.fullmatch(value["sid_sha256"])
            or not _HEX128.fullmatch(value["signature"])  # proposed Ed25519 encoding
            or not value["subject_id"] or not value["logon_luid"]):
        raise PingDenied("invalid grant evidence shape")
    if (value["request_id"] != request.request_id or value["nonce"] != request.nonce
            or value["request_sha256"] != request.sha256()
            or value["host_id"] != expected_host or value["distro"] != expected_distro
            or value["linux_uid"] != expected_uid
            or value["revocation_epoch"] != expected_epoch):
        raise PingDenied("grant binding or revocation mismatch")
    issued, expires = value["issued_at"], value["expires_at"]
    if (type(now) is not int or expires <= issued
            or expires - issued > MAX_GRANT_SECONDS
            or issued > now + CLOCK_SKEW_SECONDS or expires <= now
            or now - issued > MAX_GRANT_SECONDS + CLOCK_SKEW_SECONDS):
        raise PingDenied("expired or invalid grant interval")


class WindowsNamedPipeTokenProvider:
    """Unprovisioned boundary; no caller-supplied token or injectable fake.

    Implementation must be native Win32 kernel-token observation on the *server*
    end of a verified host-owned pipe. A handle argument alone is insufficient:
    this module has no pipe creation/DACL custody/remote rejection proof.
    """

    def observe_client(self) -> None:
        if sys.platform != "win32":
            raise IdentityAuthorityUnavailable("Windows named-pipe kernel required")
        raise IdentityAuthorityUnavailable(
            "trusted pipe, kernel impersonation and TokenUser acquisition not installed")


def foreground_ping(raw_request: bytes, *, grant: Mapping[str, Any] | None = None) -> None:
    """No authorized PING until native token, grant, replay and receipt gates exist."""
    PingRequest.from_wire(raw_request)
    # The caller cannot install a grant/identity simply by passing JSON.
    if grant is not None:
        raise IdentityAuthorityUnavailable("caller-supplied grant is not authority")
    WindowsNamedPipeTokenProvider().observe_client()
    raise IdentityAuthorityUnavailable("grant signer/replay verifier unavailable")
