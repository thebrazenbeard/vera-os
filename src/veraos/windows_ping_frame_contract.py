"""SOURCE-ONLY Win32 message-frame checks for a future VeraOS PING broker.

This is not a Win32 read implementation, a server, a replay cache, or an
identity/authorization provider. A native server would have to provide the
`ReadFile` result from its *own* verified pipe HANDLE, exactly once per
message, then call the token-observation API for that same handle. The source
fixture here has no way to prove any of that custody. Its successful result is
always `DENIED`; do not use it as an admission credential.

The Win32 `ReadFile` API can return FALSE with ERROR_MORE_DATA (234) for a
message larger than the supplied buffer in message-read mode. A partial
message must never be token-observed or treated as a valid PING. A successful
Win32 `ReadFile` does not guarantee a meaningful GetLastError value; it is
intentionally not modeled here.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Callable

from .windows_identity_ping import MAX_REQUEST_BYTES, PingRequest, REQUEST_SCHEMA
from .windows_pipe_host import MAX_PIPE_FRAME, ObservedWindowsToken
from .windows_ping_source_bridge import (
    SourceOnlyDeniedPing, SourcePingBoundaryDenied, pair_untrusted_ping,
)


ERROR_MORE_DATA = 234
_MAX_MESSAGE = min(MAX_REQUEST_BYTES, MAX_PIPE_FRAME)


@dataclass(frozen=True, slots=True)
class UntrustedReadFileResult:
    """Caller-constructed fixture, never proof of kernel operation or custody.

    `success` is modeled as exact bool (not truthy int). On failure,
    `win32_error` is the GetLastError value immediately after ReadFile.
    `bytes_read` is the DWORD output, *not* a trusted Python buffer length.
    """

    success: bool
    payload: bytes
    bytes_read: int
    win32_error: int | None = None


def canonical_ping_bytes(request: PingRequest) -> bytes:
    """Encode exactly one PING message with one deterministic representation.

    This is useful for deterministic hashes and replay ledger keys, but does
    not itself implement a nonce store or authenticate a sender/receiver.
    """
    if type(request) is not PingRequest:
        raise SourcePingBoundaryDenied("exact PING request required; deny")
    canonical = json.dumps(
        {"schema": REQUEST_SCHEMA, "action": "PING",
         "request_id": request.request_id, "nonce": request.nonce},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")
    # Reparse because a public dataclass can be constructed without validating
    # fields; a generated frame must not bypass strict source validation.
    if len(canonical) > _MAX_MESSAGE:
        raise SourcePingBoundaryDenied("outbound PING too large; deny")
    PingRequest.from_wire(canonical)
    return canonical


def checked_complete_message(result: UntrustedReadFileResult) -> bytes:
    """Deny failed, truncated, oversized or noncanonical read evidence.

    No Win32 API is invoked. `success=True` and `bytes_read` are untrusted
    caller assertions, not OS evidence. Caller must still establish exact
    HANDLE custody and last-message token association independently.
    """
    if type(result) is not UntrustedReadFileResult:
        raise SourcePingBoundaryDenied("ReadFile result shape unavailable; deny")
    if (result.success is not True or type(result.payload) is not bytes
            or type(result.bytes_read) is not int
            or not 0 < result.bytes_read <= _MAX_MESSAGE
            or result.bytes_read != len(result.payload)
            or result.win32_error is not None):
        # ERROR_MORE_DATA is one common denial, but all failures are denied.
        raise SourcePingBoundaryDenied("complete bounded ReadFile PING absent; deny")
    request = PingRequest.from_wire(result.payload)
    if result.payload != canonical_ping_bytes(request):
        # JSON permits whitespace and reordered keys. Their logical PING may
        # parse, but the proposed wire contract admits only canonical bytes,
        # preventing ambiguous wire framing and digest representations.
        raise SourcePingBoundaryDenied("noncanonical PING encoding; deny")
    return result.payload


def observe_checked_read_untrusted_denied(
    read_once: Callable[[int], UntrustedReadFileResult],
    observe_client_after_read: Callable[[], ObservedWindowsToken],
) -> SourceOnlyDeniedPing:
    """Validate one declared complete canonical frame before token callback.

    Both callbacks are injectable and thus forgeable. Returning a
    `SourceOnlyDeniedPing` is intentional; no successful authorization path
    exists even if a caller invents matching SID/LUID, nonce and byte count.
    """
    if not callable(read_once) or not callable(observe_client_after_read):
        raise SourcePingBoundaryDenied("read/observer callback unavailable; deny")
    result = read_once(_MAX_MESSAGE)
    payload = checked_complete_message(result)
    token = observe_client_after_read()
    return pair_untrusted_ping(payload, token)
