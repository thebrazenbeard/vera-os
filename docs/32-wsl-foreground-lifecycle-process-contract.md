# WSL foreground lifetime and restart: owned-process evidence

**Status:** Development-only, one unprivileged process test. Not installation,
Windows boot integration, authenticated admission, independent worker isolation,
or VeraOS production readiness.

## Exact observations (2026-11-05; Lappy, read-only unless specified)

Source: Draft PR #74 at
`048da7c59d72dbbbe718b48d1bda91460e0fda8b` plus one isolated unmerged
test, `tests/test_wsl_ipc_foreground_lifecycle_process.py`.

- Windows reported 32,491 MiB total physical memory, 5,176 MiB free at the
  sample; CPU load around 16%. These are instantaneous, not resource leases.
- `wsl.exe --version`: WSL 2.7.11.0. Ubuntu-26.04 and `docker-desktop` were
  both Running, WSL version 2. Neither was stopped, restarted, or modified.
- Ubuntu UID 1000, kernel `6.18.33.2-microsoft-standard-WSL2`, Python 3.14.4,
  `systemctl is-system-running` reported `running`, and the native Linux home
  volume reported 970,061 MiB available at inspection.
- Lappy could reach TCP port 22 on the previously identified Linux Mint node
  `192.168.1.71` at the time of the probe. **This does not authenticate a host,
  prove installed services, or qualify Mint as authority.** No SSH login was
  attempted.
- Against the exact Draft head plus only the added test, the test ran as the
  actual unprivileged WSL UID and **passed** (`Ran 1 test in 0.230s`, exit 0).
  It started its own disposable foreground IPC server with budget 2, observed
  a live `status` reply, sent a second request, observed clean exit and removal
  of only that server's socket, then started a second foreground server with
  budget 1 and observed the same result. Task and event tables remained empty.
- Scratch/root unit execution deliberately **skipped** this test; a root
  skip is not host qualification.

## Falsifiable lifecycle boundary

`systemd running` means that Linux's service manager exists inside the
current WSL guest. It says nothing about whether Windows starts this guest
before user sign-in, keeps it alive after logoff/sleep, or resumes the pilot
after a host reboot. The repository does not configure a Windows scheduled
task, service, socket activation, or a systemd unit for the pilot.

The tested clean exit uses the existing server's bounded response budget. A
hard crash may leave a stale AF_UNIX socket; independent Wave8 coverage showed
that a replacement refuses the stale inode until a separately inspected,
test-owned socket is reconciled. This test does **not** simulate a Windows
reboot, forced WSL shutdown, systemd restart, disk power loss, or independent
tamper-resistant state recovery.

## OS candidate tradeoffs — review, not benchmark

| Surface | Known advantage | Unproved authority requirement |
| --- | --- | --- |
| Lappy WSL2 | Existing $0 Python/SQLite source tests and fast isolated Linux process checks | Windows guest lifecycle; Windows filesystem/interop boundary; distinct OS user ownership and host-owned witness |
| Dedicated Linux VM on VN1/VN2 | May provide clearer guest boot, account and state isolation contracts | Exact memory pressure, hypervisor lifecycle, backup, identity custody and cold-start test not measured |
| Native Linux Mint node | Existing SSH port reachability suggests a possible host for follow-up | Hardware/owner identity, persistent uptime, backup, permissions, model capacity, and authenticated actual VeraOS service not measured |

No choice of NixOS, WSL2, Linux VM or Mint is qualified as the production
authority root from these observations. To choose, run an explicitly approved
minimal service through a host cold-start, account-scoped worker denial,
restart recovery against an independently protected checkpoint, and a true
read-only effect receipt. Do not turn a source or localhost test into an
identity/consciousness claim or background persistence promise.

**Effects:** No package/service installation, account/ACL/firewall changes,
WSL/Docker restart, GPU/model load, secrets, persistent startup, external
messages, purchases or deletions. Disposable test fixtures were created and
cleaned by the owned test itself; its development checkout remains available
for evidence until exact-path cleanup is authorized.
