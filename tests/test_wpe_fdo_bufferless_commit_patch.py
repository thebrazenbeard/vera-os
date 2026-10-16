"""WPEBackend-FDO must not export freed SHM pointers on bufferless commits."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "buildroot/board/veraos/patches/wpebackend-fdo/0001-skip-bufferless-shm-exports.patch"


def test_pinned_backend_egl_and_shm_skip_null_buffer_resource():
    text = PATCH.read_text(encoding="utf8")
    assert "src/ws-egl.cpp" in text
    assert "src/ws-shm.cpp" in text
    assert text.count("+    if (!bufferResource)") == 2
    assert text.count("+        return;") >= 2
    assert "surface.bufferResource = nullptr;" in text
    assert "surface.apiClient->exportShmBuffer(bufferResource, surface.shmBuffer)" in text


def test_bug_and_qualification_are_explicit():
    note = (ROOT / "architecture/os/VERA_OS_WPE_BUFFERLESS_SHM_GUARD_V1.md").read_text()
    assert "bufferless surface commit" in note
    assert "rendering refresh is not qualified" in note.lower()
    assert "WPEBackend-FDO 1.14.3" in note
