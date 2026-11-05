"""Pure, untrusted PING client-open plan for a future reviewed Win32 peer.

This module deliberately performs NO Win32 calls. It does not create or
connect to a named pipe, send/read bytes, observe a token, accept a response,
or issue a task/grant. A valid local pipe name is NOT server provenance:
same-logon code could create an impostor endpoint. The plan only specifies
the narrow access mask and exact PING message that a separately reviewed
and freshly authorized foreground client would need.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import NoReturn

from .windows_identity_ping import (
    IdentityAuthorityUnavailable, MAX_REQUEST_BYTES, PingRequest, REQUEST_SCHEMA,
)
from .windows_pipe_host import CLIENT_PIPE_ACCESS, FILE_CREATE_PIPE_INSTANCE, MAX_PIPE_FRAME


# Windows file/pipe object rights; Microsoft Learn "Named Pipe Security and
# Access Rights": FILE_GENERIC_WRITE also contains FILE_CREATE_PIPE_INSTANCE.
FILE_READ_DATA = 0x00000001
FILE_WRITE_DATA = 0x00000002
FILE_READ_EA = 0x00000008
FILE_WRITE_EA = 0x00000010
FILE_READ_ATTRIBUTES = 0x00000080
FILE_WRITE_ATTRIBUTES = 0x00000100
READ_CONTROL = 0x00020000
SYNCHRONIZE = 0x00100000
FILE_GENERIC_READ = 0x00120089
FILE_GENERIC_WRITE = 0x00120116
NARROW_CLIENT_ACCESS = (
    FILE_READ_DATA | FILE_WRITE_DATA | FILE_READ_ATTRIBUTES | READ_CONTROL | SYNCHRONIZE
)

# Proposed future CreateFileW parameter values, NOT an executed call.
FILE_SHARE_NONE = 0
OPEN_EXISTING = 3
FILE_FLAGS_NONE = 0
_PIPE_PREFIX = r"\\.\pipe\veraos-ping-"
_SUFFIX = re.compile(r"[0-9a-f]{32}\Z", re.ASCII)


class ClientPlanDenied(ValueError):
    """Unsupported local pipe name, DACL drift, or outbound frame contract."""


@dataclass(frozen=True, slots=True)
class UntrustedPingClientPlan:
    """Source contract only. No HANDLE or authentication token is carried."""

    pipe_name: str
    desired_access: int
    share_mode: int
    creation_disposition: int
    flags_and_attributes: int
    message: bytes


def plan_untrusted_ping(pipe_name: str, raw_request: bytes) -> UntrustedPingClientPlan:
    """Build a bounded single-message plan without touching the host.

    A future client may use these *exact* access rights instead of GENERIC_*
    flags. This does not provide a server-authenticated transport or consent.
    In particular, do not use this plan to exchange credentials or trusted
    grants with a named pipe located solely by an untrusted string.
    """
    if (type(pipe_name) is not str or not pipe_name.startswith(_PIPE_PREFIX)
            or not _SUFFIX.fullmatch(pipe_name[len(_PIPE_PREFIX):])):
        raise ClientPlanDenied("not an exact local VeraOS PING pipe name")
    if (NARROW_CLIENT_ACCESS != CLIENT_PIPE_ACCESS
            or NARROW_CLIENT_ACCESS & FILE_CREATE_PIPE_INSTANCE
            or NARROW_CLIENT_ACCESS & (FILE_READ_EA | FILE_WRITE_EA | FILE_WRITE_ATTRIBUTES)):
        raise ClientPlanDenied("narrow client access diverges from server DACL")

    request = PingRequest.from_wire(raw_request)
    message = json.dumps(
        {"schema": REQUEST_SCHEMA, "action": "PING",
         "request_id": request.request_id, "nonce": request.nonce},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")
    if len(message) > min(MAX_REQUEST_BYTES, MAX_PIPE_FRAME):
        raise ClientPlanDenied("PING exceeds one bounded pipe frame")
    return UntrustedPingClientPlan(
        pipe_name=pipe_name, desired_access=NARROW_CLIENT_ACCESS,
        share_mode=FILE_SHARE_NONE, creation_disposition=OPEN_EXISTING,
        flags_and_attributes=FILE_FLAGS_NONE, message=message,
    )


def reject_untrusted_reply(raw_reply: bytes) -> NoReturn:
    """No server provenance, grant signer, replay verifier, or WSL admission.

    Even a syntactically valid Ed25519-looking signature or a valid JSON
    object is still untrusted. Never promote pipe bytes into authority.
    """
    raise IdentityAuthorityUnavailable(
        "Windows named-pipe reply is not authenticated VeraOS authority")
