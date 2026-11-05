# Windows narrow-rights PING client: source-only plan

**Status: Draft/HOLD.** Source baseline: VeraOS Draft #74
`048da7c59d72dbbbe718b48d1bda91460e0fda8b`. This change does
not open a Windows named pipe, verify a Windows SID, bridge into WSL, or issue
an authenticated grant. It makes no host or service configuration changes.

## The concrete client/pipe mismatch

`windows_pipe_host.py` deliberately grants the exact Windows logon SID
`0x00120083` on its proposed pipe DACL. Conventional
`CreateFileW(GENERIC_READ | GENERIC_WRITE)` would request bits beyond this
mask, including `FILE_READ_EA`, `FILE_WRITE_ATTRIBUTES` and the
`FILE_CREATE_PIPE_INSTANCE` bit included in generic write. A legitimate
same-logon client could therefore fail the DACL check.

The bounded pure planner `plan_untrusted_ping` instead describes:

| Future CreateFileW field | Proposed value |
| --- | --- |
| `lpFileName` | Exact `\\.\pipe\veraos-ping-` + 32 lowercase hex only |
| `dwDesiredAccess` | `0x00120083`: FILE_READ_DATA, FILE_WRITE_DATA, FILE_READ_ATTRIBUTES, READ_CONTROL, SYNCHRONIZE |
| `dwShareMode` | 0 |
| `dwCreationDisposition` | OPEN_EXISTING (3) |
| `dwFlagsAndAttributes` | 0; no overlapped/read-mode implementation |
| `hTemplateFile` | NULL |

It canonicalizes one strictly validated `VERAOS_WINDOWS_IDENTITY_PING_REQUEST_V1`
message under 512 bytes. It never sends that message. No user-provided SID,
Linux UID, arbitrary command, effect, role or grant field is accepted.

The existing server's `PIPE_READMODE_MESSAGE` **does not imply** a future
client will read messages in that mode. Windows defaults a newly opened
client handle to byte-read mode; changing it may require
`FILE_WRITE_ATTRIBUTES`, deliberately unavailable in this DACL. Therefore
this plan explicitly does **not** implement I/O, timeout, frame reassembly,
or grant response parsing. A reviewed, fully bounded real client needs a
separate design that does not weaken the DACL.

## The stronger hostile objection

> An exact pipe name is not server authentication. A same-logon adversary can
> create an impostor endpoint before the intended host server. A successful
> `CreateFileW` under the narrow mask would at most prove *connection* to
> whatever endpoint owned that name. It cannot authorize sending secrets or
> accepting a signed-looking reply. The server's first-instance-only flag is
> protective once the server actually owns the name, but is not reverse
> authentication for a client.

The present `reject_untrusted_reply` always fails closed. Future promotion
requires source-exact pipe lifecycle/custody, a trusted host public-key or
equivalent OS identity verifier, bounded I/O, nonce replay proof, task/owner
consent binding, and independent host/WSL verification.

## Evidence limit

- **SOURCE:** planner access mask and exact frame validation; no native API.
- **TEST:** pure tests reject unsafe names, generic-rights drift, malformed
  requests, and untrusted replies.
- **HOST PROBE:** none in this increment. Prior native Windows ctypes size
  checks on Lappy do not qualify this client.
- **UNKNOWN:** real DACL interoperability, Windows session token provenance,
  impersonation after last completed read, response delivery, or trusted
  Windows-to-WSL task admission.

Microsoft primary references:
- [Named Pipe Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights)
- [Named Pipe Client](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-client)
- [Named Pipe Type, Read and Wait Modes](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-type-read-and-wait-modes)

No real named-pipe test may be performed on Patrick's hosts without fresh
explicit authorization under the existing repository contract.
