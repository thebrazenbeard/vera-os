# VeraOS WSL2 local pilot (development only)

**Status:** Opt-in source experiment. `src/veraos/wsl_pilot.py` is not `verad`,
an installed VeraOS, a resident model, or a deployable authority service. Do
not infer host readiness or a working Vera identity from successful tests.

## Why WSL2, and where it stops

WSL2 on Lappy is a practical **first Linux execution surface**: a local Linux
kernel, Python/SQLite, disposable state, and a cheap way to run recovery tests
without rebuilding a Buildroot image. Run this from an ordinary Ubuntu user on
WSL's own Linux filesystem, not `/mnt/c`, `/mnt/d`, or a Windows-mounted tree.
The Windows ecosystem root remains **`D:\VERA`**; this disposable pilot does
not replace or write to that root.

The pilot deliberately exposes **no TCP service**. A CLI invokes one of two
fixed workers for a named fixture file in a private test directory:

| Worker | Actual action | Output authority |
| --- | --- | --- |
| `inspect` | Open a regular file under `input/`, report its byte size | No output file |
| `digest` | Read at most 8 KiB under `input/`, calculate SHA-256 | Create one exclusive `<task-id>.sha256` file in `derived/` |

The SQLite task state and append-only event table record submission, atomic
claim, output intent, completion/cancellation, and recovery hold. Conditional
status transitions refuse stale completion/cancellation writes. A cooperating
Linux `flock` lease refuses restart recovery while a live worker is active;
it is not a security control against same-UID code that ignores the lease. The fixed
effect broker rejects every `deny-effect` request and records a denial. It
does not forward shell, Git, network, financial, credential, or host actions.
The CLI uses the **effective Linux UID** as its sole caller identity, owns its
state directory with mode `0700` and database with `0600`, and refuses root.

> **Hostile boundary:** Processes using the *same Linux UID* can access or
> manipulate these files and can bypass Python policy altogether. The pilot
> does not create OS-isolated workers, authenticate individual applications,
> bind Windows users to Linux sessions, protect against a privileged user, or
> make SQLite a tamper-proof audit trail. These are mandatory future gates,
> not features hidden behind the word "governed."

## Bounded smoke test in Ubuntu WSL2

First verify live CPU/RAM headroom and that other WSL/Docker workloads are idle.
Do not stop or restart their processes. The commands below are for an existing
repo checkout under the WSL Linux filesystem and use only Python's standard
library. They do not install packages, start services or load models.

On Lappy, a November 4 read-only probe identified Ubuntu's `vera` user
(UID 1000), running Docker, and roughly 2.7 GiB **free Windows RAM**. Those
values are ephemeral; reprobe immediately before the test. Lappy's `/tmp`
is `tmpfs`, so use a fresh private path below `/home/vera` on the WSL ext4
volume for meaningful disk-backed recovery evidence.

From **Windows PowerShell**, enter the existing distro:

```powershell
wsl -d Ubuntu-26.04
```

Then in the **Ubuntu shell**:

```bash
id -u                 # Must be nonzero
python3 --version
free -m
cd /path/to/vera-os   # A checkout on the Linux filesystem
export PYTHONPATH="$PWD/src"
pilot_parent="$(mktemp -d -p /home/vera -t veraos-wsl-XXXXXXXX)"
pilot_root="$pilot_parent/pilot"
python3 -m veraos.wsl_pilot --root "$pilot_root" init
printf 'VERAOS WSL disposable fixture\n' > "$pilot_root/input/demo.txt"

inspect_id="$(python3 -m veraos.wsl_pilot --root "$pilot_root" submit inspect demo.txt | python3 -c 'import json,sys; print(json.load(sys.stdin)["task_id"])')"
digest_id="$(python3 -m veraos.wsl_pilot --root "$pilot_root" submit digest demo.txt | python3 -c 'import json,sys; print(json.load(sys.stdin)["task_id"])')"
python3 -m veraos.wsl_pilot --root "$pilot_root" run "$inspect_id"
python3 -m veraos.wsl_pilot --root "$pilot_root" run "$digest_id"
python3 -m veraos.wsl_pilot --root "$pilot_root" deny-effect protected.merge
python3 -m veraos.wsl_pilot --root "$pilot_root" status
```

Expected observations: both tasks `COMPLETED`, one `derived/*.sha256` file,
ordered SQLite receipt records, `production_authority: false`,
`model_inference: false`, and `allowed: false` for the protected-effect request.
The digest can be checked independently against `sha256sum` on the fixture.
Treat the JSON output as evidence of *this process and local fixture* only.

For cancel/restart verification, submit two new tasks; cancel one while
`QUEUED`, run the other, and confirm one `CANCELLED` and one `COMPLETED` in
`status`. A controlled interruption should leave a `RUNNING` or
`CANCEL_REQUESTED` task; a new process invoking `recover` must mark it
`RECOVERY_HELD` without replaying effects. The source tests can create the
interruption deterministically:

```bash
python3 -m unittest discover -s tests -p 'test_wsl_pilot.py' -v
```

Do not kill unrelated services or use `wsl --shutdown` for a recovery demo.
Keep the test parent path recorded so it can be inspected and later removed
**by explicit exact path** after the result is preserved. Do not use a broad
cleanup command or move real data into `input/`.

## Verification contract and claim ceiling

Keep separate records for (1) source revision, (2) local unit tests, (3) real
WSL commands and exit statuses, (4) restart/readback, and (5) Windows-side
interop. At minimum preserve:

- Exact Git commit/PR head, WSL distro/kernel, Python and SQLite versions,
  effective UID, filesystem, current available RAM and CPU/load.
- Test command, count, failures/skips and exit code; actual CLI task IDs and
  state transitions; final receipt sequence and output hash.
- A negative path/symlink request, denied protected effect, cancellation,
  interrupted-claim recovery, and duplicate-claim rejection across two
  SQLite clients.
- Whether the pilot was actually run on Lappy WSL2, merely run in another
  Linux environment, or only source-reviewed. Never promote one category
  to another.

Source tests and a WSL CLI smoke test **do not** verify a durable Windows
startup path, network authentication, real per-worker sandboxing, a real model
backend, external effect isolation, GPU acceleration, or installation. An
attached Windows app would need its own host-owned identity binding and
consent checks; loopback/Origin/browser conversation IDs are not credentials.

## WSL versus VM/native Linux

| Surface | Best near-term use | Material blocker as authoritative runtime |
| --- | --- | --- |
| Lappy WSL2 | Fast Python/SQLite CLI and recovery experiments | Windows controls VM lifetime; same-user Windows-drive exposure and interop; not necessarily up after reboot |
| Dedicated Linux VM | More predictable service lifecycle and network/filesystem isolation tests | Resource cost and hypervisor/host startup still need live measurement |
| Native Linux node | Candidate persistent `verad`/state/effect-broker authority | Must first prove hardware availability, backup, update, service and recovery controls |

NixOS remains a candidate OS configuration strategy, not an implication that
WSL needs a NixOS distro or that Nix solves host trust. Compare VM/native
uptime, bounded resource use, worker account separation, filesystem ACLs,
verified backups and protected-effect enforcement before assigning authority.

**Stop conditions:** unexpected Windows/WSL host contention, low free memory,
path resolving into Windows mounts, running as root, production credentials or
private conversations appearing in fixtures, unknown owner/service conflict,
unexpected network egress/listening, missing provenance, or anything requiring
paid services, package installation, restarts or host configuration changes.
Preserve a truthful HOLD result and ask for authority before expanding scope.
