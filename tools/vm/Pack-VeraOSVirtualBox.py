#!/usr/bin/env python3
"""Package a pinned VeraOS Buildroot image as an EFI-bootable VirtualBox VDI.

No host partition changes, VM registration, installation, or deployment.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import uuid
import zlib

SECTOR=512
ALIGN=2048
TABLE_SECTORS=32
ESP_BYTES=256*1024*1024
PIN="e0a2687421a4f93e65aa00a30bcb0b4817f7a195"
ESP_TYPE=uuid.UUID("c12a7328-f81f-11d2-ba4b-00a0c93ec93b")
LINUX_TYPE=uuid.UUID("0fc63daf-8483-4772-8e79-3d69d8477de4")

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def geometry(rootbytes, espbytes=ESP_BYTES):
    if rootbytes<2048 or rootbytes%SECTOR or espbytes<1024*1024 or espbytes%(1024*1024):
        raise ValueError("Invalid rootfs/ESP geometry")
    espstart=ALIGN
    espend=espstart+espbytes//SECTOR-1
    rootstart=((espend+ALIGN)//ALIGN)*ALIGN
    rootend=rootstart+rootbytes//SECTOR-1
    last=((rootend+TABLE_SECTORS+2+ALIGN-1)//ALIGN)*ALIGN-1
    return dict(espstart=espstart,espend=espend,rootstart=rootstart,rootend=rootend,
                last=last,backuptable=last-TABLE_SECTORS,totalbytes=(last+1)*SECTOR)

def entry(typ,partid,start,end,name):
    if start>end: raise ValueError("Empty GPT partition")
    return (typ.bytes_le+partid.bytes_le+struct.pack("<QQQ",start,end,0)+
            name.encode("utf-16le")[:72].ljust(72,b"\x00"))

def header(here,other,tableloc,g,diskid,tablecrc):
    h=bytearray(SECTOR)
    struct.pack_into("<8sIIIIQQQQ16sQIII",h,0,b"EFI PART",0x10000,92,0,0,
                     here,other,34,g["last"]-TABLE_SECTORS-1,
                     diskid.bytes_le,tableloc,128,128,tablecrc)
    struct.pack_into("<I",h,16,zlib.crc32(h[:92])&0xffffffff)
    return h

def write_gpt(disk,g,diskid,espid,rootid):
    table=(entry(ESP_TYPE,espid,g["espstart"],g["espend"],"VERAOS EFI")+
           entry(LINUX_TYPE,rootid,g["rootstart"],g["rootend"],"VERAOS ROOT"))
    table=table.ljust(128*128,b"\x00")
    crc=zlib.crc32(table)&0xffffffff
    mbr=bytearray(SECTOR)
    struct.pack_into("<B3sB3sII",mbr,446,0,b"\x00\x02\x00",0xee,
                     b"\xff\xff\xff",1,min(g["last"],0xffffffff))
    mbr[510:512]=b"\x55\xaa"
    disk.seek(0); disk.write(mbr)
    disk.write(header(1,g["last"],2,g,diskid,crc))
    disk.write(table)
    disk.seek(g["backuptable"]*SECTOR); disk.write(table)
    disk.seek(g["last"]*SECTOR)
    disk.write(header(g["last"],1,g["backuptable"],g,diskid,crc))

def validate(repo,artifacts):
    if not (repo/"buildroot"/"external.desc").is_file():
        raise ValueError("Not a VeraOS source checkout")
    head=subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD"],text=True).strip()
    if len(head)!=40 or any(c not in "0123456789abcdef" for c in head):
        raise ValueError("Invalid exact source commit")
    if subprocess.check_output(["git","-C",str(repo),"status","--porcelain=v1"]):
        raise ValueError("Source tree is dirty")
    receipt=json.loads((artifacts/"veraos-build-result.json").read_text())
    if (receipt.get("Schema")!="VERA_OS_BUILDROOT_BUILD_RESULT_V1" or
        receipt.get("SourceHead")!=head or receipt.get("SourceTreeClean") is not True or
        receipt.get("BuildrootVersion")!="2024.02.4" or
        receipt.get("BuildrootCommit")!=PIN or
        receipt.get("ProtectedEffectAuthority") is not False):
        raise ValueError("Build receipt does not match source and pin")
    profile=receipt.get("BuildProfile")
    if (profile not in ("CORE_BOOT","BROWSER") or
        type(receipt.get("BrowserPackaged")) is not bool or
        receipt["BrowserPackaged"] != (profile=="BROWSER")):
        raise ValueError("Inconsistent browser/profile receipt")
    expected="veraos_x86_64_browser_defconfig" if profile=="BROWSER" else "veraos_x86_64_defconfig"
    if receipt.get("Defconfig")!=expected:
        raise ValueError("Inconsistent defconfig")
    for name,key in (("veraos-bzImage","KernelSha256"),("veraos-rootfs.ext2","RootfsSha256")):
        path=artifacts/name
        if not path.is_file() or not path.stat().st_size or sha256(path)!=receipt.get(key):
            raise ValueError("Missing or modified artifact: "+name)
    with (artifacts/"veraos-rootfs.ext2").open("rb") as f:
        f.seek(1080)
        if f.read(2)!=b"\x53\xef":
            raise ValueError("Root filesystem is not an ext-family image")
    return receipt,head

def run(*args):
    subprocess.run(list(args),check=True)

def package(repo,artifacts,output,*,noapic=False):
    repo=repo.resolve(); artifacts=artifacts.resolve(); output=output.resolve()
    if (output==repo or repo in output.parents or
        output==artifacts or artifacts in output.parents):
        raise ValueError("Output must be outside source and input artifact directory")
    if output.suffix.lower()!=".vdi": raise ValueError("Output must end with .vdi")
    outreceipt=output.with_suffix(output.suffix+".receipt.json")
    if (output.exists() or output.is_symlink() or
        outreceipt.exists() or outreceipt.is_symlink()):
        raise FileExistsError("Refusing to overwrite output or receipt")
    receipt,head=validate(repo,artifacts)
    for tool in ("grub-mkstandalone","mkfs.fat","mmd","mcopy","qemu-img"):
        if shutil.which(tool) is None: raise RuntimeError("Missing tool: "+tool)
    g=geometry((artifacts/"veraos-rootfs.ext2").stat().st_size,ESP_BYTES)
    diskid,espid,rootid=uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="veraos-vbox-",dir=output.parent) as tmp:
        work=Path(tmp)
        cfg=work/"grub.cfg"
        cfg.write_text("set timeout=2\nset default=0\n"+
                       "search --no-floppy --label VERAESP --set=root\n"+
                       "menuentry \"VeraOS\" {\n"+
                       " linux /veraos-bzImage root=PARTUUID="+str(rootid)+
                       " rw console=tty0 console=ttyS0,115200 init=/sbin/vera-init"+(" noapic" if noapic else "")+"\n}\n")
        efi=work/"BOOTX64.EFI"
        run("grub-mkstandalone","-O","x86_64-efi","-o",str(efi),
            "--modules=part_gpt fat search search_label linux",
            "boot/grub/grub.cfg="+str(cfg))
        esp=work/"esp.fat"
        with esp.open("wb") as f: f.truncate(ESP_BYTES)
        run("mkfs.fat","-F","32","-n","VERAESP",str(esp))
        run("mmd","-i",str(esp),"::/EFI","::/EFI/BOOT")
        run("mcopy","-i",str(esp),str(efi),"::/EFI/BOOT/BOOTX64.EFI")
        run("mcopy","-i",str(esp),str(artifacts/"veraos-bzImage"),"::/veraos-bzImage")
        raw=work/"veraos.raw"
        with raw.open("w+b") as disk:
            disk.truncate(g["totalbytes"])
            write_gpt(disk,g,diskid,espid,rootid)
            for src,sector in ((esp,g["espstart"]),(artifacts/"veraos-rootfs.ext2",g["rootstart"])):
                disk.seek(sector*SECTOR)
                with src.open("rb") as data: shutil.copyfileobj(data,disk,1024*1024)
        vdi=work/"veraos.vdi"
        run("qemu-img","convert","-f","raw","-O","vdi",str(raw),str(vdi))
        if not vdi.is_file() or vdi.stat().st_size<512:
            raise RuntimeError("VDI conversion failed")
        digest=sha256(vdi); size=vdi.stat().st_size
        os.link(vdi,output)  # no-clobber creation, source+destination same filesystem
    result=dict(schema="VERA_OS_VIRTUALBOX_DISK_BUILD_V1",source_head=head,
                build_profile=receipt["BuildProfile"],
                build_receipt_sha256=sha256(artifacts/"veraos-build-result.json"),
                kernel_sha256=receipt["KernelSha256"],
                rootfs_sha256=receipt["RootfsSha256"],
                vdi_sha256=digest,vdi_bytes=size,disk_guid=str(diskid),
                esp_partuuid=str(espid),root_partuuid=str(rootid),
                disk_layout="GPT_ESP_FAT32_LINUX_ROOTFS",boot_mode="UEFI_X86_64",
                boot_qualified=False,virtualbox_noapic=noapic,protected_effect_authority=False)
    with outreceipt.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2); f.write("\n")
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo",type=Path)
    parser.add_argument("artifacts",type=Path)
    parser.add_argument("output_vdi",type=Path)
    parser.add_argument("--virtualbox-noapic",action="store_true",help="Work around VirtualBox IO-APIC timer failures on affected hosts")
    args=parser.parse_args()
    print(json.dumps(package(args.repo,args.artifacts,args.output_vdi,noapic=args.virtualbox_noapic),indent=2))
