"""Guard against observed VeraOS guest missing sqlite3 extension.

Exact Python 3.12.14 guest boot passed, but vera_core import failed
in behavior_effect_verification.py on import sqlite3.
"""
from pathlib import Path

PROFILE = (
    Path(__file__).resolve().parents[1]
    / "buildroot/configs/veraos_x86_64_resident_browser_defconfig"
)


def profile_flags(source: str) -> dict[str, bool]:
    values: dict[str, bool] = {}
    for raw in source.splitlines():
        line = raw.strip()
        if line.startswith("BR2_PACKAGE_") and "=" in line:
            key, value = line.split("=", 1)
            if key in values:
                raise ValueError("Duplicate Buildroot package symbol: " + key)
            values[key] = value == "y"
        elif line.startswith("# BR2_PACKAGE_") and line.endswith(" is not set"):
            key = line[2:].split()[0]
            if key in values:
                raise ValueError("Conflicting Buildroot package symbol: " + key)
            values[key] = False
    return values


def test_resident_browser_requires_python_sqlite_extension_and_library():
    flags = profile_flags(PROFILE.read_text(encoding="utf-8"))
    assert flags["BR2_PACKAGE_PYTHON3"] is True
    assert flags["BR2_PACKAGE_SQLITE"] is True
    assert flags["BR2_PACKAGE_PYTHON3_SQLITE"] is True


def test_sqlite_library_alone_does_not_qualify_python_extension():
    flags = profile_flags("BR2_PACKAGE_PYTHON3=y\nBR2_PACKAGE_SQLITE=y\n")
    assert flags.get("BR2_PACKAGE_PYTHON3_SQLITE", False) is False


def test_explicit_disable_and_duplicate_flags_are_rejected():
    disabled = profile_flags(
        "BR2_PACKAGE_PYTHON3=y\n"
        "BR2_PACKAGE_SQLITE=y\n"
        "# BR2_PACKAGE_PYTHON3_SQLITE is not set\n"
    )
    assert disabled["BR2_PACKAGE_PYTHON3_SQLITE"] is False
    for source in (
        "BR2_PACKAGE_PYTHON3_SQLITE=y\nBR2_PACKAGE_PYTHON3_SQLITE=y\n",
        "BR2_PACKAGE_PYTHON3_SQLITE=y\n# BR2_PACKAGE_PYTHON3_SQLITE is not set\n",
    ):
        try:
            profile_flags(source)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid Buildroot sqlite flags accepted")


def test_drm_cog_and_other_resident_dependencies_preserved():
    flags = profile_flags(PROFILE.read_text(encoding="utf-8"))
    assert flags["BR2_PACKAGE_COG_PLATFORM_DRM"] is True
    assert flags["BR2_PACKAGE_COG_PLATFORM_FDO"] is False
    assert flags["BR2_PACKAGE_PYTHON_JSONSCHEMA"] is True
    assert flags["BR2_PACKAGE_PYTHON_CRYPTOGRAPHY"] is True
    assert flags["BR2_PACKAGE_PYTHON_PYYAML"] is True
