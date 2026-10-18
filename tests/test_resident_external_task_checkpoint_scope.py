"""Resident no-provider ACK distinguishes unrelated from own task checkpoint.

Two independent Mono ledger handles share disposable resident state; separate
cold Python-process checkpoint coverage lives in Mono owner regression.
"""
from test_resident_canonical_task import running, post, resident, STAGE


def _checkpoint(tmp_path, task, label):
    _, handles = resident.compose_components(STAGE, tmp_path / "state")
    try:
        ledger = handles.canonical_runtime.tasks
        original = ledger.events(task["task_id"])[0].event_digest
        assert original == task["opened_head"]
        state = ledger.checkpoint(
            task["task_id"], label,
            completed_evidence=("test-only",),
            blockers=("NO_AUTHENTICATED_PROVIDER",),
            protected_effects_still_gated=("PROVIDER_EFFECT",),
            next_frontier="HOLD",
            lifecycle_evidence_digest="a" * 64,
            expected_task_head=original)
        assert not state.closed
        assert ledger.events(task["task_id"])[-1].event_digest != original
        return ledger.verify_chain()
    finally:
        handles.close()


def test_checkpoint_b_does_not_invalidate_a_original_ack(tmp_path):
    with running(tmp_path) as base:
        code_a, first = post(base, "unchanged task A", "a", "checkpoint-scope")
        code_b, second = post(base, "independent task B", "b", "checkpoint-scope")
        assert [code_a, code_b] == [202, 202]
        a = first["canonical_intake"]
        b = second["canonical_intake"]
        assert a and b
        _checkpoint(tmp_path, b, "external-checkpoint-B")
        code, replay = post(base, "unchanged task A", "a", "checkpoint-scope")
        assert code == 202
        assert replay["canonical_intake"] == a
        assert replay["status"] == "BLOCKED"
    with running(tmp_path) as base:
        code, replay = post(base, "unchanged task A", "a", "checkpoint-scope")
        assert code == 202
        assert replay["canonical_intake"] == a


def test_checkpoint_a_invalidates_original_ack_without_provider_admission(tmp_path):
    with running(tmp_path) as base:
        code, first = post(base, "unchanged task A", "a", "checkpoint-own")
        assert code == 202 and first["canonical_intake"]
        a = first["canonical_intake"]
        _checkpoint(tmp_path, a, "external-checkpoint-A")
        code, replay = post(base, "unchanged task A", "a", "checkpoint-own")
        assert code == 202
        assert replay["canonical_intake"] is None
        assert replay["status"] == "BLOCKED"
    with running(tmp_path) as base:
        code, replay = post(base, "unchanged task A", "a", "checkpoint-own")
        assert code == 202 and replay["canonical_intake"] is None
