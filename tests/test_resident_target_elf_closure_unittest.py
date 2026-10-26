"""REDÃ¢â€ â€™GREEN actual ELF64 DT_NEEDED scanner, no Buildroot build/guest."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import os
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


def elf_with_interp(needed=(), interpreter=b"/lib64/ld-linux-x86-64.so.2\0",
                    invalid_bounds=False, extra_interp=False):
    payload = bytearray(elf(needed))
    struct.pack_into("<H", payload, 56, 4 if extra_interp else 3)
    size = len(interpreter)
    payload[0x380:0x380+size] = interpreter
    struct.pack_into("<IIQQQQQQ", payload, 64+2*56, 3, 4, 0x380, 0x380, 0,
                     1025 if invalid_bounds else size,
                     1025 if invalid_bounds else size, 1)
    if extra_interp:
        struct.pack_into("<IIQQQQQQ", payload, 64+3*56, 3, 4,
                         0x380, 0x380, 0, size, size, 1)
    return bytes(payload)


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

    def test_executable_pt_interp_missing_loader_is_not_closed(self):
        self.write("/usr/bin/python3.12",elf_with_interp(["libpython3.12.so.1.0"]))
        with self.assertRaisesRegex(probe.ELFClosureError, "interpreter|loader"):
            probe.audit(self.root)

    def test_present_interpreter_recorded_and_transitively_audited(self):
        self.write("/usr/bin/cog",elf_with_interp(["libcog.so.0"]))
        self.write("/lib64/ld-linux-x86-64.so.2",elf(["libc.so.6"]))
        report=probe.audit(self.root)
        self.assertTrue(any(x["interpreter"]=="/lib64/ld-linux-x86-64.so.2"
                            and x["importer"]=="/usr/bin/cog"
                            for x in report["interpreters"]))
        self.assertIn("/lib64/ld-linux-x86-64.so.2",report["source_files_sha256"])

    def test_relative_and_traversing_interpreter_path_rejected(self):
        for bad in [b"ld-linux-x86-64.so.2\0",b"/../../etc/shadow\0",
                    b"/lib64/ld-linux.so\0junk"]:
            with self.subTest(path=bad):
                self.write("/usr/bin/cog",elf_with_interp(["libcog.so.0"],bad))
                with self.assertRaises(probe.ELFClosureError):
                    probe.audit(self.root)

    def test_interpreter_program_header_outside_file_rejected(self):
        self.write("/usr/bin/cog",elf_with_interp(["libcog.so.0"],invalid_bounds=True))
        with self.assertRaises(probe.ELFClosureError):
            probe.audit(self.root)

    def test_multiple_interpreter_program_headers_rejected(self):
        self.write("/usr/bin/cog",elf_with_interp(["libcog.so.0"],extra_interp=True))
        with self.assertRaises(probe.ELFClosureError):
            probe.audit(self.root)

    def test_interpreter_file_exists_but_is_not_elf_rejected(self):
        self.write("/usr/bin/cog",elf_with_interp(["libcog.so.0"]))
        self.write("/lib64/ld-linux-x86-64.so.2",b"not a native loader")
        with self.assertRaises(probe.ELFClosureError):
            probe.audit(self.root)

    def test_interpreter_file_is_wrong_target_architecture_rejected(self):
        self.write("/usr/bin/cog",elf_with_interp(["libcog.so.0"]))
        self.write("/lib64/ld-linux-x86-64.so.2",elf(machine=183))
        with self.assertRaisesRegex(probe.ELFClosureError,"x86_64"):
            probe.audit(self.root)

    def test_actual_vn2_host_elf_pt_interp_matches_readelf_source_only(self):
        import re, subprocess
        binary=Path("/usr/bin/python3.12")
        if not binary.is_file():
            self.skipTest("host Python not present")
        result=subprocess.run(["readelf","-l",str(binary)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0)
        m=re.search(r"Requesting program interpreter: ([^]]+)",result.stdout)
        self.assertIsNotNone(m)
        # This is a host ELF parser cross-check, not a VeraOS target acceptance.
        _needs,_sha,interp=probe._read_elf(binary)
        self.assertEqual(interp,m.group(1))

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

    def test_empty_dt_runpath_with_bounded_string_table_is_not_extra_search(self):
        # Buildroot 2025.02.18 emits DT_RUNPATH="" in target shared libs.
        # An empty runpath does not introduce an additional search directory.
        payload = bytearray(elf(["libcog.so.0"]))
        struct.pack_into("<QQ", payload, 0x200 + 3 * 16, 29, 0)
        struct.pack_into("<QQ", payload, 0x200 + 4 * 16, 0, 0)
        struct.pack_into("<IIQQQQQQ", payload, 120,
                         2, 4, 0x200, 0x200, 0, 5 * 16, 5 * 16, 8)
        self.write("/usr/bin/cog", bytes(payload))
        self.assertEqual(probe.audit(self.root)["unresolved"], [])

    def test_nonempty_dt_runpath_remains_a_hold(self):
        payload = bytearray(elf(["libcog.so.0"]))
        struct.pack_into("<QQ", payload, 0x200 + 3 * 16, 29, 1)
        struct.pack_into("<QQ", payload, 0x200 + 4 * 16, 0, 0)
        struct.pack_into("<IIQQQQQQ", payload, 120,
                         2, 4, 0x200, 0x200, 0, 5 * 16, 5 * 16, 8)
        self.write("/usr/bin/cog", bytes(payload))
        with self.assertRaisesRegex(probe.ELFClosureError, "RPATH/RUNPATH"):
            probe.audit(self.root)

    def test_duplicate_empty_runpath_tags_are_not_accepted(self):
        payload = bytearray(elf(["libcog.so.0"]))
        struct.pack_into("<QQ", payload, 0x200 + 3 * 16, 29, 0)
        struct.pack_into("<QQ", payload, 0x200 + 4 * 16, 29, 0)
        struct.pack_into("<QQ", payload, 0x200 + 5 * 16, 0, 0)
        struct.pack_into("<IIQQQQQQ", payload, 120,
                         2, 4, 0x200, 0x200, 0, 6 * 16, 6 * 16, 8)
        self.write("/usr/bin/cog", bytes(payload))
        with self.assertRaisesRegex(probe.ELFClosureError, "RPATH/RUNPATH"):
            probe.audit(self.root)

    def test_unknown_native_search_path_holds(self):
        payload=bytearray(elf(["libcog.so.0"]))
        struct.pack_into("<QQ",payload,0x200+16*3,29,0x300)
        struct.pack_into("<QQ",payload,0x200+16*4,0,0)
        struct.pack_into("<IIQQQQQQ",payload,120,2,4,0x200,0x200,0,5*16,5*16,8)
        self.write("/usr/bin/cog",bytes(payload))
        with self.assertRaisesRegex(probe.ELFClosureError, "RPATH/RUNPATH"):
            probe.audit(self.root)


    def test_guest_absolute_parent_link_is_resolved_inside_rootfs(self):
        lib = self.root / "usr/lib"
        lib.rename(self.root / "lib-real")
        lib.symlink_to("/lib-real", target_is_directory=True)
        resolved, name = probe._inside(self.root, "/usr/lib/libssl.so.3")
        self.assertEqual(resolved, self.root / "lib-real/libssl.so.3")
        self.assertEqual(name, "/lib-real/libssl.so.3")
        self.assertEqual(probe.audit(self.root)["unresolved"], [])

    def test_guest_relative_parent_link_is_resolved_inside_rootfs(self):
        lib = self.root / "usr/lib"
        lib.rename(self.root / "lib-real")
        lib.symlink_to("../lib-real", target_is_directory=True)
        resolved, _ = probe._inside(self.root, "/usr/lib/libssl.so.3")
        self.assertEqual(resolved, self.root / "lib-real/libssl.so.3")
        self.assertEqual(probe.audit(self.root)["unresolved"], [])

    def test_guest_absolute_final_link_preserves_guest_elf_closure(self):
        target = self.root / "usr/lib/libssl.so.3"
        target.rename(self.root / "libssl-real.so.3")
        target.symlink_to("/libssl-real.so.3")
        resolved, _ = probe._inside(self.root, "/usr/lib/libssl.so.3")
        self.assertEqual(resolved, self.root / "libssl-real.so.3")
        self.assertEqual(probe.audit(self.root)["unresolved"], [])

    def test_guest_root_never_accepts_absolute_host_directory_decoy(self):
        lib = self.root / "usr/lib"
        outside = self.root.parent / "host-native"
        lib.rename(outside)
        lib.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(probe.ELFClosureError):
            probe.audit(self.root)

    def test_elf_parent_symlink_cycle_fails_closed(self):
        lib = self.root / "usr/lib"
        lib.rename(self.root / "lib-real")
        lib.symlink_to("/usr/lib", target_is_directory=True)
        with self.assertRaisesRegex(probe.ELFClosureError, "too long"):
            probe.audit(self.root)


    @unittest.skipUnless(os.name == "posix", "Linux post-build descriptor check; Windows source fixture unqualified")
    def test_guest_mutation_after_validation_must_not_consume_host_elf(self):
        from unittest import mock
        cog = self.root / "usr/bin/cog"
        host_decoy = self.root.parent / "host-decoy-elf"
        host_decoy.write_bytes(elf(["libcog.so.0"]))
        original_inside = probe._inside
        swapped = [False]
        def interleave(root, guest, *, directory=False):
            resolved, normalized = original_inside(root, guest, directory=directory)
            if guest == "/usr/bin/cog" and not swapped[0]:
                swapped[0] = True
                resolved.unlink()
                resolved.symlink_to(host_decoy)
            return resolved, normalized
        with mock.patch.object(probe, "_inside", side_effect=interleave):
            with self.assertRaises(probe.ELFClosureError):
                probe.audit(self.root)
        self.assertTrue(swapped[0])


    @unittest.skipUnless(os.name == "posix", "Linux post-build descriptor check; Windows source fixture unqualified")
    def test_parent_directory_swapped_after_validation_must_not_hash_host_elf(self):
        from unittest import mock
        guest_dir = self.root / "usr/bin"
        outside = self.root.parent / "host-elf-bin"
        outside.mkdir()
        (outside / "cog").write_bytes(elf(["libcog.so.0"]))
        original_inside = probe._inside
        swapped = [False]
        def interleave(root, guest, *, directory=False):
            resolved, normalized = original_inside(root, guest, directory=directory)
            if guest == "/usr/bin/cog" and not swapped[0]:
                swapped[0] = True
                guest_dir.rename(self.root / "old-usr-bin")
                guest_dir.symlink_to(outside, target_is_directory=True)
            return resolved, normalized
        with mock.patch.object(probe, "_inside", side_effect=interleave):
            with self.assertRaises(probe.ELFClosureError):
                probe.audit(self.root)
        self.assertTrue(swapped[0])


    @unittest.skipUnless(os.name == "posix", "Linux descriptor check; Windows source fixture unqualified")
    def test_in_place_same_size_guest_elf_write_during_read_fails_closed(self):
        from unittest import mock
        cog = self.root / "usr/bin/cog"
        baseline = cog.read_bytes()
        self.assertEqual(len(baseline), 1024)
        native_fdopen = probe.os.fdopen
        changed = [False]
        def modify_before_read(fd, *args, **kwargs):
            # Run after descriptor-root containment validation but before read.
            if os.readlink("/proc/self/fd/" + str(fd)) == str(cog) and not changed[0]:
                changed[0] = True
                with cog.open("r+b") as output:
                    output.seek(len(baseline)-1)
                    output.write(b"!")
            return native_fdopen(fd, *args, **kwargs)
        with mock.patch.object(probe.os, "fdopen", side_effect=modify_before_read):
            with self.assertRaisesRegex(probe.ELFClosureError, "changed during"):
                probe.audit(self.root)
        self.assertTrue(changed[0])
        self.assertEqual(cog.stat().st_size, len(baseline))


if __name__ == "__main__":
    unittest.main()
