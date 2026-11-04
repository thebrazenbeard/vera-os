import dataclasses
import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from veraos.learning_boundary import (SyntheticEvent, QuarantineJournal, CandidateRef,
                                      EvaluationRef, GenerationSnapshot, production_admitted)


def event(**changes):
    value = dict(schema="synthetic-event-v1", event_id="a" * 32, seed=7,
                 action=3, outcome=1, generation_sha256="b" * 64)
    value.update(changes)
    return json.dumps(value)


def candidate(**changes):
    values = dict(base_sha256="a" * 64, tokenizer_sha256="b" * 64,
                  template_sha256="c" * 64, config_sha256="d" * 64,
                  adapter_sha256="e" * 64)
    values.update(changes)
    return CandidateRef(**values)


class BoundaryTests(unittest.TestCase):
    def test_strict_parse_rejects_extra_actor_consent_and_ambiguous_json(self):
        for raw in (event(actor="authenticated"), event(consent=True), event(seed=True),
                    event(outcome=2), event(generation_sha256="A" * 64),
                    event().replace('"seed": 7', '"seed": 7, "seed": 8'),
                    event() + " " * 513):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                SyntheticEvent.parse(raw)

    def test_string_subclass_cannot_bypass_event_size_limit(self):
        class ForgedRaw(str):
            def encode(self, *args, **kwargs):
                return b""

        with self.assertRaises(ValueError):
            SyntheticEvent.parse(ForgedRaw(event() + " " * 513))

    def test_replay_conflict_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.sqlite"
            journal = QuarantineJournal(path)
            original = SyntheticEvent.parse(event())
            self.assertTrue(journal.append(original))
            self.assertFalse(journal.append(SyntheticEvent.parse(event())))
            with self.assertRaises(ValueError):
                journal.append(SyntheticEvent.parse(event(outcome=0)))
            journal.close()
            journal = QuarantineJournal(path)
            self.assertFalse(journal.append(original))
            self.assertEqual(journal.db.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 1)
            journal.close()

    def test_orderly_close_rolls_back_uncommitted_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.sqlite"
            journal = QuarantineJournal(path)
            journal.db.execute("BEGIN")
            journal.db.execute("INSERT INTO synthetic_events VALUES (?, ?)", ("a" * 32, "partial"))
            journal.close()  # SQLite rolls back an uncommitted transaction.
            journal = QuarantineJournal(path)
            self.assertTrue(journal.append(SyntheticEvent.parse(event())))
            journal.close()

    def test_concurrent_identical_appends_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.sqlite"
            QuarantineJournal(path).close()
            barrier = threading.Barrier(2)

            def append():
                journal = QuarantineJournal(path)
                try:
                    barrier.wait(timeout=5)
                    return journal.append(SyntheticEvent.parse(event()))
                finally:
                    journal.close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: append(), range(2)))
            self.assertEqual(sorted(results), [False, True])
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 1)

    def test_subclass_cannot_override_canonical_storage(self):
        class ForgedEvent(SyntheticEvent):
            def canonical(self):
                return '{"real_data":"foreign"}'

        with tempfile.TemporaryDirectory() as tmp:
            journal = QuarantineJournal(Path(tmp) / "journal.sqlite")
            with self.assertRaises(ValueError):
                journal.append(ForgedEvent("a" * 32, 1, 2, 1, "b" * 64))
            self.assertEqual(journal.db.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 0)
            journal.close()

    def test_direct_construction_is_revalidated(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = QuarantineJournal(Path(tmp) / "journal.sqlite")
            with self.assertRaises(ValueError):
                journal.append(SyntheticEvent("a" * 32, True, 2, 1, "b" * 64))
            journal.close()

    def test_snapshot_lineage_and_immutable_shape(self):
        c = candidate()
        evaluation = EvaluationRef(c, "f" * 64)
        snap = GenerationSnapshot("1" * 32, c, evaluation)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            snap.request_id = "2" * 32
        for key in c.__dict__:
            with self.subTest(key=key), self.assertRaises(ValueError):
                GenerationSnapshot("1" * 32, candidate(**{key: "0" * 64}), evaluation)
        with self.assertRaises(ValueError):
            EvaluationRef(c, "not-a-hash")

    def test_self_asserted_pass_or_approval_never_admits(self):
        for claim in ({}, {"pass": True}, {"authenticated": True, "consent": True},
                      {"candidate": candidate(), "issuer": "vera-os"}):
            self.assertIs(production_admitted(**claim), False)

    def test_subclass_cannot_forge_lineage_equality(self):
        class ForgedCandidate(CandidateRef):
            def __eq__(self, other):
                return True

        class ForgedEvaluation(EvaluationRef):
            pass

        real = candidate()
        forged = ForgedCandidate(**candidate(base_sha256="0" * 64).__dict__)
        evaluation = EvaluationRef(real, "f" * 64)
        with self.assertRaises(ValueError):
            EvaluationRef(forged, "f" * 64)
        with self.assertRaises(ValueError):
            GenerationSnapshot("1" * 32, forged, evaluation)
        with self.assertRaises(ValueError):
            GenerationSnapshot("1" * 32, real, ForgedEvaluation(real, "f" * 64))

    def test_string_subclass_cannot_forge_reference_equality(self):
        class ForgedString(str):
            def __eq__(self, other):
                return True

        with self.assertRaises(ValueError):
            candidate(base_sha256=ForgedString("0" * 64))
        real = candidate()
        with self.assertRaises(ValueError):
            GenerationSnapshot(ForgedString("1" * 32), real, EvaluationRef(real, "f" * 64))
        with tempfile.TemporaryDirectory() as tmp:
            journal = QuarantineJournal(Path(tmp) / "journal.sqlite")
            with self.assertRaises(ValueError):
                journal.append(SyntheticEvent(ForgedString("a" * 32), 1, 2, 1, "b" * 64))
            with self.assertRaises(ValueError):
                journal.append(SyntheticEvent("a" * 32, 1, 2, 1, ForgedString("b" * 64)))
            journal.close()


if __name__ == "__main__":
    unittest.main()
