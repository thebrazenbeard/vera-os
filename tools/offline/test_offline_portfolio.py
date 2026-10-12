"""Offline portfolio snapshot checks: real local Git bundle, no network, no installation."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("offline_freeze", HERE / "Freeze-VeraPortfolio.py")
f = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f)


def git(*args):
    return subprocess.check_output(["git", *map(str,args)], stderr=subprocess.STDOUT, text=True).strip()


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.home = Path(self.t.name)
        self.bare = self.home/"remote.git"
        git("init", "-q", "--bare", self.bare)
        self.work = self.home/"work"
        git("clone", "-q", self.bare, self.work)
        git("-C",self.work,"config","user.name","Test")
        git("-C",self.work,"config","user.email","test@example.invalid")
        git("-C",self.work,"checkout","-qb","main")
        (self.work/"README.md").write_text("# source only\n")
        git("-C",self.work,"add",".")
        git("-C",self.work,"commit","-qm","first")
        git("-C",self.work,"push","-q","origin","main")
        git("--git-dir="+str(self.bare),"symbolic-ref","HEAD","refs/heads/main")
        self.row={"repo":"thebrazenbeard/offline-test","default_branch":"main",
                  "private":True,"archived":False,"role":"PORTAL_MANAGED_PROJECT",
                  "activation":"ON_DEMAND","previous_plan_head":None}
        self.out=self.home/"out"
        (self.out/"bundles").mkdir(parents=True)
        (self.out/"receipts").mkdir()
        self.real=f._command

    def local_clone(self,*args,**kw):
        if args[0:2]==("git","clone"):
            args=list(args)
            args[-2]=str(self.bare)
            return self.real(*args,**kw)
        return self.real(*args,**kw)

    def capture(self):
        with mock.patch.object(f,"_command",side_effect=self.local_clone):
            return f.capture_one(self.out,self.row)

    def test_capture_verify_and_offline_restore(self):
        result=self.capture()
        self.assertEqual(result["schema"],"VERA_OS_GIT_BUNDLE_RECEIPT_V1")
        self.assertTrue(result["private"])
        self.assertFalse(result["runtime_qualified"])
        restored=self.home/"restored"
        git("clone","-q",self.out/"bundles"/result["bundle"],restored)
        self.assertEqual(git("-C",restored,"rev-parse","HEAD"),result["head"])
        self.assertEqual((restored/"README.md").read_text(),"# source only\n")

    def test_no_overwrite_existing_bundle(self):
        first=self.capture()
        second=self.capture()
        self.assertEqual(first["sha256"],second["sha256"])
        self.assertEqual(len(list((self.out/"bundles").glob("*.bundle"))),1)

    def test_modified_archive_is_rejected(self):
        result=self.capture()
        with (self.out/"bundles"/result["bundle"]).open("ab") as out:
            out.write(b"tamper")
        with self.assertRaisesRegex(f.MirrorError,"mismatch"):
            f._verify_one(self.out,self.row)

    def test_mismatched_repository_identity_is_rejected(self):
        self.capture()
        other=dict(self.row,private=False)
        with self.assertRaisesRegex(f.MirrorError,"provenance"):
            f._verify_one(self.out,other)

    def test_missing_receipt_not_misrepresented_as_complete(self):
        self.assertFalse(list((self.out/"receipts").glob("*.json")))

    def test_census_from_source_covers_all_90(self):
        index=f.census(f.DEFAULT_INVENTORY)
        self.assertEqual(index["repo_count"],90)
        self.assertEqual(index["private_count"],21)
        self.assertEqual(index["archived_count"],5)
        self.assertIn("thebrazenbeard/RSLinux",{x["repo"] for x in index["repositories"]})
        self.assertNotIn("thebrazenbeard/RSLinux5000000",{x["repo"] for x in index["repositories"]})

    def test_directory_traversal_inventory_rejected(self):
        d={"schema":"VERA_OS_OWNED_OFFLINE_PORTFOLIO_CENSUS_V1",
           "repo_count":90,"owner":"thebrazenbeard","private_count":0,
           "archived_count":0,"repositories":[
               {"repo":"thebrazenbeard/repo-"+str(i),"default_branch":"main",
                "private":False,"archived":False} for i in range(90)]}
        d["repositories"][0]["repo"]="thebrazenbeard/../outside"
        path=self.home/"bad.json"
        path.write_text(json.dumps(d))
        with self.assertRaisesRegex(f.MirrorError,"Unsafe"):
            f.census(path)


if __name__ == "__main__":
    unittest.main()
