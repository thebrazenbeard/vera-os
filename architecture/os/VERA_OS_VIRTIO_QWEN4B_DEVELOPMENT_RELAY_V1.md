# VeraOS under-4GB Qwen development relay V1

Exact live local Ollama inventory observed October 16, 2026:
- Model: qwen3:4b-instruct
- Size: 2,497,293,803 bytes, strictly below 4,000,000,000
- Ollama model digest: 0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0
- Quantization: Q4_K_M.

Model presence on Windows is NOT evidence of in-guest reachability, behavior,
admitted production cognition or VerifiedVeraRuntime identity.

## Restricted development transport
QEMU VirtIO serial device name org.veraos.model.v1, guest dev entry
resolved from /sys/class/virtio-ports by exact name. QEMU container uses
network NONE with NO guest NIC (-nic none) and no published ports. The
chardev uses the fixed Unix socket /modelbridge/virtio-model.sock in a
private Docker named volume shared ONLY by the QEMU and relay containers.
An explicitly launched relay container uses Docker Desktop host networking
to connect only to Windows Ollama via host.docker.internal:11434, while
its VirtIO side is Unix-socket-only. Neither guest nor QEMU container
has a network route. No arbitrary destination/URL from the guest is
forwarded. No shell/host effects, remote storage or credentials.
The relay must be explicitly started; no persistent daemon installed.

Protocol is line-delimited bounded JSON on VirtIO serial. Operations
are only models and chat, with exact model and digest/size verification,
bounded message roles/count/length, no tools, non-streaming fixed Ollama
/api/chat options, and framed identity-matched responses. The loopback
OpenAI-compatible guest facade is 127.0.0.1:18766 only. This is an
isolated developer interface, not an arbitrary network proxy.

## Explicit opt-in qualification
A separate rootfs diagnostic init /sbin/vera-virtio-probe must be named
on the QEMU kernel command line to enable the guest probe. Normal
/sbin/vera-init is unchanged. Probe rejects any usable guest NIC while allowing the kernel-created sit0
placeholder only when administratively DOWN, opens the exact VirtIO port, exposes the temporary guest loopback
model facade, calls existing native_cognition P.O.R.T.A.L. and Pre-Active
APIs against the actual pinned staged components, persists a result in
probe-pre-active.sqlite3 and confirms idempotent replay.

**The probe constructs a test-only provider record. Its PASS field is NOT
a source-authenticated independent model qualification.** Consequently,
the default VeraOS resident and dashboard remain no-cognition regardless
of a successful probe. Model outputs cannot create canonical identity,
memory, control-plane authority or protected effects.

## Qualification ceilings
Host unit tests and model inventory prove neither VirtIO connectivity nor
guest model cognition. An exact QEMU test must show the no-NIC marker,
attached pinned model marker, real Pre-Active completed model output,
deduped durable run, bounded serial logs and no protected effects. Then
independent architect review, signed/trustworthy model admission evidence
and normal resident chat UI integration are still required before
production local cognition can be considered installed/qualified.
Never install on Windows, mutate its EFI/partition map, merge PRs, or
grant runtime protected effects on the strength of this package alone.
