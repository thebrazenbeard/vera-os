"""Adversarial offline source-journal tests; NO Windows grant or issuer."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from veraos.windows_identity_ping import PingDenied, PingRequest, REQUEST_SCHEMA
from veraos.windows_ping_replay_journal import (
    SourcePingReplayHeld, _digest, record_untrusted_ping,
)


def ping(request_id="a" * 32, nonce="b" * 32, **extra):
    body = {"schema": REQUEST_SCHEMA, "action": "PING",
            "request_id": request_id, "nonce": nonce}
    body.update(extra)
    return json.dumps(body).encode("utf-8")


class SourceReplayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="veraos-untrusted-ping-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.db = self.tmp / "observation.sqlite3"

    def call(self, data=None):
        return record_untrusted_ping(self.db, ping() if data is None else data)

    def rows(self):
        with sqlite3.connect(self.db) as db:
            return db.execute("SELECT count(*) FROM source_ping_seen").fetchone()[0]

    def test_first_sighting_and_exact_retry_both_deny(self):
        first = self.call()
        second = self.call()
        self.assertFalse(first.replayed)
        self.assertTrue(second.replayed)
        self.assertEqual((first.admission, second.admission), ("DENIED", "DENIED"))
        self.assertEqual(first.authority, "UNTRUSTED_SOURCE_ONLY")
        self.assertEqual(self.rows(), 1)

    def test_nonce_reuse_with_different_request_id_is_replay(self):
        self.call()
        self.assertTrue(self.call(ping(request_id="c" * 32)).replayed)
        self.assertEqual(self.rows(), 1)

    def test_id_reuse_with_different_nonce_is_replay(self):
        self.call()
        self.assertTrue(self.call(ping(nonce="d" * 32)).replayed)
        self.assertEqual(self.rows(), 1)

    def test_distinct_ping_survives_reopen_and_remains_denied(self):
        self.call()
        fresh = self.call(ping("c" * 32, "d" * 32))
        self.assertFalse(fresh.replayed)
        self.assertEqual(fresh.admission, "DENIED")
        self.assertEqual(self.rows(), 2)
        self.assertTrue(self.call(ping("c" * 32, "d" * 32)).replayed)

    def test_concurrent_double_submit_is_one_row_only(self):
        # Multiple connections race for the same nonce; SQLite IMMEDIATE lock
        # gives one observation followed by one replay, not two admissions.
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: self.call(), (0, 1)))
        self.assertEqual(sorted(x.replayed for x in outcomes), [False, True])
        self.assertEqual(self.rows(), 1)
        self.assertTrue(all(x.admission == "DENIED" for x in outcomes))

    def test_json_claim_and_malformed_packet_do_not_touch_ledger(self):
        for invalid in [ping(role="admin"), ping(effect="shell"), b"{",
                        ping(nonce="bad"), ping() + b" " * 513]:
            with self.subTest(data=invalid[:25]), self.assertRaises(PingDenied):
                self.call(invalid)
        self.assertFalse(self.db.exists())

    def test_partial_row_delete_is_held_and_does_not_reissue(self):
        self.call()
        self.call(ping("c" * 32, "d" * 32))
        with sqlite3.connect(self.db) as db:
            key = db.execute("SELECT request_id_digest FROM source_ping_seen "
                             "LIMIT 1").fetchone()[0]
            db.execute("DELETE FROM source_ping_seen WHERE request_id_digest=?", (key,))
        with self.assertRaisesRegex(SourcePingReplayHeld, "marker mismatch"):
            self.call(ping("e" * 32, "f" * 32))
        self.assertEqual(self.rows(), 1)

    def test_modified_digest_marker_is_held(self):
        self.call()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE source_ping_meta SET value='0' WHERE name='digest'")
        with self.assertRaisesRegex(SourcePingReplayHeld, "marker mismatch"):
            self.call(ping("c" * 32, "d" * 32))
        self.assertEqual(self.rows(), 1)

    def test_attached_or_extra_schema_is_held(self):
        self.call()
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE VIEW injected_authority AS SELECT 1")
        with self.assertRaisesRegex(SourcePingReplayHeld, "schema differs"):
            self.call(ping("c" * 32, "d" * 32))

    def test_whole_database_rollback_not_detectable_by_same_db_digest(self):
        self.call()
        older = self.tmp / "older.sqlite3"
        with sqlite3.connect(self.db) as src, sqlite3.connect(older) as dest:
            src.backup(dest)
        self.call(ping("c" * 32, "d" * 32))
        with sqlite3.connect(older) as src, sqlite3.connect(self.db) as dest:
            src.backup(dest)
        # Demonstrated limitation, not a passed anti-rollback test.
        replay_after_rollback = self.call(ping("c" * 32, "d" * 32))
        self.assertFalse(replay_after_rollback.replayed)
        self.assertEqual(replay_after_rollback.admission, "DENIED")

    def test_same_uid_writer_can_recompute_marker_after_erasing_nonce(self):
        self.call()
        self.call(ping("c" * 32, "d" * 32))
        second_digest = PingRequest.from_wire(ping("c" * 32, "d" * 32)).sha256()
        with sqlite3.connect(self.db) as db:
            request_id_digest = db.execute(
                "SELECT request_id_digest FROM source_ping_seen "
                "WHERE request_sha256=?",
                (second_digest,)
            ).fetchone()[0]
            db.execute("DELETE FROM source_ping_seen WHERE request_id_digest=?",
                       (request_id_digest,))
            db.execute("UPDATE source_ping_meta SET value=? WHERE name='digest'",
                       (_digest(db),))
        # Falsifier: digest equality within the same DB authenticates nothing.
        # This remains DENIED but cannot claim successful replay prevention.
        response = self.call(ping("c" * 32, "d" * 32))
        self.assertFalse(response.replayed)
        self.assertEqual(response.admission, "DENIED")

    def test_untrusted_path_symlink_is_rejected(self):
        target = self.tmp / "unrelated.db"
        target.write_text("keep", encoding="ascii")
        self.db.symlink_to(target)
        with self.assertRaisesRegex(SourcePingReplayHeld, "non-symlink"):
            self.call()
        self.assertEqual(target.read_text(encoding="ascii"), "keep")


if __name__ == "__main__":
    unittest.main()
