"""Source-enforced DEV worker scope; not an OS confinement or authority issuer.

The WSL pilot has same-UID workers with possible Windows mounts/interop. A
caller-supplied observation, signed-looking document or role label must never
turn that developer subprocess into a production worker or effect principal.

This gate permits only two *fixed local fixture execution paths*. It can never
grant protected effects or production isolation. A future real worker broker
requires a separately implemented and host-qualified admission mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass


DEV_INLINE_FIXTURE = "dev-inline-fixture"
DEV_SUBPROCESS_FIXTURE = "dev-subprocess-fixture"


class WorkerExecutionHeld(RuntimeError):
    """A requested scope exceeds the source-only WSL development boundary."""


@dataclass(frozen=True, slots=True)
class WorkerExecutionDecision:
    dev_fixture_allowed: bool
    production_worker_isolation: str
    protected_effects: str
    reasons: tuple[str, ...]


def assess_worker_execution(
    *, operation: object, requested_effects: object = (),
    claimed_isolation_evidence: object = None,
) -> WorkerExecutionDecision:
    """Classify intent, NEVER trusting supplied proof as an OS-backed grant.

    `claimed_isolation_evidence` is deliberately uninspected: it may be a
    mutable dict, forged process report, unvalidated token or malicious object.
    It can be recorded as untrusted input elsewhere but is not an authority
    primitive. Even a favorable *real* kernel snapshot is only an observation,
    not cross-principal denial or independent broker verification.
    """
    del claimed_isolation_evidence
    approved_dev_operation = (type(operation) is str and operation in (
        DEV_INLINE_FIXTURE, DEV_SUBPROCESS_FIXTURE))
    no_effects = type(requested_effects) is tuple and not requested_effects
    allowed = approved_dev_operation and no_effects
    reasons = (
        "os_worker_denial_not_qualified",
        "windows_interop_and_mount_denial_not_qualified",
        "trusted_host_principal_not_qualified",
        "protected_effect_broker_not_qualified",
    )
    if not approved_dev_operation:
        reasons += ("non_development_operation_held",)
    if not no_effects:
        reasons += ("requested_effect_scope_held",)
    return WorkerExecutionDecision(
        dev_fixture_allowed=allowed,
        production_worker_isolation="HOLD",
        protected_effects="DENIED",
        reasons=reasons,
    )


def require_dev_fixture_execution(
    *, operation: object, requested_effects: object = (),
    claimed_isolation_evidence: object = None,
) -> None:
    """Enforce the source-only pilot's fixed operation and empty effect set."""
    decision = assess_worker_execution(
        operation=operation, requested_effects=requested_effects,
        claimed_isolation_evidence=claimed_isolation_evidence,
    )
    if (not decision.dev_fixture_allowed or
            decision.production_worker_isolation != "HOLD" or
            decision.protected_effects != "DENIED"):
        raise WorkerExecutionHeld("worker scope exceeds DEV fixture boundary")
