"""Idempotency under concurrent local writers and duplicate received packets."""
import concurrent.futures
from pathlib import Path
import tempfile
import threading
import sqlite3
from contextlib import closing
import unittest
from veraos.federation import FederationError, NodeJournal, Participant, SharedOrientation

WORKERS = 16

def run_concurrent(action, n=WORKERS):
    gate=threading.Barrier(n)
    def call(i):
        gate.wait(timeout=10)
        try:
            return ("OK", action(i))
        except Exception as exc:
            return (type(exc).__name__, str(exc))
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(call,range(n)))


class ConcurrentIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name)
        self.node=NodeJournal(self.dir/"local.sqlite",node_id="VN1")
        self.participant=Participant("Vera","VN1","agent:vn1")

    def record(self, value):
        return self.node.record(self.participant,event_id="same",kind="PROPOSAL",
                                entity="test:subject",predicate="value",
                                value=value,confidence_ppm=500000)

    def test_same_event_in_16_simultaneous_local_calls_is_idempotent(self):
        results=run_concurrent(lambda i:self.record({"observation":True}).digest)
        self.assertTrue(all(k=="OK" for k,v in results), results)
        self.assertEqual(len({v for k,v in results}),1)
        self.assertEqual(len(self.node.events()),1)

    def test_same_payload_in_16_concurrent_receiver_stages_is_idempotent(self):
        event=self.record({"observation":True})
        shared=SharedOrientation(self.dir/"shared.sqlite",leader_node="VN1")
        results=run_concurrent(lambda i:shared.stage(event,authenticated_node_id="VN1"))
        self.assertTrue(all(k=="OK" for k,v in results), results)
        with closing(sqlite3.connect(shared.path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0],1)
        self.assertEqual(shared.orientation().revision,0)

    def test_conflicting_simultaneous_local_event_still_fails_semantically(self):
        results=run_concurrent(lambda i:self.record({"observation": bool(i%2)}))
        types=[x[0] for x in results]
        self.assertEqual(types.count("OK"),8,results)
        self.assertEqual(types.count("FederationError"),8,results)
        self.assertEqual(len(self.node.events()),1)


if __name__=="__main__":
    unittest.main()
