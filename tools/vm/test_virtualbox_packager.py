"""Offline, small-fixture tests for VeraOS VirtualBox VDI packaging.

External EFI/FAT/VDI tools are mocked: tests do not prove a guest boots.
"""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import uuid
import zlib

SPEC=importlib.util.spec_from_file_location("pack_vbox",Path(__file__).with_name("Pack-VeraOSVirtualBox.py"))
p=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)

class GptTests(unittest.TestCase):
    def test_geometry(self):
        g=p.geometry(2*1024*1024,4*1024*1024)
        self.assertEqual(g["espstart"],2048)
        self.assertEqual(g["rootstart"]%2048,0)
        self.assertGreater(g["rootstart"],g["espend"])
        self.assertLess(g["rootend"],g["backuptable"])
    def test_bad_geometry(self):
        for n in (0,512,5000):
            with self.subTest(n=n),self.assertRaises(ValueError):
                p.geometry(n,4*1024*1024)
    def test_protective_mbr_and_gpt_crc(self):
        g=p.geometry(2*1024*1024,4*1024*1024)
        with tempfile.TemporaryFile() as f:
            f.truncate(g["totalbytes"])
            diskid,espid,rootid=uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
            p.write_gpt(f,g,diskid,espid,rootid)
            f.seek(0); mbr=f.read(512)
            self.assertEqual(mbr[510:512],b"\x55\xaa")
            self.assertEqual(mbr[450],0xee)
            for where,here,other in ((512,1,g["last"]),(g["last"]*512,g["last"],1)):
                f.seek(where); hdr=bytearray(f.read(512))
                self.assertEqual(hdr[:8],b"EFI PART")
                self.assertEqual(struct.unpack_from("<Q",hdr,24)[0],here)
                self.assertEqual(struct.unpack_from("<Q",hdr,32)[0],other)
                crc=struct.unpack_from("<I",hdr,16)[0]
                struct.pack_into("<I",hdr,16,0)
                self.assertEqual(zlib.crc32(hdr[:92]),crc)
            f.seek(1024); table=f.read(16384)
            self.assertEqual(uuid.UUID(bytes_le=table[:16]),p.ESP_TYPE)
            self.assertEqual(uuid.UUID(bytes_le=table[128:144]),p.LINUX_TYPE)
            self.assertEqual(uuid.UUID(bytes_le=table[16:32]),espid)
            self.assertEqual(uuid.UUID(bytes_le=table[144:160]),rootid)
            f.seek(g["backuptable"]*512)
            self.assertEqual(f.read(16384),table)

