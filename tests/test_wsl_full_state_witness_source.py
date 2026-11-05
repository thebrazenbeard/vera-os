"""Source-only full-state recovery witness and crash-ordering tests.

The witness records here are fabricated in-process. They do not authenticate
Windows custody, enforce a monotonic external generation, or admit tasks.
"""
from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import pwd
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veraos.wsl_ipc import _dispatch  # noqa: E402
from veraos.wsl_pilot import Pilot, PilotError, SCHEMA  # noqa: E402
from veraos import wsl_recovery_witness as witness  # noqa: E402
from veraos.wsl_recovery_witness import (  # noqa: E402
    FullStateTransition, full_pilot_state_digest,
    assert_full_state_transition_consistent,
)


@unittest.skipUnless(os.name == "posix", "POSIX fixture required")
class FullStateWitnessSourceTests(unittest.TestCase):
    def setUp(self):
        if os.geteuid() == 0:
            for name in ("veraos.wsl_pilot._uid", "veraos.wsl_ipc._uid"):
                identity = patch(name, return_value=0)
                identity.start()
                self.addCleanup(identity.stop)
        home = (Path(pwd.getpwuid(os.geteuid()).pw_dir)
                if "microsoft" in os.uname().release.lower() else None)
        self.temp = Path(tempfile.mkdtemp(prefix="veraos-full-witness-", dir=home))
        self.addCleanup(shutil.rmtree, self.temp)
        self.root = self.temp / "pilot"
        with Pilot.init(self.root):
            pass
        self.keyed("a" * 32)

    def keyed(self, request_id: str) -> None:
        with Pilot(self.root) as pilot:
            _dispatch(pilot, {"action": "submit", "worker": "inspect",
                              "filename": "fixture.txt", "request_id": request_id})

    def digest(self) -> str:
        with Pilot(self.root) as pilot:
            return full_pilot_state_digest(pilot.db)

    def check(self, claim: FullStateTransition | None) -> None:
        with Pilot(self.root) as pilot:
            assert_full_state_transition_consistent(pilot.db, claim)

    def claim(self, before: str, after: str, *, phase="COMMITTED", generation=2,
              owner_uid=None) -> FullStateTransition:
        return FullStateTransition(
            owner_uid=os.geteuid() if owner_uid is None else owner_uid,
            schema=SCHEMA, version="1", generation=generation, phase=phase,
            before_digest=before, after_digest=after,
        )

    def backup(self, filename: str) -> Path:
        dst = self.temp / filename
        with closing(sqlite3.connect(self.root / "pilot.sqlite3")) as source:
            with closing(sqlite3.connect(dst)) as target:
                source.backup(target)
        return dst

    def restore(self, source_path: Path) -> None:
        with closing(sqlite3.connect(source_path)) as source:
            with closing(sqlite3.connect(self.root / "pilot.sqlite3")) as target:
                source.backup(target)

    def test_committed_transition_matching_full_state_is_consistent_only(self):
        before = self.digest()
        self.keyed("b" * 32)
        after = self.digest()
        self.check(self.claim(before, after))

    def test_complete_sqlite_rollback_rejected_against_separately_retained_newer_claim(self):
        before = self.digest()
        old = self.backup("older.sqlite3")
        self.keyed("b" * 32)
        claim = self.claim(before, self.digest())
        self.restore(old)
        with self.assertRaisesRegex(PilotError, "full-state mismatch"):
            self.check(claim)

    def test_database_ahead_of_stale_committed_claim_is_held(self):
        first = self.digest()
        self.keyed("b" * 32)
        second = self.digest()
        self.check(self.claim(first, second))
        self.keyed("c" * 32)
        with self.assertRaisesRegex(PilotError, "full-state mismatch"):
            self.check(self.claim(first, second))

    def test_prepared_claim_holds_before_and_after_sqlite_commit(self):
        before = self.digest()
        old = self.backup("prior.sqlite3")
        self.keyed("b" * 32)
        after = self.digest()
        claim = self.claim(before, after, phase="PREPARED")
        with self.assertRaisesRegex(PilotError, "prepared; hold"):
            self.check(claim)
        self.restore(old)
        with self.assertRaisesRegex(PilotError, "prepared; hold"):
            self.check(claim)

    def test_unkeyed_task_and_denial_receipt_changes_full_state_digest(self):
        before = self.digest()
        with Pilot(self.root) as pilot:
            pilot.submit("digest", "fixture.txt")
            pilot.protected_effect("protected.merge")
        after = self.digest()
        self.assertNotEqual(before, after)
        self.check(self.claim(before, after))

    def test_unkeyed_only_state_rollback_now_detectable_with_external_newer_claim(self):
        before = self.digest()
        old = self.backup("prior.sqlite3")
        with Pilot(self.root) as pilot:
            pilot.submit("digest", "fixture.txt")
        claim = self.claim(before, self.digest())
        self.restore(old)
        with self.assertRaisesRegex(PilotError, "full-state mismatch"):
            self.check(claim)

    def test_same_uid_forged_matching_transition_is_not_host_authentication(self):
        before = self.digest()
        old = self.backup("old.sqlite3")
        self.keyed("b" * 32)
        self.restore(old)
        # Attack can mint a matching fabricated claim under the same UID.
        fake_before = "0" * 64
        self.check(self.claim(fake_before, self.digest()))
        self.assertEqual(before, self.digest())

    def test_missing_malformed_and_foreign_transition_hold(self):
        current = self.digest()
        for claim in (
            None,
            self.claim(current, current, phase="PENDING"),
            self.claim(current, current, generation=True),
            self.claim(current, current, owner_uid=os.geteuid() + 1),
            self.claim("not a digest", current),
            self.claim(current, current, generation=-1),
        ):
            with self.subTest(claim=claim), self.assertRaises(PilotError):
                self.check(claim)

    def test_unknown_state_table_is_held_instead_of_silently_omitted(self):
        with Pilot(self.root) as pilot:
            pilot.db.execute("CREATE TABLE untracked_state (value TEXT)")
            pilot.db.commit()
        with self.assertRaisesRegex(PilotError, "unsupported pilot state table"):
            self.digest()

    def test_concurrent_wal_writer_cannot_tear_a_multitable_snapshot(self):
        before = self.digest()
        injected = False
        source_rows = witness._source_rows

        def write_after_first_table(db, query):
            nonlocal injected
            result = source_rows(db, query)
            if not injected and "FROM sqlite_master" in query:
                injected = True
                # Real second SQLite connection commits during the first
                # reader's multitable scan. In WAL mode the first reader must
                # keep a stable snapshot, never hash half-new state.
                with closing(sqlite3.connect(self.root / "pilot.sqlite3")) as writer:
                    with writer:
                        writer.execute("INSERT INTO tasks VALUES (?,?,?,?,?)",
                                       ("f" * 32, "digest", "fixture.txt", "QUEUED",
                                        os.geteuid()))
                        writer.execute("INSERT INTO events(task_id,code,detail) "
                                       "VALUES (?,?,?)", ("f" * 32, "SUBMITTED", "digest"))
            return result

        with Pilot(self.root) as pilot:
            with patch.object(witness, "_source_rows", side_effect=write_after_first_table):
                observed = full_pilot_state_digest(pilot.db)
        self.assertTrue(injected)
        self.assertEqual(observed, before)
        self.assertNotEqual(self.digest(), before)


if __name__ == "__main__":
    unittest.main()
