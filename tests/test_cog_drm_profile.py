"""Regression guard for Cog's implicit Wayland/FDO default."""
from pathlib import Path

PROFILE = (
    Path(__file__).resolve().parents[1]
    / "buildroot" / "configs" / "veraos_x86_64_resident_browser_defconfig"
)


def test_resident_browser_explicitly_selects_drm_without_wayland_fdo():
    lines = {line.strip() for line in PROFILE.read_text(encoding="utf-8").splitlines()}
    assert "BR2_PACKAGE_COG=y" in lines
    assert "BR2_PACKAGE_COG_PLATFORM_DRM=y" in lines
    # Buildroot 2025.02.18 defaults FDO to yes unless explicitly disabled.
    # FDO requires Cairo, absent in this direct-DRM profile.
    assert "# BR2_PACKAGE_COG_PLATFORM_FDO is not set" in lines
    assert "BR2_PACKAGE_COG_PLATFORM_FDO=y" not in lines