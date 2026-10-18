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

def _inside(root, guest, *, directory=False):
    """Resolve each Linux guest path component within root, never on the host.

    Guest-absolute symlinks (including parents) reset to the guest root.
    Relative symlink targets may ascend only while staying guest-rooted.
    """
    if (not isinstance(guest, str) or not guest.startswith("/")
            or guest.startswith("//") or "\x00" in guest or "\\" in guest
            or ".." in guest.split("/")):
        raise ELFClosureError("invalid guest absolute ELF path")
    pending = guest.split("/")
    parts = []
    links = 0
    while pending:
        part = pending.pop(0)
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise ELFClosureError("guest ELF symlink escapes rootfs")
            parts.pop()
            continue
        if ":" in part or "\\" in part or "\x00" in part:
            raise ELFClosureError("guest ELF symlink escapes rootfs")
        current = root.joinpath(*parts, part)
        if current.is_symlink():
            links += 1
            if links > 20:
                raise ELFClosureError("guest ELF symlink chain too long")
            target = current.readlink().as_posix()
            if (not target or target.startswith("//")
                    or "\\" in target or "\x00" in target):
                raise ELFClosureError("guest ELF symlink escapes rootfs")
            if target.startswith("/"):
                parts = []
            pending = target.split("/") + pending
            continue
        parts.append(part)
    file = root.joinpath(*parts)
    if not (file.is_dir() if directory else file.is_file()):
        raise ELFClosureError("missing guest ELF " + guest)
    return file, "/" + "/".join(parts)

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
    interpreter = None
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
        if ptyp == 3:  # PT_INTERP: Linux refuses to start without this loader.
            if interpreter is not None:
                raise ELFClosureError("multiple PT_INTERP segments")
            if not 2 <= sz <= 256 or sz != memsz:
                raise ELFClosureError("malformed PT_INTERP size")
            raw = _range(data, off, sz)
            if raw[-1:] != b"\0" or b"\0" in raw[:-1]:
                raise ELFClosureError("PT_INTERP must be one NUL-terminated path")
            try:
                interpreter = raw[:-1].decode("ascii")
            except UnicodeDecodeError as exc:
                raise ELFClosureError("PT_INTERP non-ASCII path") from exc
            if (not interpreter.startswith("/")
                    or posixpath.normpath(interpreter) != interpreter
                    or not re.fullmatch(r"/[A-Za-z0-9_+./-]+", interpreter)
                    or ".." in interpreter.split("/")):
                raise ELFClosureError("PT_INTERP unsafe interpreter path")
    if dynamic is None:
        return (), hashlib.sha256(data).hexdigest(), interpreter
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
        return (), hashlib.sha256(data).hexdigest(), interpreter
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
    return tuple(needed), hashlib.sha256(data).hexdigest(), interpreter

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
        directory, _ = _inside(root, prefix, directory=True)
        found = sorted(directory.glob(pattern))
        if not found:
            raise ELFClosureError("required native Python extension missing: " + label)
        roots.extend(prefix + "/" + item.name for item in found)
    # Include all optional compiled Python extensions discovered in this target
    # and each site package; closure includes their transitive DT_NEEDED too.
    for prefix in (py + "/lib-dynload", py + "/site-packages"):
        try:
            folder, _ = _inside(root, prefix, directory=True)
        except ELFClosureError as exc:
            if not str(exc).startswith("missing guest ELF "):
                raise
            continue
        roots += [prefix + "/" + p.relative_to(folder).as_posix()
                  for p in sorted(folder.rglob("*.so"))]
    pending = sorted(set(roots))
    files, edges, interpreters, visited = {}, [], [], set()
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
        needed, digest, interpreter = _read_elf(target)
        files[normalized] = digest
        if interpreter is not None:
            try:
                _, loader = _inside(root, interpreter)
            except ELFClosureError as exc:
                raise ELFClosureError(
                    "missing or unsafe PT_INTERP interpreter " + interpreter
                    + " from " + normalized) from exc
            interpreters.append({"importer": normalized, "interpreter": loader})
            pending.append(loader)  # Examine the loader ELF and its dependencies too.
        for lib in needed:
            # Buildroot fixed lib dirs plus the binary's own directory.
            search = (posixpath.dirname(normalized),) + _SEARCH
            candidates = []
            for folder in search:
                p = posixpath.join(folder, lib)
                try:
                    _, target_guest = _inside(root, p)
                except ELFClosureError as exc:
                    if not str(exc).startswith("missing guest ELF "):
                        raise
                    continue
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
        "interpreters": sorted(interpreters, key=lambda e: e["importer"]),
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
