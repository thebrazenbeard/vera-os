"""Linux synthetic ext2 immutable audit-stream contract, not guest qualification."""
from pathlib import Path
import errno
import hashlib
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("veraos_sealed_candidate", ROOT/"tools/vm/Verify-VeraOSPinnedExt2.py")
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)

@unittest.skipUnless(os.name == "posix" and hasattr(os, "memfd_create") and
                     shutil.which("mke2fs") and shutil.which("debugfs"),
                     "Linux sealed memfd + ext2 tools required")
class SealedExt2Custody(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="os42-sealed-ext2-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)

    def make_image(self, name: str, body: bytes):
        stage = self.root/("stage-"+name)
        file = stage/"opt/veraos/components/vera_mono/probe.py"
        file.parent.mkdir(parents=True)
        file.write_bytes(body)
        image = self.root/(name+".ext2")
        subprocess.run(["mke2fs","-q","-F","-t","ext2","-d",str(stage),str(image),"8M"],
                       capture_output=True,check=True)
        return image

    def member(self, name: str):
        return subprocess.run(["debugfs","-R",
            "cat /opt/veraos/components/vera_mono/probe.py",name],
            capture_output=True,check=True).stdout

    def test_sealed_member_survives_same_uid_original_path_swap(self):
        a = self.make_image("A", b"member-from-A\n")
        b = self.make_image("B", b"member-from-B\n")
        digest = hashlib.sha256(a.read_bytes()).hexdigest()
        with self.assertRaisesRegex(candidate.ArtifactCustodyError, "alias"):
            with candidate.pinned_sealed_ext2(a,digest) as (sealed_path,receipt):
                self.assertEqual(self.member(str(sealed_path)), b"member-from-A\n")
                os.replace(b,a)
                self.assertEqual(self.member(str(sealed_path)), b"member-from-A\n")
                self.assertEqual(self.member(str(a)), b"member-from-B\n")
                self.assertEqual(receipt["image_sha256"],digest)

    def test_sealed_bytes_reject_same_uid_direct_write(self):
        a = self.make_image("A",b"sealed-probe\n")
        digest = hashlib.sha256(a.read_bytes()).hexdigest()
        with candidate.pinned_sealed_ext2(a,digest) as (sealed_path,receipt):
            descriptor=os.open(sealed_path,os.O_RDWR)
            try:
                with self.assertRaises(OSError) as held:
                    os.write(descriptor,b"tamper")
                self.assertEqual(held.exception.errno,errno.EPERM)
            finally:
                os.close(descriptor)
            self.assertTrue(receipt["seals_applied"])

    def test_large_artifact_explicitly_held_without_unbounded_memfd(self):
        artifact=self.root/"oversized.ext2"
        with artifact.open("wb") as stream:
            stream.truncate(129*1024*1024)
        with self.assertRaisesRegex(candidate.ArtifactCustodyError,"size limit"):
            with candidate.pinned_sealed_ext2(artifact,"0"*64):
                self.fail("oversized image admitted")

    def test_wrong_selected_digest_held(self):
        a=self.make_image("A",b"source-A\n")
        with self.assertRaisesRegex(candidate.ArtifactCustodyError,"digest mismatch"):
            with candidate.pinned_sealed_ext2(a,"0"*64):
                self.fail("wrong hash admitted")

if __name__=="__main__":
    unittest.main()
