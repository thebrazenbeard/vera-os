"""Source-only preflight for the *server* end of a future Windows PING pipe.

This module does not call Win32, inspect a process, open a pipe, discover a
service, provision a signer, or authenticate VeraOS. Its inputs are all
caller-constructible claims. Even a perfect comparison stays DENIED.

Why this exists: ``FILE_FLAG_FIRST_PIPE_INSTANCE`` and a per-logon pipe DACL
constrain an endpoint but cannot tell the connecting client which process
created it. A same-logon impostor can create a lookalike pipe name. TokenUser
and AuthenticationId collected *from the client* by the server do not solve
this reverse trust problem.

A real issuer needs a separately host-protected discovery/registration root,
a least-privilege service identity distinct from a browser/model process,
client-handle-bound GetNamedPipeServerProcessId, a pinned process handle plus
creation-time checks, kernel-observed token and service SID, image/file
identity matched against host-owned policy, and a protected signing key. A
second PID read cannot alone eliminate PID reuse or process replacement.
After those, signed grant verification, durable replay/consent and receipt
custody remain separate gates. No synthetic field below is proof of them.

Microsoft API reference:
https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeserverprocessid
https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocess
https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import NoReturn


_SID = re.compile(r"S-1-(?:[0-9]+-)+[0-9]+\Z", re.ASCII)
_HEX64 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_HEX16 = re.compile(r"[0-9a-f]{16}\Z", re.ASCII)
_PIPE_NAME = re.compile(r"\\\\\.\\pipe\\veraos-ping-[0-9a-f]{32}\Z", re.ASCII)
MAX_PATH_CHARS = 32767


class ServerProvenanceDenied(ValueError):
    """Invalid synthetic metadata; no trusted Windows server was established."""


class ServerAuthorityUnavailable(RuntimeError):
    """Native issuer custody has not been installed or qualified."""


@dataclass(frozen=True, slots=True)
class ClaimedServerProcess:
    """An untrusted snapshot, NOT a native handle or a server credential.

    ``pid_from_pipe_*`` are nominally two queries against a *held-open client
    pipe handle* before and after inspecting a *held-open process handle*.
    Callers can fabricate them; these fields never certify either handle.
    """

    pipe_name: str
    pid_from_pipe_before: int
    pid_from_process_handle: int
    pid_from_pipe_after: int
    process_created_filetime: int
    image_path: str
    image_sha256: str
    process_user_sid: str
    process_service_sid: str
    process_logon_luid: str


@dataclass(frozen=True, slots=True)
class ClaimedHostIssuerPolicy:
    """A claimed pinset, NOT proof the policy is host-owned/protected.

    `process_user_sid` is the token's user; `service_sid` must separately be
    observed in kernel token groups, not accepted from process command line.
    Path and hash comparisons are useful mismatch tests but are insufficient
    even when the binary is authentic: anyone may execute a readable binary.
    """

    image_path: str
    image_sha256: str
    process_user_sid: str
    service_sid: str


@dataclass(frozen=True, slots=True)
class SourceServerComparison:
    """Only mismatch diagnostics. Cannot be promoted into a grant.

    Its constructor and inputs are forgeable; `admission` is deliberately a
    property returning DENIED, not a caller-supplied boolean.
    """

    checks_matching: bool

    @property
    def admission(self) -> str:
        return "DENIED"

    @property
    def evidence_class(self) -> str:
        return "SOURCE_ONLY_UNTRUSTED_PROCESS_CLAIMS"


def _check_path(path: object) -> bool:
    # Strictly preserve the string supplied by the caller. Case folding,
    # textual normalization or resolving a symlink would create false trust.
    return (type(path) is str and 4 <= len(path) <= MAX_PATH_CHARS
            and path[1:3] == ":\\"
            and ("A" <= path[0] <= "Z" or "a" <= path[0] <= "z")
            and "\x00" not in path and "/" not in path)


def compare_claimed_server_process(
    observed: ClaimedServerProcess, policy: ClaimedHostIssuerPolicy,
) -> SourceServerComparison:
    """Reject contradictions; matching synthetic data is still DENIED.

    This does not prove the claimed process was opened from the named-pipe
    handle, its service SID came from a kernel token, its image was the one
    actually executing, or its policy was protected by Windows ACLs.
    """
    if type(observed) is not ClaimedServerProcess or type(policy) is not ClaimedHostIssuerPolicy:
        raise ServerProvenanceDenied("exact source snapshot/policy types required")
    if (type(observed.pipe_name) is not str
            or _PIPE_NAME.fullmatch(observed.pipe_name) is None):
        raise ServerProvenanceDenied("invalid local named-pipe shape")
    pids = (observed.pid_from_pipe_before, observed.pid_from_process_handle,
            observed.pid_from_pipe_after)
    if any(type(pid) is not int or not 0 < pid < 2**32 for pid in pids):
        raise ServerProvenanceDenied("invalid process identity shape")
    if len(set(pids)) != 1:
        raise ServerProvenanceDenied("named-pipe process PID inconsistency")
    if (type(observed.process_created_filetime) is not int
            or observed.process_created_filetime <= 0):
        raise ServerProvenanceDenied("process lifetime evidence unavailable")
    if not _check_path(observed.image_path) or not _check_path(policy.image_path):
        raise ServerProvenanceDenied("invalid process image path")
    for sha in (observed.image_sha256, policy.image_sha256):
        if type(sha) is not str or _HEX64.fullmatch(sha) is None:
            raise ServerProvenanceDenied("invalid process image digest")
    for sid in (observed.process_user_sid, observed.process_service_sid,
                policy.process_user_sid, policy.service_sid):
        if type(sid) is not str or _SID.fullmatch(sid) is None:
            raise ServerProvenanceDenied("invalid claimed process token SID")
    if (type(observed.process_logon_luid) is not str
            or _HEX16.fullmatch(observed.process_logon_luid) is None):
        raise ServerProvenanceDenied("invalid process authentication LUID")
    if (observed.process_user_sid == observed.process_service_sid
            or policy.process_user_sid == policy.service_sid):
        raise ServerProvenanceDenied("service SID must be separately observed")
    matching = (
        observed.image_path == policy.image_path
        and observed.image_sha256 == policy.image_sha256
        and observed.process_user_sid == policy.process_user_sid
        and observed.process_service_sid == policy.service_sid
    )
    return SourceServerComparison(checks_matching=matching)


def deny_source_only_server_authority(
    comparison: SourceServerComparison,
) -> NoReturn:
    """No application-level trust path from synthetic metadata; fail closed."""
    if type(comparison) is not SourceServerComparison:
        raise ServerProvenanceDenied("unrecognized source-only comparison")
    raise ServerAuthorityUnavailable(
        "host-protected issuer identity, pipe handle binding and signer not available")
