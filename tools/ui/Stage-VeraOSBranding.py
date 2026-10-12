#!/usr/bin/env python3
"""Prepare a locally held VeraOS desktop branding stage from Patrick's own files.

Generated raster assets remain outside the Git repository. The tool does not
install, publish, mount disks, or activate a desktop. Only --create needs Pillow;
--verify-stage uses the Python standard library and can run in Buildroot's host.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

SCHEMA = "VERA_OS_LOCAL_DESKTOP_BRANDING_STAGE_V1"
WALLPAPER_SOURCE = "VERA_PC.png"
ICON_SOURCE = "vera small icon.png"
AVATAR_SOURCE = "VERA_FACE_CANON.png"
TARGET_WALLPAPER = "wallpaper-1920x1080.jpg"
ICON_SIZES = (256, 128, 64, 32)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED = {TARGET_WALLPAPER} | {f"launcher-{n}.png" for n in ICON_SIZES}


class BrandingError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def _expected_file_set(include_avatar: bool) -> set[str]:
    return EXPECTED | ({"avatar-512.png"} if include_avatar else set())


def verify_stage(stage: Path) -> dict:
    """Check exact stage names, file bytes, source provenance and no symlink escape."""
    stage = Path(stage)
    if stage.is_symlink() or not stage.is_dir():
        raise BrandingError("Branding stage missing or linked")
    manifest_path = stage / "branding-receipt.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise BrandingError("Branding stage receipt missing or linked")
    try:
        record = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError) as exc:
        raise BrandingError("Invalid branding stage receipt") from exc
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise BrandingError("Wrong branding stage schema")
    if record.get("owner_scope") != "LOCAL_PRIVATE_VERAOS_ONLY" or \
       record.get("installed") is not False or record.get("desktop_render_qualified") is not False:
        raise BrandingError("Branding stage cannot claim deployment or visual qualification")
    include_avatar = record.get("avatar_included")
    if type(include_avatar) is not bool:
        raise BrandingError("Invalid optional avatar classification")
    expected = _expected_file_set(include_avatar)
    if {p.name for p in stage.iterdir()} != expected | {"branding-receipt.json"}:
        raise BrandingError("Unexpected file in branding stage")
    records = record.get("assets")
    if not isinstance(records, list) or len(records) != len(expected):
        raise BrandingError("Incomplete branding asset receipt")
    seen: set[str] = set()
    for entry in records:
        if not isinstance(entry, dict):
            raise BrandingError("Malformed branding receipt entry")
        name = entry.get("file")
        digest = entry.get("sha256")
        length = entry.get("bytes")
        if name not in expected or name in seen or not isinstance(digest, str) or \
           not SHA256.fullmatch(digest) or type(length) is not int or length < 20:
            raise BrandingError("Invalid or duplicate branding asset")
        item = stage / name
        if item.is_symlink() or not item.is_file() or item.stat().st_size != length or sha256_file(item) != digest:
            raise BrandingError("Branding asset changed or is missing")
        seen.add(name)
    if seen != expected:
        raise BrandingError("Branding receipt is missing required assets")
    sources = record.get("sources")
    if not isinstance(sources, list) or len(sources) != (3 if include_avatar else 2):
        raise BrandingError("Branding source provenance missing")
    source_names = {item.get("file") for item in sources if isinstance(item, dict)}
    desired_sources = {WALLPAPER_SOURCE, ICON_SOURCE} | ({AVATAR_SOURCE} if include_avatar else set())
    if source_names != desired_sources or any(
        not isinstance(item.get("sha256"), str) or not SHA256.fullmatch(item["sha256"])
        for item in sources
    ):
        raise BrandingError("Invalid branding source identity")
    return {
        "schema": "VERA_OS_DESKTOP_BRANDING_STAGE_VERIFICATION_V1",
        "status": "LOCAL_BRANDING_FILES_HASH_VERIFIED_NOT_RENDERED",
        "asset_count": len(seen),
        "avatar_included": include_avatar,
        "source_assets": sorted(source_names),
        "receipt_sha256": sha256_file(manifest_path),
        "guest_installed": False,
        "desktop_render_qualified": False,
        "protected_effect_authority": False,
    }


def create(source_dir: Path, output: Path, *, include_avatar: bool = False) -> dict:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise BrandingError("Pillow is required only to create the local branding stage") from exc
    source_dir = Path(source_dir).resolve(strict=True)
    if not source_dir.is_dir():
        raise BrandingError("Source must be a directory")
    output = Path(output).absolute()
    if source_dir == output or source_dir in output.parents:
        raise BrandingError("Do not stage inside original pictures directory")
    if output.exists() or output.is_symlink():
        raise FileExistsError("Refuse to overwrite existing branding stage")
    files = [WALLPAPER_SOURCE, ICON_SOURCE] + ([AVATAR_SOURCE] if include_avatar else [])
    for name in files:
        p = source_dir / name
        if p.is_symlink() or not p.is_file():
            raise BrandingError(f"Required local Vera branding source missing: {name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)  # exclusive; partial failure stays visible and cannot be mistaken for valid
    sources = [{"file": n, "sha256": sha256_file(source_dir / n),
                "bytes": (source_dir / n).stat().st_size} for n in files]
    written: list[dict] = []

    def record(name: str, kind: str, size: tuple[int, int]):
        p = output / name
        written.append({"file": name, "role": kind, "width": size[0],
                        "height": size[1], "bytes": p.stat().st_size,
                        "sha256": sha256_file(p)})

    with Image.open(source_dir / WALLPAPER_SOURCE) as original:
        if original.width < 1280 or original.height < 720:
            raise BrandingError("Desktop wallpaper is too small for 1920x1080 presentation")
        bg = Image.new("RGBA", original.size, (27, 6, 19, 255))
        bg.alpha_composite(original.convert("RGBA"))
        wall = ImageOps.fit(bg.convert("RGB"), (1920, 1080), Image.Resampling.LANCZOS)
        wall.save(output / TARGET_WALLPAPER, "JPEG", quality=91, optimize=True, progressive=True)
    record(TARGET_WALLPAPER, "desktop_wallpaper", (1920, 1080))

    with Image.open(source_dir / ICON_SOURCE) as original:
        if original.width < 64 or original.height < 64:
            raise BrandingError("Launcher icon source is too small")
        icon = original.convert("RGBA")
        for size in ICON_SIZES:
            result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            scaled = ImageOps.contain(icon, (size, size), Image.Resampling.LANCZOS)
            result.alpha_composite(scaled, ((size-scaled.width)//2, (size-scaled.height)//2))
            name = f"launcher-{size}.png"
            result.save(output / name, "PNG", optimize=True)
            record(name, "launcher_icon", (size, size))

    if include_avatar:
        with Image.open(source_dir / AVATAR_SOURCE) as original:
            avatar = ImageOps.contain(original.convert("RGB"), (512, 512),
                                      Image.Resampling.LANCZOS)
            avatar.save(output / "avatar-512.png", "PNG", optimize=True)
        record("avatar-512.png", "optional_avatar", avatar.size)

    receipt = {
        "schema": SCHEMA,
        "owner_scope": "LOCAL_PRIVATE_VERAOS_ONLY",
        "policy": "NO_GITHUB_UPLOAD_NO_PUBLICATION_WITHOUT_EXACT_USER_AUTHORITY",
        "avatar_included": include_avatar,
        "sources": sources,
        "assets": sorted(written, key=lambda item: item["file"]),
        "installed": False,
        "desktop_render_qualified": False,
        "protected_effect_authority": False,
    }
    with (output / "branding-receipt.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return verify_stage(output)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--create", action="store_true")
    mode.add_argument("--verify-stage", type=Path)
    p.add_argument("--source-dir", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--include-avatar", action="store_true")
    args = p.parse_args()
    if args.create:
        if args.source_dir is None or args.output is None:
            p.error("--create requires --source-dir and --output")
        outcome = create(args.source_dir, args.output, include_avatar=args.include_avatar)
    else:
        if args.source_dir or args.output or args.include_avatar:
            p.error("--verify-stage does not accept creation options")
        outcome = verify_stage(args.verify_stage)
    print(json.dumps(outcome, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BrandingError, OSError, ValueError) as error:
        print(f"VERAOS_BRANDING_HOLD: {error}", file=sys.stderr)
        raise SystemExit(2)
