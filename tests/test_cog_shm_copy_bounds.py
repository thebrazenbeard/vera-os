"""Exercise the source-bound C fix gate for Cog's unsafe mismatched SHM/GBM copy."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "buildroot/board/veraos/patches/cog/0002-drm-shm-frame-row-bounds.patch"


def test_guard_patch_exists_and_bounds_source_and_target_rows():
    text = PATCH.read_text(encoding="utf-8")
    assert "cog-drm-modeset-renderer.c" in text
    assert "stride < width * 4" in text
    assert "bo_stride < width * 4" in text
    assert "gbm_bo_get_height" in text
    assert "gbm_bo_get_width" in text
    assert "wl_shm_buffer_end_access" in text
    assert "gbm_bo_unmap" in text
    assert "memcpy" in text


def test_guard_denies_out_of_bounds_frame_copy_instead_of_spoofing_rendering():
    text = PATCH.read_text(encoding="utf-8")
    assert "drop invalid SHM frame" in text
    assert "rendering is not qualified" in (
        ROOT / "architecture/os/VERA_OS_COG_SHM_BOUNDS_FIX_V1.md"
    ).read_text(encoding="utf-8").lower()
