"""Pinned Buildroot source preflight must reject disabled optional Python modules."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "veraos_buildroot_preflight",
    ROOT / "tools/vm/Probe-ResidentBuildroot.py",
)
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)
PIN = "d030e36bbc9669230c015be971b14b6e062cfdde"


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    upstream = tmp_path / "pinned-buildroot"
    repo = tmp_path / "veraos"
    (upstream / "package/python3").mkdir(parents=True)
    (repo / "buildroot/configs").mkdir(parents=True)
    (repo / "architecture/os").mkdir(parents=True)
    (upstream / "package/python3/python3.mk").write_text(
        "PYTHON3_VERSION_MAJOR = 3.12\n"
        "PYTHON3_VERSION = $(PYTHON3_VERSION_MAJOR).14\n",
        encoding="utf-8",
    )
    kconfig = upstream / "package/python3/Config.in"
    kconfig.write_text(
        "config BR2_PACKAGE_PYTHON3_SQLITE\n"
        "    bool \"sqlite3\"\n"
        "config BR2_PACKAGE_PYTHON3_SSL\n"
        "    bool \"ssl\"\n", encoding="utf-8",
    )
    profile = repo / "buildroot/configs/resident_defconfig"
    profile.write_text(
        "BR2_PACKAGE_PYTHON3=y\nBR2_PACKAGE_PYTHON3_SQLITE=y\n"
        "BR2_PACKAGE_PYTHON3_SSL=y\nBR2_PACKAGE_COG_PLATFORM_DRM=y\n"
        "BR2_PACKAGE_DEJAVU=y\nBR2_PACKAGE_DEJAVU_SANS=y\n",
        encoding="utf-8",
    )
    contract = {
        "candidate": {
            "peeled_git_commit": PIN,
            "target_python_expected": "3.12.14",
            "source_defconfig": "buildroot/configs/resident_defconfig",
        },
        "requires": {
            "python_packages": [],
            "browser_flags": [
                "BR2_PACKAGE_COG_PLATFORM_DRM",
                "BR2_PACKAGE_DEJAVU", "BR2_PACKAGE_DEJAVU_SANS",
            ],
            "python_stdlib_flags": [
                "BR2_PACKAGE_PYTHON3_SQLITE",
                "BR2_PACKAGE_PYTHON3_SSL",
            ],
        },
    }
    (repo / "architecture/os/VERA_OS_RESIDENT_BUILDROOT_CANDIDATE_V1.json").write_text(
        json.dumps(contract), encoding="utf-8",
    )

    def git_info(args, *, text=True):
        assert args[:3] == ["git", "-C", str(upstream.resolve())]
        if "rev-parse" in args:
            return PIN + "\n"
        if "status" in args:
            return ""
        raise AssertionError(f"Unexpected git command: {args}")

    monkeypatch.setattr(preflight.subprocess, "check_output", git_info)
    return upstream, repo, profile, kconfig


def test_guest_stdlib_flags_confirmed_from_upstream_and_source(candidate):
    upstream, repo, _, _ = candidate
    receipt = preflight.probe(upstream, repo)
    assert receipt["status"] == "PINNED_SOURCE_SYMBOLS_VERIFIED_KCONFIG_NOT_RUN"
    assert receipt["image_built"] is False
    assert receipt["resident_runtime_qualified"] is False
    assert receipt["ready_for_authorized_build"] is False
    assert receipt["build_readiness"] == "NOT_READY_KCONFIG_UNRESOLVED"


def test_missing_python_ssl_is_rejected_before_any_build(candidate):
    upstream, repo, profile, _ = candidate
    profile.write_text(
        profile.read_text(encoding="utf-8").replace("BR2_PACKAGE_PYTHON3_SSL=y\n", ""),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="BR2_PACKAGE_PYTHON3_SSL"):
        preflight.probe(upstream, repo)


def test_explicit_disabled_python_ssl_conflicts_with_enabled_flag(candidate):
    upstream, repo, profile, _ = candidate
    profile.write_text(
        profile.read_text(encoding="utf-8") +
        "# BR2_PACKAGE_PYTHON3_SSL is not set\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="BR2_PACKAGE_PYTHON3_SSL"):
        preflight.probe(upstream, repo)


def test_undefined_python_ssl_symbol_in_pinned_buildroot_is_rejected(candidate):
    upstream, repo, _, kconfig = candidate
    kconfig.write_text(
        "config BR2_PACKAGE_PYTHON3_SQLITE\n    bool \"sqlite3\"\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="BR2_PACKAGE_PYTHON3_SSL"):
        preflight.probe(upstream, repo)


def test_missing_cog_font_or_drm_source_flags_rejected(candidate):
    upstream, repo, profile, _ = candidate
    original = profile.read_text(encoding="utf-8")
    for flag in ("BR2_PACKAGE_COG_PLATFORM_DRM",
                 "BR2_PACKAGE_DEJAVU", "BR2_PACKAGE_DEJAVU_SANS"):
        profile.write_text(original.replace(flag + "=y\n", ""), encoding="utf-8")
        with pytest.raises(ValueError, match=flag):
            preflight.probe(upstream, repo)
    profile.write_text(original, encoding="utf-8")
