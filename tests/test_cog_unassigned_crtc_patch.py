"""Cog's DRM plugin must tolerate an initially unassigned CRTC.

The QEMU guest provided a connected VirtIO connector and 26 valid modes, but
Cog 0.18.4 aborted because the encoder's current CRTC was not assigned.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH_DIR = ROOT / "buildroot/board/veraos/patches/cog"
PROFILE = ROOT / "buildroot/configs/veraos_x86_64_resident_browser_defconfig"


def test_buildroot_profile_selects_source_bound_cog_patch_directory():
    text = PROFILE.read_text(encoding="utf-8")
    assert 'BR2_GLOBAL_PATCH_DIR="$(BR2_EXTERNAL_VERAOS_PATH)/board/veraos/patches"' in text
    assert "BR2_PACKAGE_COG_PLATFORM_DRM=y" in text
    assert "# BR2_PACKAGE_COG_PLATFORM_FDO is not set" in text


def test_cog_patch_handles_unassigned_crtc_only_when_possible_mask_allows():
    patches = list(PATCH_DIR.glob("*.patch"))
    assert len(patches) == 1
    patch = patches[0].read_text(encoding="utf-8")
    assert "platform/drm/cog-platform-drm.c" in patch
    assert "encoder->crtc_id == 0" in patch
    assert "encoder->possible_crtcs & crtc_mask" in patch
    assert "-        if (encoder->possible_crtcs & crtc_mask && encoder->crtc_id == crtc_id)" in patch
    assert "+        if ((encoder->possible_crtcs & crtc_mask)" in patch
    assert "no crtc for encoder found!" not in patch


def test_patch_documentation_distinguishes_workaround_from_rendering_evidence():
    document = (ROOT / "architecture/os/VERA_OS_COG_VIRTIO_CRTC_INIT_FIX_V1.md").read_text()
    assert "no crtc for encoder found!" in document
    assert "rendering is not qualified" in document.lower()
