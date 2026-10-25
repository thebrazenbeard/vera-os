"""Source-only debugfs -p ext2 listing protocol; no real image/build/guest."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "exact_ext2_reader", ROOT / "tools/vm/Audit-VeraOSImage.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

BASE = "/opt/veraos/components"


def ls(*items):
    # debugfs(8) -p documented /inode/mode/uid/gid/name/size/ format.
    return b"\n".join(
        f"/{i + 20}/{mode}/0/0/{name}/0/".encode("ascii")
        for i, (mode, name) in enumerate(items)
    ) + b"\n"


class Ext2EnumerationTests(unittest.TestCase):
    def setUp(self):
        self.lists = {
            BASE: ls(("040755", "."), ("040755", ".."),
                     ("040755", "vera_mono"), ("040755", "portal")),
            BASE + "/vera_mono": ls(("040755", "packages")),
            BASE + "/vera_mono/packages": ls(("100644", "core.py")),
            BASE + "/portal": ls(("100644", "entry.py")),
        }
        reader = audit.ExtRootfs.__new__(audit.ExtRootfs)
        def debug(cmd):
            self.assertTrue(cmd.startswith("ls -p "))
            return self.lists.get(cmd.removeprefix("ls -p "), b""), b""
        reader._debugfs = debug
        self.reader = reader

    def test_bounded_recursive_component_closure(self):
        self.assertEqual(self.reader.component_files(), {
            "components/vera_mono/packages/core.py",
            "components/portal/entry.py",
        })

    def test_unexpected_image_import_is_not_ignored(self):
        self.lists[BASE + "/portal"] = ls(
            ("100644", "entry.py"), ("100644", "old_shadow.py"))
        self.assertIn("components/portal/old_shadow.py",
                      self.reader.component_files())

    def test_absent_or_unparseable_listing_fails_closed(self):
        for bad in (b"", b"debugfs: missing\n",
                    b"/21/100644/0/0/bad file.py/0/\n",
                    b"/21/100644/0/0/a.py/0/\n/22/100644/0/0/a.py/0/\n",
                    b"/21/120777/0/0/shortcut.py/0/\n",
                    b"/21/100644/0/0/../../../escape.py/0/\n"):
            with self.subTest(listing=bad):
                self.lists[BASE + "/portal"] = bad
                with self.assertRaises(audit.AuditError):
                    self.reader.component_files()

    def test_ext2_symlinks_and_special_inodes_fail_closed(self):
        for mode in ("120777", "020666", "010666"):
            with self.subTest(mode=mode):
                self.lists[BASE + "/portal"] = ls((mode, "special"))
                with self.assertRaisesRegex(audit.AuditError, "unsupported"):
                    self.reader.component_files()

    def test_listing_cannot_hide_unknown_child_directory(self):
        self.lists[BASE + "/portal"] = ls(("040755", "nested"))
        with self.assertRaisesRegex(audit.AuditError, "incomplete"):
            self.reader.component_files()

    def test_directory_listing_may_not_be_unbounded(self):
        self.lists[BASE + "/portal"] = b"x" * (1024 * 1024 + 1)
        with self.assertRaisesRegex(audit.AuditError, "incomplete"):
            self.reader.component_files()


if __name__ == "__main__":
    unittest.main()
