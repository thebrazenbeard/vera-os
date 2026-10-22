"""Audit actual debugfs -p listing shape, preserving fail-closed member validation."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("veraos_image_ext2_parser", ROOT/"tools/vm/Audit-VeraOSImage.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

class Ext2DirectoryListingContract(unittest.TestCase):
    def fake(self, entries):
        reader = object.__new__(audit.ExtRootfs)
        with patch.object(reader, "_debugfs", side_effect=lambda command:(entries[command],b"debugfs 1.47.0\n")):
            return reader.component_files()

    def test_debugfs_real_directory_has_empty_size_and_blank_trailer(self):
        # Recorded actual debugfs 1.47.0 ls -p output on a disposable ext2 image.
        chunks = {
            "ls -p /opt/veraos/components":
                b"/18/040775/1000/1000/.//\n/17/040775/1000/1000/..//\n"
                b"/19/040775/1000/1000/vera_mono//\n\n",
            "ls -p /opt/veraos/components/vera_mono":
                b"/19/040775/1000/1000/.//\n/18/040775/1000/1000/..//\n"
                b"/20/100664/1000/1000/module.py/12/\n\n"
        }
        self.assertEqual(self.fake(chunks), {"components/vera_mono/module.py"})

    def test_malformed_directory_size_denied(self):
        chunks = {
            "ls -p /opt/veraos/components":b"/19/040775/1000/1000/vera_mono/9/\n",
        }
        with self.assertRaisesRegex(audit.AuditError,"malformed"):
            self.fake(chunks)

    def test_malformed_regular_size_denied(self):
        chunks = {
            "ls -p /opt/veraos/components":b"/20/100664/1000/1000/file.py//\n",
        }
        with self.assertRaisesRegex(audit.AuditError,"malformed"):
            self.fake(chunks)

    def test_symlink_inode_still_denied(self):
        chunks = {
            "ls -p /opt/veraos/components":b"/20/120777/1000/1000/link.py/13/\n",
        }
        with self.assertRaisesRegex(audit.AuditError,"unsupported"):
            self.fake(chunks)

    @unittest.skipUnless(os.name == "posix" and shutil.which("mke2fs") and shutil.which("debugfs"),
                         "requires Linux ext2 mke2fs and debugfs")
    def test_actual_ext2_debugfs_file_and_inventory(self):
        with tempfile.TemporaryDirectory(prefix="os39-ext2-inventory-") as td:
            root=Path(td)
            f=root/"fs/opt/veraos/components/vera_mono/sample.py"
            f.parent.mkdir(parents=True)
            contents=b"# real ext2 resident fixture\n"
            f.write_bytes(contents)
            image=root/"sample.ext2"
            subprocess.run(["mke2fs","-q","-F","-t","ext2","-d",str(root/"fs"),str(image),"8M"],
                           capture_output=True,check=True)
            reader=audit.ExtRootfs(image)
            self.assertEqual(reader.read("/opt/veraos/components/vera_mono/sample.py"),contents)
            self.assertEqual(reader.component_files(),{"components/vera_mono/sample.py"})

if __name__=="__main__":
    unittest.main()

