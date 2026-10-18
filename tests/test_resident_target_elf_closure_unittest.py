"""REDÃ¢â€ â€™GREEN actual ELF64 DT_NEEDED scanner, no Buildroot build/guest."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools/vm/Probe-ResidentELFClosure.py"
spec = importlib.util.spec_from_file_location("probe_elf_closure", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def elf(needed=(), machine=62, klass=2, corrupt=False):
    # Real ELF64 header, PT_LOAD+PT_DYNAMIC and mapped dynamic string table.
    out = bytearray(1024)
    out[:16] = b"\x7fELF" + bytes([klass, 1, 1]) + bytes(9)
    struct.pack_into("<HHIQQQIHHHHHH", out, 16,
                     3, machine, 1, 0, 64, 0, 0, 64, 56, 2, 0, 0, 0)
    strs = b"\0"
    offsets = []
    for name in needed:
        offsets.append(len(strs))
        strs += name.encode("ascii") + b"\0"
    out[0x300:0x300+len(strs)] = strs
    dyn = [(5, 0x300), (10, len(strs))]
    dyn += [(1, offset) for offset in offsets]
    dyn += [(0, 0)]
    for i, (tag, value) in enumerate(dyn):
        struct.pack_into("<QQ", out, 0x200+i*16, tag, value)
    struct.pack_into("<IIQQQQQQ", out, 64,
                     1, 5, 0, 0, 0, len(out), len(out), 4096)
    struct.pack_into("<IIQQQQQQ", out, 120,
                     2, 4, 0x200, 0x200, 0, len(dyn)*16, len(dyn)*16, 8)
    if corrupt:
        struct.pack_into("<QQ", out, 0x200, 5, 0xffffffffffffff00)
    return bytes(out)


class ELFClosure(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="veraos-elf-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("/usr/bin/python3.12", elf(["libpython3.12.so.1.0"]))
        self.write("/usr/bin/cog", elf(["libcog.so.0"]))
        self.write("/usr/lib/python3.12/lib-dynload/_ssl.cpython-312.so", elf(["libssl.so.3"]))
        self.write("/usr/lib/python3.12/lib-dynload/_sqlite3.cpython-312.so", elf(["libsqlite3.so.0"]))
        self.write("/usr/lib/python3.12/site-packages/cryptography/hazmat/bindings/_rust.abi3.so",
                   elf(["libcrypto.so.3"]))
        for x in ["libpython3.12.so.1.0", "libcog.so.0", "libssl.so.3",
                  "libsqlite3.so.0", "libcrypto.so.3"]:
            self.write("/usr/lib/"+x, elf(["libc.so.6"]))
        self.write("/lib/libc.so.6", elf())

    def write(self, guest, bytes_):
        p=self.root/guest.lstrip("/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(bytes_)
        return p

    def test_actual_elf_binary_dependencies_are_recursively_closed(self):
        report=probe.audit(self.root)
        self.assertEqual(report["status"], "STATIC_ELF_CLOSURE_VERIFIED_GUEST_UNQUALIFIED")
        self.assertGreaterEqual(report["native_files_checked"], 11)
        self.assertEqual(report["unresolved"], [])
        self.assertTrue(any(x["needed"] == "libc.so.6" for x in report["edges"]))
        self.assertFalse(report["target_import_executed"])
        self.assertFalse(report["image_built"])

    def test_opt_in_postbuild_requires_actual_elf_closure(self):
        root = Path(__file__).resolve().parents[1]
        hook = (root / "buildroot/board/veraos/x86_64/post-build.sh").read_text()
        assert "Probe-ResidentELFClosure.py" in hook
        assert hook.index("Probe-ResidentTargetRootfs.py") < hook.index("Probe-ResidentELFClosure.py")
        assert hook.index("Probe-ResidentELFClosure.py") < hook.index("Explicitly no auto-start")
        assert 'if [ "${VERAOS_REQUIRE_RESIDENT_CORE:-0}" = "1" ]; then' in hook

    def test_missing_transitive_library_fails_closed(self):
        (self.root/"lib/libc.so.6").unlink()
        with self.assertRaisesRegex(probe.ELFClosureError, "libc.so.6"):
            probe.audit(self.root)

    def test_wrong_target_architecture_rejected(self):
        self.write("/usr/bin/cog", elf(["libcog.so.0"],machine=183))
        with self.assertRaisesRegex(probe.ELFClosureError, "x86_64"):
            probe.audit(self.root)

    def test_invalid_dynamic_string_table_rejected(self):
        self.write("/usr/bin/cog",elf(["libcog.so.0"],corrupt=True))
        with self.assertRaises(probe.ELFClosureError):
            probe.audit(self.root)

    def test_missing_crypto_extension_fails_closed(self):
        (self.root/"usr/lib/python3.12/site-packages/cryptography/hazmat/bindings/_rust.abi3.so").unlink()
        with self.assertRaisesRegex(probe.ELFClosureError, "cryptography"):
            probe.audit(self.root)

    def test_library_path_traversal_in_needed_rejected(self):
        self.write("/usr/bin/cog", elf(["../libc.so.6"]))
        with self.assertRaisesRegex(probe.ELFClosureError, "invalid library"):
            probe.audit(self.root)

    def test_unbounded_dynamic_segment_rejected(self):
        payload=bytearray(elf(["libcog.so.0"]))
        struct.pack_into("<IIQQQQQQ",payload,120,
                         2,4,0x200,0x200,0,0x100000000,0x100000000,8)
        self.write("/usr/bin/cog",bytes(payload))
        with self.assertRaises(probe.ELFClosureError):
            probe.audit(self.root)

    def test_unknown_native_search_path_holds(self):
        payload=bytearray(elf(["libcog.so.0"]))
        struct.pack_into("<QQ",payload,0x200+16*3,29,0x300)
        struct.pack_into("<QQ",payload,0x200+16*4,0,0)
        struct.pack_into("<IIQQQQQQ",payload,120,2,4,0x200,0x200,0,5*16,5*16,8)
        self.write("/usr/bin/cog",bytes(payload))
        with self.assertRaisesRegex(probe.ELFClosureError, "RPATH/RUNPATH"):
            probe.audit(self.root)


if __name__ == "__main__":
    unittest.main()
