"""Offline VeraOS portfolio interface must never promote cached source to execution."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("veraos_offline", ROOT / "src/veraos/offline_portfolio.py")
offline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(offline)


class LocalOfflinePortfolioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/"bundles").mkdir()
        (self.root/"receipts").mkdir()
        self.rows = []
        for i in range(90):
            name = f"project-{i:02d}"
            head = f"{i+1:040x}"
            repo = "thebrazenbeard/" + name
            bundle_name = f"thebrazenbeard--{name}-{head[:12]}.bundle"
            body = b"GIT-BUNDLE-FIXTURE" + name.encode("ascii")
            (self.root/"bundles"/bundle_name).write_bytes(body)
            rec = {
                "schema": "VERA_OS_GIT_BUNDLE_RECEIPT_V1",
                "repo": repo, "default_branch": "main",
                "head": head, "bundle": bundle_name,
                "sha256": hashlib.sha256(body).hexdigest(),
                "bytes": len(body), "private": i < 21,
                "archived": i >= 85, "runtime_qualified": False,
                "role": "PORTAL_MANAGED_PROJECT",
                "activation": "ON_DEMAND",
            }
            (self.root/"receipts"/f"thebrazenbeard--{name}.json").write_text(json.dumps(rec))
            self.rows.append(rec)
        summary = {
            "schema": "VERA_OS_OFFLINE_GIT_PORTFOLIO_SNAPSHOT_V1",
            "status": "ALL_REPOSITORIES_BYTES_VERIFIED_SOURCE_ONLY",
            "repo_total": 90, "repo_verified": 90, "repo_missing": [],
            "private_verified": 21, "archived_verified": 5,
        }
        (self.root/"portfolio-snapshot-summary.json").write_text(json.dumps(summary))

    def test_no_false_executable_claim(self):
        result = offline.inspect_offline_portfolio(self.root, verify_bytes=True)
        self.assertEqual(result["total"], 90)
        self.assertEqual(result["private"], 21)
        self.assertTrue(result["all_archive_bytes_verified"])
        self.assertFalse(result["fully_offline_application_operation_qualified"])
        self.assertFalse(result["runtime_effect_authority"])
        self.assertTrue(all(row["execution"] == "NOT_QUALIFIED" for row in result["repos"]))

    def test_look_up_checks_selected_bundle_bytes(self):
        p = offline.lookup_repo(self.root, "thebrazenbeard/project-12")
        self.assertEqual(p["repository"], "thebrazenbeard/project-12")
        self.assertTrue(Path(p["bundle_path"]).is_file())
        with Path(p["bundle_path"]).open("ab") as writer:
            writer.write(b"ALTERED")
        with self.assertRaisesRegex(offline.OfflinePortfolioError, "hash differs"):
            offline.lookup_repo(self.root, "thebrazenbeard/project-12")

    def test_no_network_fallback_for_absent_repo(self):
        with self.assertRaisesRegex(offline.OfflinePortfolioError, "not in"):
            offline.lookup_repo(self.root, "someoneelse/nope")

    def test_missing_bundle_fails_closed(self):
        (self.root/"bundles"/self.rows[2]["bundle"]).unlink()
        with self.assertRaisesRegex(offline.OfflinePortfolioError, "Missing or changed"):
            offline.inspect_offline_portfolio(self.root)

    def test_wrong_summary_is_not_accepted(self):
        f=self.root/"portfolio-snapshot-summary.json"
        content=json.loads(f.read_text())
        content["repo_verified"]=89
        f.write_text(json.dumps(content))
        with self.assertRaisesRegex(offline.OfflinePortfolioError, "incomplete"):
            offline.inspect_offline_portfolio(self.root)

    def test_receipt_fake_authority_is_rejected(self):
        f=self.root/"receipts"/"thebrazenbeard--project-13.json"
        content=json.loads(f.read_text())
        content["runtime_qualified"]=True
        f.write_text(json.dumps(content))
        with self.assertRaisesRegex(offline.OfflinePortfolioError, "unqualified"):
            offline.inspect_offline_portfolio(self.root)

    def test_duplicate_or_unexpected_bundle_rejected(self):
        (self.root/"bundles"/"extra.bundle").write_text("extra")
        with self.assertRaisesRegex(offline.OfflinePortfolioError, "Bundle set differs"):
            offline.inspect_offline_portfolio(self.root)

    def test_private_flag_is_not_string(self):
        f=self.root/"receipts"/"thebrazenbeard--project-00.json"
        content=json.loads(f.read_text())
        content["private"]="true"
        f.write_text(json.dumps(content))
        with self.assertRaisesRegex(offline.OfflinePortfolioError, "unqualified"):
            offline.inspect_offline_portfolio(self.root)


if __name__ == "__main__":
    unittest.main()
