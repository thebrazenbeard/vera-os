# VeraOS repository instructions

Scope: coding and review agents working in `thebrazenbeard/vera-os`. This
source-visible proprietary repository proposes a governed local runtime; a
checkout, model weight, test pass, or ChatGPT conversation is not evidence of
an installed or continuously running VeraOS.

## Authority and source of truth

- Inspect live accepted `main`, relevant source/tests, repo documentation,
  workflows and current draft PR heads before making state claims or edits.
  Accepted main outranks a draft; keep commits and evidence classes separate.
- Vera is the proposed governed agent/runtime; local and hosted models are
  replaceable cognition engines. Conversations are interfaces, not containers.
  Identity, experience and nonbiological life are open questions, not product
  implementation claims.
- `D:\VERA` is the authoritative Windows ecosystem root. `C:\VERA` is
  obsolete. Historical `D:\VeraOS` prototype paths must not be silently
  rewritten or assumed active.
- Keep the budget at **$0**. Do not incur compute, hosting, API, billing or
  provisioning costs without fresh explicit authorization.
- Preserve repository ownership, proprietary source and third-party licenses.
  Do not copy private data into public/source-visible repositories.

## Runtime and trust boundaries

- WSL2 on Lappy is a **development and test surface**, not the default
  production authority root. NixOS is a candidate, not an accepted base.
  Historic Debian/Buildroot evidence is historical, not a current host probe.
- Target Patrick-controlled **Windows/Linux** hosts. Local GGUF inference
  through KoboldCPP or llama.cpp remains a measured compatibility target,
  not an installed model claim. Keep model binaries out of Git and avoid
  permanent duplicate weights on Lappy; prefer external artifact custody
  with manifests and checksums.
- A Linux UID or `SO_PEERCRED` result is not a Windows SID, logon session,
  authenticated human, consent grant, or protected-effect authorization.
  Browser Origin, localhost and `X-Vera-Session` are not personal credentials.
- Same-UID Python subprocesses do not constitute OS worker isolation. Require
  tested kernel/ACL/namespace/VM confinement and separate least-privilege
  principals before qualifying independent workers. WSL Windows-drive mounts
  and executable interop are potential bypasses; record actual mount,
  capability and interop probes, and hold isolation until denial is tested.
- Default-deny protected effects, model-initiated external actions, private
  memory admission, credentials, host configuration, service installation,
  autostart, restarts, remote exposure and production changes. A future
  effect broker requires verified caller authority, explicit consent, a
  specific capability and a durable receipt.
- Do not treat a model's self-description, persona source, GGUF artifact,
  synthetic inference or model consensus as identity or system verification.
- Keep task state, private memory, identity/orientation, consent, permissions,
  audit receipts, secrets, model artifacts, derived indexes and worktrees in
  separately governed state classes. Never automatically import chat archives.

## Work, testing and review

- Work in bounded, reversible, isolated branches/worktrees. Do not overwrite
  another agent's changes or broaden authority by implication. No merge,
  force-push, release, deletion, credential/ACL change, paid service or
  production deployment without the required explicit authorization.
- Prefer the smallest executable local slice: authenticated session, durable
  task, scoped worker, governed tool, receipt, cancellation and restart
  recovery. Do not substitute architecture prose for available source tests.
- Separate `SOURCE`, `TEST`, `CI`, `HOST_PROBE`, `MODEL_REVIEW` and
  independent human/external review. Record exact git heads, commands, test
  counts, skips, expected failures, exit codes and environment. A model
  review is not an external security audit.
- The current draft WSL Python suites use
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_wsl*.py' -q`.
  Run narrower relevant tests first, then proportionate adjacent tests and
  exact-head unprivileged host qualification if safely available. Never
  declare a Windows-native, model or production test passed from a Linux
  source fixture.
- For authority, recovery, memory and isolation changes, actively reproduce
  hostile counterexamples and retain unresolved objections as release holds.
  Fail closed when issuer, owner, revision, grant, replay state or recovery
  custody is ambiguous.
- Check an authorized Blotter's last 20 entries and append a truthful
  checkpoint when its real interface is available; otherwise state that
  continuity evidence was unavailable. Do not fabricate updates.

No native ChatGPT subagent label, proposal name or protocol document itself
establishes an installed worker or background execution capability.
