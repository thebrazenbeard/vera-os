"""EXPERIMENTAL Win32 source-only, foreground named-pipe token observation.

Not a deployed/validated Windows broker. Importing this module has no effects.
`ephemeral_pipe` can create ONE local named-pipe instance only if deliberately
called on Windows. It has an explicit per-logon-SID DACL, remote-client denial,
and first-instance-only protection. It never installs an ACL on a host file,
service, firewall rule, scheduled task, or persistent endpoint.

`observe_after_read` MUST be called by a future reviewed server only after it
has read a complete bounded PING message from the connected pipe. Microsoft
documents that impersonation refers to the security context of the LAST pipe
message read; merely connecting a pipe is not sufficient. The observation is
kernel-derived evidence, NOT subject mapping, consent, grant, or admission.

There is intentionally NO connect/serve loop, WSL launcher, signing key,
signature verifier, replay ledger, or successful PING response in this source.
Never test real pipe operations on Patrick's hosts without fresh authorization.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import os
import re
import secrets
import sys
from typing import Iterator


# Win32 named-pipe flags. See CreateNamedPipeW (Microsoft Learn).
PIPE_ACCESS_DUPLEX = 0x00000003
FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
PIPE_TYPE_MESSAGE = 0x00000004
PIPE_READMODE_MESSAGE = 0x00000002
PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
PIPE_WAIT = 0x00000000
CLIENT_PIPE_ACCESS = 0x00120083  # RD/WR data, READ_ATTR, READ_CONTROL, SYNCHRONIZE
FILE_CREATE_PIPE_INSTANCE = 0x00000004  # explicitly NOT granted to clients
TOKEN_QUERY = 0x0008
TOKEN_USER = 1
TOKEN_STATISTICS = 10
TOKEN_LOGON_SID = 28
ERROR_INSUFFICIENT_BUFFER = 122
MAX_TOKEN_BYTES = 65536
MAX_PIPE_FRAME = 512
_LOGON_SID = re.compile(r"S-1-5-5-[0-9]+-[0-9]+\Z", re.ASCII)


class WindowsPipeUnavailable(RuntimeError):
    """Native API or pipe security could not be established; deny operation."""


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _TOKEN_USER(ctypes.Structure):
    _fields_ = [("User", _SID_AND_ATTRIBUTES)]


class _TOKEN_GROUPS_ONE(ctypes.Structure):
    _fields_ = [("GroupCount", wintypes.DWORD),
                ("Groups", _SID_AND_ATTRIBUTES * 1)]


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _TOKEN_STATISTICS(ctypes.Structure):
    _fields_ = [
        ("TokenId", _LUID), ("AuthenticationId", _LUID),
        ("ExpirationTime", ctypes.c_longlong),
        ("TokenType", wintypes.DWORD), ("ImpersonationLevel", wintypes.DWORD),
        ("DynamicCharged", wintypes.DWORD),
        ("DynamicAvailable", wintypes.DWORD),
        ("GroupCount", wintypes.DWORD), ("PrivilegeCount", wintypes.DWORD),
        ("ModifiedId", _LUID),
    ]


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("nLength", wintypes.DWORD),
                ("lpSecurityDescriptor", ctypes.c_void_p),
                ("bInheritHandle", wintypes.BOOL)]


@dataclass(frozen=True)
class ObservedWindowsToken:
    """Evidence from impersonated Win32 token, not Vera identity/authorization."""

    user_sid: str
    logon_luid: str


@dataclass(frozen=True)
class EphemeralPipe:
    name: str
    handle: int
    # Captured from the broker process token when the DACL was constructed.
    # This is NOT caller input or an authorization grant.
    owner_logon_sid: str


def _require_windows() -> None:
    if sys.platform != "win32" or os.name != "nt":
        raise WindowsPipeUnavailable("native Windows kernel APIs required")


def _require_native_abi() -> None:
    """Refuse token parsing if native Win32 structure layout is unexpected."""
    pointer = ctypes.sizeof(ctypes.c_void_p)
    if (pointer not in (4, 8) or ctypes.sizeof(wintypes.DWORD) != 4
            or ctypes.sizeof(wintypes.LONG) != 4 or ctypes.sizeof(_LUID) != 8
            or ctypes.sizeof(_SID_AND_ATTRIBUTES) != (16 if pointer == 8 else 8)
            or _SID_AND_ATTRIBUTES.Attributes.offset != pointer
            or ctypes.sizeof(_TOKEN_USER) != (16 if pointer == 8 else 8)
            or ctypes.sizeof(_TOKEN_GROUPS_ONE) != (24 if pointer == 8 else 12)
            or _TOKEN_GROUPS_ONE.Groups.offset != (8 if pointer == 8 else 4)
            or ctypes.sizeof(_TOKEN_STATISTICS) != 56
            or _TOKEN_STATISTICS.AuthenticationId.offset != 8
            or _TOKEN_STATISTICS.ModifiedId.offset != 48
            or ctypes.sizeof(_SECURITY_ATTRIBUTES) != (24 if pointer == 8 else 12)):
        raise WindowsPipeUnavailable("native Windows security ABI mismatch")


def _client_dacl_sddl(logon_sid: str) -> str:
    """Only logon-session client read/write; never FILE_CREATE_PIPE_INSTANCE.

    System retains administrative access; a same-logon attacker is NOT isolated.
    `D:P` makes the DACL protected against inheritance; the caller must supply
    a kernel-observed TokenLogonSid, not user-provided SID or account name.
    """
    if type(logon_sid) is not str or not _LOGON_SID.fullmatch(logon_sid):
        raise WindowsPipeUnavailable("invalid logon SID")
    if CLIENT_PIPE_ACCESS & FILE_CREATE_PIPE_INSTANCE:
        raise WindowsPipeUnavailable("client DACL grants pipe instance creation")
    return (f"D:P(A;;0x{CLIENT_PIPE_ACCESS:08x};;;{logon_sid})"
            "(A;;GA;;;SY)")


def _require_same_logon_sid(owner_logon_sid: str, client_logon_sid: str) -> None:
    """Refuse a client token outside the pipe owner's observed logon SID.

    This is a defense-in-depth post-impersonation check: the pipe DACL also
    grants SYSTEM and may be bypassed by administrators. Passing does not
    establish user consent, verify server custody, or authorize an operation.
    """
    if (type(owner_logon_sid) is not str or type(client_logon_sid) is not str
            or not _LOGON_SID.fullmatch(owner_logon_sid)
            or not _LOGON_SID.fullmatch(client_logon_sid)
            or owner_logon_sid != client_logon_sid):
        raise WindowsPipeUnavailable("pipe client logon session mismatch")


def _bind(dll: object, symbol: str, restype: object, argtypes: list[object]):
    function = getattr(dll, symbol)
    function.restype = restype
    function.argtypes = argtypes
    return function


class _Native:
    """No optional/mock DLL backend. Win32 is loaded only after platform gate."""

    def __init__(self) -> None:
        _require_windows()
        _require_native_abi()
        # LOAD_LIBRARY_SEARCH_SYSTEM32; do not resolve a namesake from cwd/PATH.
        self.adv = ctypes.WinDLL("advapi32.dll", use_last_error=True, winmode=0x800)
        self.kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
        H = wintypes.HANDLE
        D = wintypes.DWORD
        B = wintypes.BOOL
        P = ctypes.c_void_p
        self.OpenProcessToken = _bind(self.adv, "OpenProcessToken", B,
                                      [H, D, ctypes.POINTER(H)])
        self.OpenThreadToken = _bind(self.adv, "OpenThreadToken", B,
                                     [H, D, B, ctypes.POINTER(H)])
        self.GetTokenInformation = _bind(self.adv, "GetTokenInformation", B,
                                         [H, D, P, D, ctypes.POINTER(D)])
        self.ConvertSidToStringSidW = _bind(self.adv, "ConvertSidToStringSidW", B,
                                            [P, ctypes.POINTER(P)])
        self.ConvertStringSD = _bind(
            self.adv, "ConvertStringSecurityDescriptorToSecurityDescriptorW",
            B, [wintypes.LPCWSTR, D, ctypes.POINTER(P), ctypes.POINTER(D)])
        self.ImpersonateNamedPipeClient = _bind(
            self.adv, "ImpersonateNamedPipeClient", B, [H])
        self.RevertToSelf = _bind(self.adv, "RevertToSelf", B, [])
        self.GetCurrentProcess = _bind(self.kernel, "GetCurrentProcess", H, [])
        self.GetCurrentThread = _bind(self.kernel, "GetCurrentThread", H, [])
        self.CreateNamedPipeW = _bind(
            self.kernel, "CreateNamedPipeW", H,
            [wintypes.LPCWSTR, D, D, D, D, D, D,
             ctypes.POINTER(_SECURITY_ATTRIBUTES)])
        self.CloseHandle = _bind(self.kernel, "CloseHandle", B, [H])
        self.LocalFree = _bind(self.kernel, "LocalFree", P, [P])


def _last_error(reason: str) -> WindowsPipeUnavailable:
    # Deliberately redact numerical errors from caller-visible receipts.
    return WindowsPipeUnavailable(reason)


def _token_data(native: _Native, token: int, info_class: int) -> ctypes.Array:
    needed = wintypes.DWORD(0)
    native.GetTokenInformation(token, info_class, None, 0, ctypes.byref(needed))
    if (ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER or needed.value == 0
            or needed.value > MAX_TOKEN_BYTES):
        raise _last_error("token size query denied")
    buf = ctypes.create_string_buffer(needed.value)
    if not native.GetTokenInformation(token, info_class, buf, needed,
                                      ctypes.byref(needed)):
        raise _last_error("token information unavailable")
    return buf


def _sid_string(native: _Native, pointer: int) -> str:
    if not pointer:
        raise WindowsPipeUnavailable("null token SID")
    native_text = ctypes.c_void_p()
    if not native.ConvertSidToStringSidW(pointer, ctypes.byref(native_text)):
        raise _last_error("token SID conversion unavailable")
    try:
        return ctypes.wstring_at(native_text.value)
    finally:
        native.LocalFree(native_text)


def _token_sid(native: _Native, token: int, info_class: int) -> str:
    data = _token_data(native, token, info_class)
    if info_class == TOKEN_USER:
        if len(data) < ctypes.sizeof(_TOKEN_USER):
            raise WindowsPipeUnavailable("short token user information")
        pointer = ctypes.cast(data, ctypes.POINTER(_TOKEN_USER)).contents.User.Sid
    elif info_class == TOKEN_LOGON_SID:
        if len(data) < ctypes.sizeof(_TOKEN_GROUPS_ONE):
            raise WindowsPipeUnavailable("short token logon SID information")
        groups = ctypes.cast(data, ctypes.POINTER(_TOKEN_GROUPS_ONE)).contents
        if groups.GroupCount != 1:
            raise WindowsPipeUnavailable("no unique token logon SID")
        pointer = groups.Groups[0].Sid
    else:
        raise WindowsPipeUnavailable("unsupported token SID class")
    return _sid_string(native, pointer)


def _token_authentication_luid(native: _Native, token: int) -> str:
    data = _token_data(native, token, TOKEN_STATISTICS)
    if len(data) < ctypes.sizeof(_TOKEN_STATISTICS):
        raise WindowsPipeUnavailable("short token statistics")
    luid = ctypes.cast(data, ctypes.POINTER(_TOKEN_STATISTICS)).contents.AuthenticationId
    return f"{int(luid.HighPart) & 0xffffffff:08x}{int(luid.LowPart):08x}"


@contextmanager
def ephemeral_pipe() -> Iterator[EphemeralPipe]:
    """Opt-in, one-instance, non-inheritable host-owned foreground pipe.

    The endpoint is not automatically discoverable and has no accept loop.
    Creating it is a Windows OS action and is NOT performed by source tests.
    """
    native = _Native()
    token = wintypes.HANDLE()
    if not native.OpenProcessToken(native.GetCurrentProcess(), TOKEN_QUERY,
                                   ctypes.byref(token)):
        raise _last_error("host token unavailable")
    try:
        logon_sid = _token_sid(native, token, TOKEN_LOGON_SID)
    finally:
        native.CloseHandle(token)
    sddl = _client_dacl_sddl(logon_sid)
    sd = ctypes.c_void_p()
    if not native.ConvertStringSD(sddl, 1, ctypes.byref(sd), None):
        raise _last_error("explicit pipe security descriptor unavailable")
    try:
        attr = _SECURITY_ATTRIBUTES(ctypes.sizeof(_SECURITY_ATTRIBUTES), sd, False)
        name = r"\\.\pipe\veraos-ping-" + secrets.token_hex(16)
        handle = native.CreateNamedPipeW(
            name, PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT |
            PIPE_REJECT_REMOTE_CLIENTS, 1, MAX_PIPE_FRAME, MAX_PIPE_FRAME,
            0, ctypes.byref(attr))
    finally:
        native.LocalFree(sd)
    if not handle or int(handle) == ctypes.c_void_p(-1).value:
        raise _last_error("secure pipe creation unavailable")
    try:
        yield EphemeralPipe(name=name, handle=int(handle),
                            owner_logon_sid=logon_sid)
    finally:
        native.CloseHandle(handle)


def observe_after_read(pipe: EphemeralPipe) -> ObservedWindowsToken:
    """Kernel-observe the last *successfully read* connected client's token.

    Caller must own the `ephemeral_pipe` handle and must have read a complete
    bounded PING frame itself. This function does not validate that provenance
    and must not by itself be treated as an authentication/grant decision.
    """
    native = _Native()
    if (type(pipe) is not EphemeralPipe or type(pipe.handle) is not int
            or pipe.handle <= 0 or type(pipe.owner_logon_sid) is not str
            or not _LOGON_SID.fullmatch(pipe.owner_logon_sid)):
        raise WindowsPipeUnavailable("invalid server pipe handle")
    # Do not carry an ambient thread impersonation into a new pipe request.
    if not native.RevertToSelf():
        os._exit(70)
    if not native.ImpersonateNamedPipeClient(pipe.handle):
        raise _last_error("pipe client impersonation unavailable")
    token = wintypes.HANDLE()
    try:
        # OpenAsSelf=True accommodates a low impersonation level token.
        if not native.OpenThreadToken(native.GetCurrentThread(), TOKEN_QUERY,
                                      True, ctypes.byref(token)):
            raise _last_error("client impersonation token unavailable")
        sid = _token_sid(native, token, TOKEN_USER)
        client_logon_sid = _token_sid(native, token, TOKEN_LOGON_SID)
        _require_same_logon_sid(pipe.owner_logon_sid, client_logon_sid)
        auth_id = _token_authentication_luid(native, token)
        return ObservedWindowsToken(user_sid=sid, logon_luid=auth_id)
    finally:
        try:
            if token.value:
                native.CloseHandle(token)
        finally:
            if not native.RevertToSelf():
                # Per Microsoft, continuing in the client's security context
                # after a failed revert is unsafe: terminate the process.
                os._exit(70)
