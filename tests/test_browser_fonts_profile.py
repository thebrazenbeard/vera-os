"""A browser image without actual font files cannot be called graphical."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "buildroot/configs/veraos_x86_64_resident_browser_defconfig"


def test_resident_browser_requires_usable_sans_font():
    text = PROFILE.read_text(encoding="utf-8")
    assert "BR2_PACKAGE_COG_PLATFORM_DRM=y" in text
    assert "BR2_PACKAGE_DEJAVU=y" in text
    assert "BR2_PACKAGE_DEJAVU_SANS=y" in text
    assert "# BR2_PACKAGE_DEJAVU_MONO is not set" in text
    assert "# BR2_PACKAGE_DEJAVU_SERIF is not set" in text


def test_font_dependency_is_not_just_config_file_presence():
    doc = (ROOT / "architecture/os/VERA_OS_FONT_RENDERING_FIX_V1.md").read_text(
        encoding="utf-8"
    )
    assert "No TTF fonts" in doc
    assert "framebuffer" in doc
    assert "rendering is not qualified" in doc.lower()
