"""The VeraOS guest imports require Python HTTPSConnection, which needs Python SSL."""

from pathlib import Path

PROFILE = Path(__file__).resolve().parents[1] / "buildroot/configs/veraos_x86_64_resident_browser_defconfig"


def test_resident_guest_enables_python_ssl_for_HTTPSConnection():
    options = {line.strip() for line in PROFILE.read_text(encoding="utf-8").splitlines()}
    assert "BR2_PACKAGE_PYTHON3=y" in options
    assert "BR2_PACKAGE_PYTHON3_SSL=y" in options
    assert "BR2_PACKAGE_PYTHON3_SQLITE=y" in options
    assert "BR2_PACKAGE_COG_PLATFORM_DRM=y" in options
    assert "# BR2_PACKAGE_COG_PLATFORM_FDO is not set" in options