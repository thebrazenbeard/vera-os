from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/"buildroot/board/veraos/patches/cog/0002-drm-shm-frame-row-bounds.patch"


def test_guard_reports_exact_format_dimensions_without_guessing_bytes_per_pixel():
    patch=PATCH.read_text(encoding="utf-8")
    assert "shm=%dx%d stride=%d format=%u gbm=%ux%u" in patch
    assert "wl_shm_buffer_get_format(shm_buffer)" in patch
    assert "drop invalid SHM frame" in patch
    assert "stride < width * 4" in patch
