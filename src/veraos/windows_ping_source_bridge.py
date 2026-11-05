"""Non-authorizing, SOURCE-ONLY pairing of PING bytes with token-shaped data.

The read and observation callbacks are explicitly injectable and therefore
UNTRUSTED. They do not establish Windows kernel provenance, pipe ownership,
message completion, consent, grant issuance, or replay protection. This module
never invokes Win32, WSL, a host service, or a protected effect; it cannot
authorize anything even if all supplied values appear valid. A real broker
must implement and independently qualify its own native read/custody path.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Callable

from .windows_identity_ping import MAX_REQUEST_BYTES, PingRequest
from .windows_pipe_host import ObservedWindowsToken


_WINDOWS_SID = re.compile(r"S-1-(?:[0-9]+-)+[0-9]+\Z", re.ASCII)
_AUTH_LUID = re.compile(r"[0-9a-f]{16}\Z", re.ASCII)


class SourcePingBoundaryDenied(RuntimeError):
    """An incomplete/ambiguous source-only input must not produce a receipt."""


@dataclass(frozen=True, slots=True)
class ClaimedCompleteFrame:
    """Caller-controlled read result; `complete` is NOT OS-certified."""

    payload: bytes
    complete: bool


@dataclass(frozen=True, slots=True)
class SourceOnlyDeniedPing:
    """Stable debugging evidence, never a Windows or WSL identity credential."""

    request_sha256: str
    user_sid_claim_sha256: str
    claimed_logon_luid_sha256: str

    @property
    def admission(self) -> str:
        # Do not make this constructor-settable; the caller controls all input.
        return "DENIED"

    @property
    def authority(self) -> str:
        return "SOURCE_ONLY_UNTRUSTED_CALLBACKS"


def pair_untrusted_ping(raw: bytes, token: ObservedWindowsToken) -> SourceOnlyDeniedPing:
    """Strictly parse a PING and bind it to *claimed*, non-authorizing token data.

    The source type `ObservedWindowsToken` can be constructed by a caller.
    Its name is not evidence that a Windows API was actually invoked.
    A digest of SID/LUID is not anonymization or a signing credential.
    """
    request = PingRequest.from_wire(raw)
    if (type(token) is not ObservedWindowsToken or
            type(token.user_sid) is not str or
            _WINDOWS_SID.fullmatch(token.user_sid) is None or
            type(token.logon_luid) is not str or
            _AUTH_LUID.fullmatch(token.logon_luid) is None):
        raise SourcePingBoundaryDenied("untrusted token data malformed; deny")
    # Domain-separated digests are source evidence only. An attacker can forge
    # both input claims and every digest; no verifier should accept this object.
    return SourceOnlyDeniedPing(
        request_sha256=request.sha256(),
        user_sid_claim_sha256=hashlib.sha256(
            b"VERAOS_UNTRUSTED_SID_V1\0" + token.user_sid.encode("ascii")
        ).hexdigest(),
        claimed_logon_luid_sha256=hashlib.sha256(
            b"VERAOS_UNTRUSTED_LUID_V1\0" + token.logon_luid.encode("ascii")
        ).hexdigest(),
    )


def source_read_then_observe_denied(
    read_one: Callable[[int], ClaimedCompleteFrame],
    observe_after_read: Callable[[], ObservedWindowsToken],
) -> SourceOnlyDeniedPing:
    """Check one supplied frame before asking for supplied token observation.

    The read-once callback receives the exact 512-byte maximum. Its
    `complete=True` claim cannot be trusted as a Win32 ReadFile success, and
    callback ordering here cannot prove there were no intervening pipe reads.
    The function intentionally returns DENIED in every success-shaped case.
    """
    if not callable(read_one) or not callable(observe_after_read):
        raise SourcePingBoundaryDenied("read and observe callbacks required; deny")
    frame = read_one(MAX_REQUEST_BYTES)
    if (type(frame) is not ClaimedCompleteFrame or frame.complete is not True or
            type(frame.payload) is not bytes or not 0 < len(frame.payload) <= MAX_REQUEST_BYTES):
        raise SourcePingBoundaryDenied("complete bounded PING frame unavailable; deny")
    # The exact existing parser rejects duplicate keys, caller-supplied SID,
    # effect/grant fields, malformed JSON, schema/action drift and bad nonce.
    PingRequest.from_wire(frame.payload)
    token = observe_after_read()
    return pair_untrusted_ping(frame.payload, token)
