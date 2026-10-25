"""A->B->A head-scope regression, using real disposable resident HTTP/Mono ledger."""
import json
import urllib.request

from test_resident_canonical_task import running, post, get_history, resident, STAGE


def test_interleaved_a_b_a_replay_and_history_use_task_heads(tmp_path):
    with running(tmp_path) as base:
        first = post(base, "task A exact literal", "a", "aba")
        second = post(base, "task B exact literal", "b", "aba")
        replay = post(base, "task A exact literal", "a", "aba")
        assert [first[0], second[0], replay[0]] == [202, 202, 202]
        assert first[1]["canonical_intake"] is not None
        assert second[1]["canonical_intake"] is not None
        assert replay[1]["canonical_intake"] == first[1]["canonical_intake"]
        code, history = get_history(base, "aba")
        assert code == 200
        assert [m["status"] for m in history["messages"]] == [
            "PENDING_NO_ADMITTED_PROVIDER", "PENDING_NO_ADMITTED_PROVIDER"]
    # Cold resident replay is still the original task, never a second opener.
    with running(tmp_path) as base:
        replay = post(base, "task A exact literal", "a", "aba")
        assert replay[0] == 202 and replay[1]["canonical_intake"] == first[1]["canonical_intake"]
        assert get_history(base, "aba")[1]["messages"] == history["messages"]
    _, handles = resident.compose_components(STAGE, tmp_path / "state")
    try:
        ledger = handles.canonical_runtime.tasks
        heads = []
        for m in history["messages"]:
            events = ledger.events(m["task_id"])
            assert len(events) == 1 and events[0].event_type == "TASK_OPENED"
            assert m["task_journal_head"] == events[-1].event_digest
            heads.append(events[-1].event_digest)
        assert heads[0] != heads[1]
        assert ledger.verify_chain() != heads[0]  # Valid global chain, different scope.
    finally:
        handles.close()


def test_omitted_conversation_id_legacy_a_b_a_still_acknowledged(tmp_path):
    with running(tmp_path) as base:
        def post_legacy(text, request_id):
            payload = json.dumps({"task": text, "request_id": request_id}).encode()
            req = urllib.request.Request(base + "/api/conversation", data=payload,
                headers={"Origin": base, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=7) as response:
                return response.status, json.loads(response.read())
        a = post_legacy("default task A", "legacy-a")
        b = post_legacy("default task B", "legacy-b")
        again = post_legacy("default task A", "legacy-a")
        assert [a[0], b[0], again[0]] == [202, 202, 202]
        assert a[1]["canonical_intake"] is not None
        assert again[1]["canonical_intake"] == a[1]["canonical_intake"]
        assert a[1]["canonical_intake"]["conversation_id"] == "veraos-local-console"