class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.repo=self.root/"repo";self.repo.mkdir()
        (self.repo/"buildroot").mkdir()
        (self.repo/"buildroot"/"external.desc").write_text("name: VERAOS\n")
        for cmd in (("init","-q"),("config","user.email","test@example.invalid"),
                    ("config","user.name","Test"),("add","."),("commit","-qm","base")):
            subprocess.run(["git","-C",str(self.repo),*cmd],check=True,capture_output=True)
        self.head=subprocess.check_output(["git","-C",str(self.repo),"rev-parse","HEAD"],text=True).strip()
        self.art=self.root/"art";self.art.mkdir()
        (self.art/"veraos-bzImage").write_bytes(b"small fake kernel")
        raw=bytearray(2*1024*1024);raw[1080:1082]=b"\x53\xef"
        (self.art/"veraos-rootfs.ext2").write_bytes(raw)
        self.receipt=dict(Schema="VERA_OS_BUILDROOT_BUILD_RESULT_V1",SourceHead=self.head,
                          SourceTreeClean=True,BuildrootVersion="2024.02.4",BuildrootCommit=p.PIN,
                          ProtectedEffectAuthority=False,BuildProfile="CORE_BOOT",
                          BrowserPackaged=False,Defconfig="veraos_x86_64_defconfig",
                          KernelSha256=p.sha256(self.art/"veraos-bzImage"),
                          RootfsSha256=p.sha256(self.art/"veraos-rootfs.ext2"))
        self.write_receipt()
        self.out=self.root/"output"/"veraos.vdi"
    def write_receipt(self):
        (self.art/"veraos-build-result.json").write_text(json.dumps(self.receipt))
    def test_exact_source_accepts_valid_fixture(self):
        self.assertEqual(p.validate(self.repo,self.art)[1],self.head)
    def test_digest_tampering_rejected(self):
        with (self.art/"veraos-rootfs.ext2").open("r+b") as f:
            f.seek(2000);f.write(b"corrupt")
        with self.assertRaisesRegex(ValueError,"modified"):
            p.validate(self.repo,self.art)
    def test_wrong_head_rejected(self):
        self.receipt["SourceHead"]="a"*40;self.write_receipt()
        with self.assertRaisesRegex(ValueError,"pin"):
            p.validate(self.repo,self.art)
    def test_nonboolean_browser_flag_rejected(self):
        self.receipt["BrowserPackaged"]="false";self.write_receipt()
        with self.assertRaisesRegex(ValueError,"profile"):
            p.validate(self.repo,self.art)
    def test_dirty_source_rejected(self):
        (self.repo/"untracked").write_text("change")
        with self.assertRaisesRegex(ValueError,"dirty"):
            p.validate(self.repo,self.art)
    def test_existing_output_cannot_be_clobbered(self):
        self.out.parent.mkdir();self.out.write_text("preserve")
        with self.assertRaises(FileExistsError):
            p.package(self.repo,self.art,self.out)
        self.assertEqual(self.out.read_text(),"preserve")
    def test_output_inside_repo_rejected(self):
        with self.assertRaisesRegex(ValueError,"outside"):
            p.package(self.repo,self.art,self.repo/"vdi.vdi")
    def test_output_inside_inputs_rejected(self):
        with self.assertRaisesRegex(ValueError,"outside"):
            p.package(self.repo,self.art,self.art/"vdi.vdi")
    def test_mocked_efi_gpt_vdi_pipeline(self):
        calls=[]
        def fake_run(*args):
            calls.append(args)
            if args[0]=="grub-mkstandalone":
                Path(args[args.index("-o")+1]).write_bytes(b"EFI boot")
            if args[0]=="qemu-img":
                raw=Path(args[-2]);g=p.geometry(2*1024*1024,p.ESP_BYTES)
                with raw.open("rb") as f:
                    f.seek(g["rootstart"]*512+1080)
                    self.assertEqual(f.read(2),b"\x53\xef")
                Path(args[-1]).write_bytes(b"FAKE VDI"*128)
        with mock.patch.object(p,"ESP_BYTES",4*1024*1024),\
             mock.patch.object(p.shutil,"which",return_value="/usr/bin/mock"),\
             mock.patch.object(p,"run",side_effect=fake_run):
            receipt=p.package(self.repo,self.art,self.out)
        self.assertFalse(receipt["boot_qualified"])
        self.assertEqual(receipt["vdi_sha256"],p.sha256(self.out))
        self.assertEqual(calls[0][0],"grub-mkstandalone")
        self.assertEqual(calls[-1][0],"qemu-img")
        self.assertTrue(self.out.with_suffix(".vdi.receipt.json").is_file())
        self.assertFalse(receipt["virtualbox_noapic"])


    def test_host_specific_noapic_option_embeds_grub_arg(self):
        seen=[]
        def fake_run(*args):
            if args[0]=="grub-mkstandalone":
                cfg=Path(args[-1].split("=",1)[1]).read_text()
                seen.append(cfg)
                Path(args[args.index("-o")+1]).write_bytes(b"EFI boot")
            elif args[0]=="qemu-img":
                Path(args[-1]).write_bytes(b"FAKE VDI"*128)
        with mock.patch.object(p,"ESP_BYTES",4*1024*1024),\
             mock.patch.object(p.shutil,"which",return_value="/usr/bin/mock"),\
             mock.patch.object(p,"run",side_effect=fake_run):
            receipt=p.package(self.repo,self.art,self.out,noapic=True)
        self.assertTrue(receipt["virtualbox_noapic"])
        self.assertEqual(len(seen),1)
        self.assertIn("init=/sbin/vera-init noapic",seen[0])

if __name__=="__main__":
    unittest.main()
