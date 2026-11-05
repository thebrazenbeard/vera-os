# Local-task denial receipt — bounded prototype (Draft/HOLD)

Accepted production authority: **none**. This change does **not** authenticate
Windows clients, bridge a Windows PING to WSL, admit a worker, or execute an
effect. It records an existing local Pilot task ID as expressly untrusted
assertion data, not as the event's authoritative task association.

## Behavior and compatibility

- `Pilot.protected_effect(kind)` remains default-deny and retains its existing
  `events(task_id=NULL, code=PROTECTED_EFFECT_DENIED, detail=kind)` contract.
- `Pilot.protected_effect(kind, task_id=<uuid hex>)` checks whether the task
  exists in this Pilot SQLite DB and has the current Linux owner UID. If yes,
  it writes a denied event with `events.task_id=NULL` and includes the requested
  ID in `detail.asserted_task_id`. If unknown, it writes an **unbound** denial
  with `detail.asserted_task_id=null` rather than falsely attributing an event.
- The structured JSON detail explicitly carries
  `association=CALLER_ASSERTED_EXISTING_LOCAL_TASK` (or
  `UNBOUND_UNKNOWN_LOCAL_TASK`), `authenticated_principal_id=null`, and
  `windows_ping_request_id=null`. The `schema` is
  `VERAOS_LOCAL_TASK_DENIAL_V1`.
- `deny-effect <kind> --task-id <uuid hex>` exercises the same behavior in a
  separate foreground command invocation. No new SQLite columns or schema
  migrations; no production broker exposure.

## Hard boundary

> A task UUID is a correlation label, not a capability token. Any process with
> sufficient same-UID filesystem access can submit a task and assert another
> known task's UUID. Placing that assertion in `events.task_id` would
> contaminate authoritative task history. Keeping `events.task_id=NULL` and
> marking `detail.asserted_task_id` untrusted avoids that confusion. The local
> owner UID is not an authenticated Windows principal. Therefore this receipt
> **does not prove** the Windows PING -> admitted task -> protected-effect chain.

The separate expected-failure test for that missing chain must remain an
expected failure. Successful source tests cannot promote the broker from
default-deny to effects authority. A later protocol needs an authenticated
host-owned admission event, a principal binding, explicit action scope and
consent, and a cryptographic or OS-enforced receipt link before this becomes
eligible for any protected effect dispatch.

## Verification boundary

- Local POSIX/SQLite: `test_wsl_denial_task_receipt.py` (4 passes, 1 skipped
  when the scratch test runner is root), `test_wsl_pilot.py` (14 passes,
  2 skipped). The separate-process CLI scenario must be re-run as an actual
  unprivileged WSL user by the integration owner.
- Native Windows identity, DACL/token impersonation, WSL peer authority,
  external effect, and anti-rollback authority: **NOT VERIFIED**.
