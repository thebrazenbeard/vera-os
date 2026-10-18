#!/usr/bin/env python3
"""Check real target ELF64 x86_64 PT_DYNAMIC/DT_NEEDED closure, never execute target code.

Requires an actual assembled Buildroot rootfs tree; synthetic fixtures only
qualify this parser. Python imports, dynamic loader behavior, GUI/boot and
generated-image identity remain separately UNQUALIFIED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import struct
import sys

class ELFClosureError(ValueError):
    pass

_LIB = re.compile(r"[A-Za-z0-9_+.-]+\.so(?:\.[A-Za-z0-9_.+-]+)*\Z")
_SEARCH = ("/lib", "/usr/lib", "/lib64", "/usr/lib64",
           "/usr/lib/x86_64-linux-gnu")
_MAX_FILE = 512 * 1024 * 1024

def _inside(root, guest):
    if not guest.startswith("/") or "\0" in guest:
        raise ELFClosureError("invalid guest absolute ELF path")
    path = posixpath.normpath(guest)
    if any(s == ".." for s in guest.split("/")):
        raise ELFClosureError("guest ELF path traversal denied")
    for _ in range(20):
        file = root / path.lstrip("/")
        if not file.is_symlink():
            try:
                safe = file.resolve(strict=True)
            except (OSError, ValueError) as exc:
                raise ELFClosureError("missing guest ELF " + path) from exc
            if not safe.is_relative_to(root):
                raise ELFClosureError("guest ELF escapes rootfs " + path)
            return file, path
        target = os.readlink(file)
        path = posixpath.normpath(
            target if target.startswith("/") else
            posixpath.join(posixpath.dirname(path), target))
        if not path.startswith("/"):
            raise ELFClosureError("guest ELF symlink escapes rootfs")
    raise ELFClosureError("guest ELF symlink chain too long")

def _range(data, offset, length):
    if offset < 0 or length < 0 or offset + length > len(data):
        raise ELFClosureError("ELF segment outside bounded file")
    return data[offset:offset + length]

def _read_elf(path):
    size = path.stat().st_size
    if size < 64 or size > _MAX_FILE:
        raise ELFClosureError("ELF file empty or exceeds fixed bound")
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise ELFClosureError("ELF64 little-endian target required")
    (typ, machine, ver, _entry, phoff, _shoff, _flags,
     ehsize, phentsize, phnum, _shentsize, _shnum, _shidx) = struct.unpack_from(
        "<HHIQQQIHHHHHH", data, 16)
    if typ not in (2, 3) or machine != 62 or ver != 1:
        raise ELFClosureError("target must be x86_64 ELF executable/shared object")
    if ehsize != 64 or phentsize != 56 or not 1 <= phnum <= 128:
        raise ELFClosureError("ELF header/program table invalid")
    _range(data, phoff, phnum * phentsize)
    loads = []
    dynamic = None
    for i in range(phnum):
        (ptyp, _flags, off, virt, _phys, sz, memsz, _align) = struct.unpack_from(
            "<IIQQQQQQ", data, phoff + i * phentsize)
        if ptyp == 1:
            _range(data, off, sz)
            loads.append((virt, sz, off))
        if ptyp == 2:
            if dynamic is not None:
                raise ELFClosureError("multiple ELF dynamic segments")
            dynamic = (off, sz)
    if dynamic is None:
        return (), hashlib.sha256(data).hexdigest()
    if dynamic[1] % 16 or dynamic[1] > 256 * 1024:
        raise ELFClosureError("unbounded or unaligned ELF dynamic table")
    _range(data, *dynamic)
    tags = []
    for offset in range(dynamic[0], dynamic[0] + dynamic[1], 16):
        tag, value = struct.unpack_from("<QQ", data, offset)
        tags.append((tag, value))
        if tag == 0:
            break
    if not tags or tags[-1][0] != 0:
        raise ELFClosureError("ELF DT_NULL terminator missing")
    if any(t in (15, 29) for t, _ in tags):
        raise ELFClosureError("ELF DT_RPATH/RUNPATH not yet supported: HOLD")
    needed_offsets = [v for t, v in tags if t == 1]
    if not needed_offsets:
        return (), hashlib.sha256(data).hexdigest()
    strtabs = [v for t, v in tags if t == 5]
    lengths = [v for t, v in tags if t == 10]
    if len(strtabs) != 1 or len(lengths) != 1 or not lengths[0]:
        raise ELFClosureError("ELF dynamic string table missing or ambiguous")
    start = None
    for virt, length, offset in loads:
        if virt <= strtabs[0] < virt + length:
            start = offset + strtabs[0] - virt
            break
    if start is None:
        raise ELFClosureError("ELF DT_STRTAB not inside PT_LOAD")
    strings = _range(data, start, lengths[0])
    needed = []
    for off in needed_offsets:
        if off >= len(strings):
            raise ELFClosureError("ELF DT_NEEDED string offset invalid")
        end = strings.find(b"\0", off)
        if end == -1:
            raise ELFClosureError("ELF DT_NEEDED string unterminated")
        try:
            name = strings[off:end].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ELFClosureError("ELF DT_NEEDED is not ASCII") from exc
        if not _LIB.fullmatch(name):
            raise ELFClosureError("ELF DT_NEEDED invalid library name")
        if name in needed:
            raise ELFClosureError("ELF repeated DT_NEEDED")
        needed.append(name)
    return tuple(needed), hashlib.sha256(data).hexdigest()

def audit(rootfs: Path):
    root = Path(rootfs).resolve(strict=True)
    if not root.is_dir():
        raise ELFClosureError("target rootfs directory missing")
    py = "/usr/lib/python3.12"
    roots = ["/usr/bin/python3.12", "/usr/bin/cog"]
    for prefix, pattern, label in (
        (py + "/lib-dynload", "_ssl*.so", "_ssl"),
        (py + "/lib-dynload", "_sqlite3*.so", "_sqlite3"),
        (py + "/site-packages/cryptography/hazmat/bindings", "_rust*.so", "cryptography")):
        directory = root / prefix.lstrip("/")
        found = sorted(directory.glob(pattern)) if directory.is_dir() else []
        if not found:
            raise ELFClosureError("required native Python extension missing: " + label)
        roots.extend(prefix + "/" + item.name for item in found)
    # Include all optional compiled Python extensions discovered in this target
    # and each site package; closure includes their transitive DT_NEEDED too.
    for prefix in (py + "/lib-dynload", py + "/site-packages"):
        folder = root / prefix.lstrip("/")
        if folder.is_dir():
            roots += ["/" + p.relative_to(root).as_posix()
                      for p in sorted(folder.rglob("*.so"))]
    pending = sorted(set(roots))
    files, edges, visited = {}, [], set()
    while pending:
        guest = pending.pop(0)
        target, normalized = _inside(root, guest)
        if normalized in visited:
            continue
        if len(visited) >= 2048:
            raise ELFClosureError("ELF dependency traversal exceeds bound")
        visited.add(normalized)
        if not target.is_file():
            raise ELFClosureError("ELF dependency not a regular file")
        needed, digest = _read_elf(target)
        files[normalized] = digest
        for lib in needed:
            # Buildroot fixed lib dirs plus the binary's own directory.
            search = (posixpath.dirname(normalized),) + _SEARCH
            candidates = []
            for folder in search:
                p = posixpath.join(folder, lib)
                if (root / p.lstrip("/")).exists() or (root / p.lstrip("/")).is_symlink():
                    resolved, target_guest = _inside(root, p)
                    candidates.append(target_guest)
            candidates = sorted(set(candidates))
            if not candidates:
                raise ELFClosureError("unresolved ELF DT_NEEDED " + lib + " from " + normalized)
            if len(candidates) > 1:
                raise ELFClosureError("ambiguous ELF DT_NEEDED " + lib + " from " + normalized)
            edges.append({"importer": normalized, "needed": lib, "target": candidates[0]})
            pending.append(candidates[0])
    return {
        "schema": "VERAOS_TARGET_ELF_CLOSURE_V1",
        "status": "STATIC_ELF_CLOSURE_VERIFIED_GUEST_UNQUALIFIED",
        "target_machine": "ELF64_LITTLE_ENDIAN_X86_64",
        "native_files_checked": len(files),
        "source_files_sha256": files,
        "edges": sorted(edges, key=lambda e: (e["importer"], e["needed"])),
        "unresolved": [],
        "target_import_executed": False,
        "buildroot_kconfig_resolved_by_this_probe": False,
        "image_built": False,
        "normal_pid1_cog_executed": False,
        "protected_effect_authority": False,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rootfs-directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(args.rootfs_directory)
    except (ELFClosureError, OSError, ValueError, struct.error) as exc:
        print("TARGET_ELF_CLOSURE_HOLD: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
