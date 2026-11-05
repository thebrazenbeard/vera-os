# Wave 12: opt-in native Windows pipe evidence and remaining holds

Date: 2026-11-05. Target: Draft PR #74, `019969a21b3c8c763926f1af504cd8b4b43086ae` (not accepted `main`).

## Observed host test (REAL_SYSTEM_PROBE)

With Patrick's explicit one-time authorization, an in-memory Python 3.14.5 foreground harness on Windows **LAPPY** imported the source-exact `src/veraos/windows_pipe_host.py` from the WSL Draft checkout. The file's SHA-256 was checked as `254d3b1643b227baae8213ee8041c8e84a06ed1a2e9074841f5c113f0ad4a798` and its Git blob was `5080e3a0ded09cd05c27394cf57c6b207cc53ba0`.

- A temporary, random, first-instance-only local Windows named pipe was created with a logon-session DACL and remote-client rejection.
- A same-logon Windows client connected and sent the **raw transport frame** `PING`; the server actually read it before calling `ImpersonateNamedPipeClient`.
- The native `TokenUser` SID and token-authentication LUID observed from the impersonated client matched the test server's own Windows process token. No SID or LUID values were printed.
- The server verified that `RevertToSelf` removed its thread's client token, replied `PONG`, then closed the endpoint. A reopen attempt failed after shutdown.
- Windows probe process exit: **0**; runtime **0.67 seconds**. Blotter recorded the truthful receipt at **#543**, `engineering.windows_pipe_native_ping_verified`.

The one-time script ran from memory rather than being installed as a Windows file/service. The test source itself was not committed with that run; an opt-in test added to the Draft afterward is a *reconstruction*, not the identical byte-for-byte harness. Do not claim the reconstructed test passed native Windows until separately reauthorized and run.

## Scope boundary

This was **Windows transport/token-observation only**, not the VeraOS application PING contract. `windows_identity_ping.PingRequest` expects canonical JSON including schema/action/request ID/nonce. The raw `PING` sent by the native probe was not parsed through that function and never generated a valid grant, authenticated task, consent record, replay receipt, or WSL admission. The Windows source's `EphemeralPipe` is a constructible Python descriptor, not unforgeable host-owned handle custody.

No service installation, scheduled task, host-file ACL edit, firewall change, credential, signing key, account, model load, protected effect, memory admission, merge, or paid operation occurred. The Windows test was a short ephemeral process. Previously observed WSL process/mount/interop conditions still fail production worker-isolation gates.

## Release holds and falsifiers

1. **Server provenance:** a random first-instance pipe with a logon DACL does not by itself authenticate the *server* to a client. A competing same-logon server/name or a caller-crafted descriptor is not rejected by a host-owned service identity. Qualify with separately protected service principal and trusted discovery before consumer admission.
2. **Different-logon denial:** only positive same-logon behavior was observed on Windows. A negative test with another logon/principal is not done and must not be simulated by user-supplied SID text. Creating users, changing ACLs or using elevated tokens requires fresh explicit authorization.
3. **Replay and consent:** no Windows issuer/replay-store/grant signature/consent/owner-session mapping was installed. Linux SQLite same-UID writes and whole-DB rollback remain outside host custody.
4. **Application isolation:** this probe did not exercise actual model inference, a WSL task receiving a Windows-authorized PING, protected-effect broker, private memory bridge, nor a dedicated worker OS principal.

**Do not run native opt-in regression tests automatically in normal CI or development discovery.** They open OS pipe endpoints and require Patrick's separately scoped authorization at the time of execution. A default-skipping test is source infrastructure, not retrospective evidence of a second Windows run.
