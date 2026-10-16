"""A wl_shm_buffer owns wl_resource user_data; Cog must never clobber it."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT/"buildroot/board/veraos/patches/cog/0003-drm-do-not-clobber-wl-shm-userdata.patch"


def test_renderer_ownership_is_stored_on_cogs_buffer_not_wayland_resource():
    patch = PATCH.read_text(encoding="utf8")
    assert "cog-drm-modeset-renderer.c" in patch
    assert "+    void               *owner;" in patch
    assert "buffer->owner" in patch
    assert "-    wl_resource_set_user_data(buffer_resource, self);" in patch
    assert patch.count("-    wl_resource_set_user_data(buffer_resource, self);") == 2
    assert "-    wl_resource_set_user_data(buffer->buffer_resource, NULL);" in patch
    assert "-    CogDrmModesetRenderer *renderer = wl_resource_get_user_data(buffer->buffer_resource);" in patch
    assert "+    CogDrmModesetRenderer *renderer = buffer->owner;" in patch


def test_source_document_preserves_wayland_shm_contract():
    doc=(ROOT/"architecture/os/VERA_OS_COG_WAYLAND_SHM_USERDATA_FIX_V1.md").read_text(encoding="utf8")
    assert "wl_shm_buffer_get" in doc
    assert "wl_resource_get_user_data" in doc
    assert "rendering is not qualified" in doc.lower()


def test_patch_never_replaces_upstream_wpe_exports():
    patch = PATCH.read_text(encoding="utf8")
    assert "WPEBackend-FDO" not in patch
    assert "src/ws-shm.cpp" not in patch
    assert "0002-drm-shm-frame-row-bounds.patch" not in patch
