# Windows-owned host identity: smallest WSL2 prototype contract

**Status: DESIGN, not implemented or deployed.** Target is a $0, foreground-only identity `PING` vertical slice on Patrick's Lappy. `D:\VERA` remains the authoritative Windows ecosystem root; this proposal neither reauthorizes `C:\VERA` nor changes Windows/WSL configuration.

## Evidence and authority boundary

- **SOURCE:** `vera-os` accepted `main` at `31b66b6ff317eb981c4bd8fcc4ae6e5db1d21adf` has **neither** of the following draft-only WSL modules. Draft #71 proposes `src/veraos/wsl_pilot.py`, a foreground Python/SQLite WAL task prototype with two scoped *logical* workers; stacked Draft #72 proposes `src/veraos/wsl_ipc.py`, Linux AF_UNIX IPC with `SO_PEERCRED` UID checks, socket mode `0600`, and bounded operations. These are not accepted implementation, a Windows identity bridge, installed daemon, running model, or production isolation.
- **TEST/source gap:** `tests/test_wsl_ipc_replay_gap.py` documents the lost-reply/duplicate-admission risk. Existing Python tests and synthetic peer credentials cannot establish Windows SID custody or foreign-UID OS enforcement.
- **PROPOSAL:** [Draft PR #72](https://github.com/thebrazenbeard/vera-os/pull/72) explores IPC/recovery gates; it does not supersede accepted `main` until merged. Related [docs/15-wsl2-windows-identity-and-worker-isolation.md](15-wsl2-windows-identity-and-worker-isolation.md) defines graduation criteria.
- **SOURCE:** `vera-mono/packages/vera_identity/src/vera_identity/resources/schemas/vera_pc_connection_authorization_v1.schema.json` defines `VERA_PCCC_AUTHORIZATION_V1` authorization data, bounded operations (`PING`, `GET_HOST_STATUS`, `READ_TEXT`, `HASH_FILE`), nonce, validity interval, revisions, epochs, digests, and leases. It does **not** itself establish a Windows SID-to-Linux UID mapping. `vera-mono/architecture/VERA_TASK_DELEGATION_OWNERSHIP_V1.json` assigns task-packet authority to `vera_core.TaskExecutionLedger` below a qualified runtime, not to chat/browser callers. `vera-mono/packages/vera_pc_connection/src/pc_connection/state_machine.py` requires fencing, readback and `RECOVERY_REQUIRED` for ambiguous outcomes.

## Proposed smallest executable slice

1. A **foreground, Windows-owned broker** exposes a local Windows named pipe with an explicit DACL for one authorized SID, and rejects remote clients (`PIPE_REJECT_REMOTE_CLIENTS`). Before processing *each* request it impersonates the pipe client, opens the impersonation token, obtains `TokenUser` SID and `TokenStatistics.AuthenticationId` (logon LUID), then always calls `RevertToSelf` in `finally`. It ignores any SID, username or owner field asserted by the caller. No auto-start, service registration, installation, secret export or firewall/ACL mutation is authorized by this design.
2. The broker resolves a **separately reviewed** mapping of observed `(Windows SID, logon LUID, host_id)` to the Vera subject and one explicitly allowed Linux principal. It issues only a bounded `PING` request initially; no effects, private memory, model weights or arbitrary command execution. A signed, short-lived grant binds the observed Windows principal to request ID, job ID, exact operation and digest, host, distro, Linux UID, nonce, validity interval and revocation epoch. A signing key must be provisioned through a future authorized custody flow; use disposable synthetic keys in tests only.
3. A foreground fixed-target `wsl.exe -d Ubuntu-26.04 --exec …` relay transports length-bounded frames over stdin/stdout. Do not pass grants or secrets through process arguments, environment variables, Windows paths or logs. The Linux receiver verifies grant signature, all bound fields, expiry, epoch and unique nonce *before* admitting an operation; it also verifies the actual Linux peer UID where a local socket is used. An allowlisted `PING` returns a durable, redacted receipt.
4. SQLite retains a unique `(issuer_id, nonce)` admission record and idempotent client request ID. An identical replay returns the prior receipt; changed payload with the same ID is denied. A dropped or ambiguous reply requires receipt readback by the same authenticated session; it must not trigger blind resubmission. Windows logoff/revocation invalidates prior grants even if WSL continues running.

| Boundary | Required authority check | Still insufficient against |
| --- | --- | --- |
| Windows caller → named pipe | Kernel token SID + logon LUID from impersonation; restrictive pipe DACL; remote rejection | Malware in the same Windows logon SID, administrators |
| Windows broker → WSL relay | Fixed distro/executable, framed data, verified grant and replay ledger | Compromised Windows broker or WSL root |
| Linux receiver → worker/state | Real OS UID enforcement, separate permissions, fixed operation allowlist and durable receipt | Same-UID processes or WSL root when state shares ownership |
| Worker → protected effect/STM | **Default deny; no forwarding in this prototype** | Host interop or writable Windows mounts if left unrestricted |

## Test contract before any integration claim

All cases below are **required future tests**, not recorded passes. Tests must report Windows build, WSL distro/kernel, exact Git SHA, real SID/UID classes, temp directory mount filesystem, test counts, subprocess return codes, receipts, and redacted error class. Do not log tokens, signing keys, private STM or account identifiers.

| Case | Expected executable result |
| --- | --- |
| One allowed SID/logon session and correct bound `PING` | Exactly one admission, one durable receipt, controlled restart/readback |
| Forged JSON SID/username; unauthorized Windows SID; remote pipe client | Rejection based on kernel-observed identity, not asserted JSON |
| Pipe name squatting, malicious pre-created pipe, broker crash/restart | Endpoint ownership validated; fail closed, no fallback to untrusted pipe |
| Wrong logon LUID, post-logoff session, stale epoch, expired or not-yet-valid grant | Denied before admission despite matching SID |
| Wrong host, distro, UID, operation, packet/parameter digest or signature | Denied without state/effect mutation |
| Exact duplicate nonce/request; conflicting duplicate; lost reply/EOF then retry | Same receipt for identical request, conflict denied, readback after ambiguous result; no duplicate task |
| Foreign Linux UID attempts direct socket, SQLite, audit, key or worker files | Kernel-enforced denial using real distinct UIDs, not mocked credentials |
| `/mnt/c`, `/mnt/d`, Windows executable interop, environment inheritance | Prove inability to bypass broker or read Windows secrets; otherwise mark WSL isolation gate failed |
| Effect tool, model inference, STM ingest, autostart attempt | Strictly unavailable/denied; zero protected effects |

Pre-implementation source test discovery (these command names may have no matching tests yet):

```sh
python -m unittest discover -s tests -p 'test_windows_host_identity*.py' -v
python -m unittest discover -s tests -p 'test_wsl_ipc*.py' -v
```

Read-only host orientation, not pipe-identity evidence:

```powershell
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
[pscustomobject]@{Authenticated=$identity.IsAuthenticated; HasSID=($null -ne $identity.User); AuthType=$identity.AuthenticationType}
wsl.exe --list --verbose
wsl.exe -d Ubuntu-26.04 --exec sh -lc 'id -u; stat -f -c %T /home/vera'
```

Historical **PROBE**, not a fresh run: Lappy showed WSL2 Ubuntu-26.04, Linux user `vera` UID 1000, ext4 under `/home/vera`, `/tmp` on tmpfs, Docker active, and only ~2.2–2.7 GiB free physical Windows RAM. A restart-recovery experiment needs a fresh private directory under `/home/vera` on ext4, **not** `/tmp`; do not load large models or interfere with Docker while memory remains constrained.

## Hostile challenge; decision gates

> **REVIEW:** Windows SID authentication at a named pipe proves an OS token at a boundary, not a human's continuing consent. Same-SID malware can call that pipe. A token-protected process can outlive a logon unless revocation is enforced. The WSL root user and a same-UID worker can bypass application-level checks, and Windows-drive mounts/interop offer an alternate path around Linux permissions. A lost response can duplicate work unless deduplication is durable. Any of these falsifies claims of protected effects or independent worker isolation.

**Stop** on missing kernel token verification, untrusted pipe endpoint, absent logoff/epoch fencing, unavailable persistent replay ledger, writable shared-UID secrets, host interop bypass, lack of a verified Windows→Linux owner mapping, or non-idle/low-memory Lappy. No production or private-memory integration follows from passing a Python test suite. If four genuinely independent principals (state owner, inspector, digester, protected-effect broker), or equivalent kernel-enforced scopes, cannot be enforced and negatively tested in WSL2, prefer a conventional Linux VM or native Linux host for the authority root; keep WSL2 for development and compatibility smoke tests.

Next decision: implement and test the **foreground read-only `PING` bridge** on a throwaway local fixture and capture the exact failure/passing matrix. Request fresh Patrick authorization before any real ACL/key provisioning, service changes, protected effects, machine restart or broader deployment.
