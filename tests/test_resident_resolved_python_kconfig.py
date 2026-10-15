"""Resolved Buildroot .config must retain VeraOS resident Python import dependencies."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "tools/vm/Verify-VeraOSResolvedConfig.py"
MODULE = importlib.util.module_from_spec(importlib.util.spec_from_file_location("resolved", CHECK))
# Load is delayed until tests run so a missing implementation is a proper red test.
REQUIRED = ("BR2_PACKAGE_PYTHON3", "BR2_PACKAGE_PYTHON3_SQLITE", "BR2_PACKAGE_PYTHON3_SSL")


def validate(tmp_path, lines):
    config = tmp_path / ".config"
    config.write_text("\n".join(lines) + "\n", encoding="utf-8")
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"requires": {"python_stdlib_flags": list(REQUIRED[1:])}}))
    MODULE.__spec__.loader.exec_module(MODULE)
    return MODULE.verify(config, contract)


def test_valid_resolved_config_is_source_evidence_only(tmp_path):
    proof = validate(tmp_path, [f"{flag}=y" for flag in REQUIRED])
    assert proof["status"] == "RESOLVED_STDLIB_CONFIG_READBACK_NOT_IMAGE_QUALIFICATION"
    assert proof["required_symbols"] == list(REQUIRED)
    assert len(proof["config_sha256"]) == 64
    assert proof["image_built"] is False
    assert proof["resident_runtime_qualified"] is False

@pytest.mark.parametrize("bad", [
    ["BR2_PACKAGE_PYTHON3=y", "BR2_PACKAGE_PYTHON3_SQLITE=y"],
    ["BR2_PACKAGE_PYTHON3=y", "# BR2_PACKAGE_PYTHON3_SQLITE is not set", "BR2_PACKAGE_PYTHON3_SSL=y"],
    ["BR2_PACKAGE_PYTHON3=y", "BR2_PACKAGE_PYTHON3_SQLITE=y", "BR2_PACKAGE_PYTHON3_SSL=n"],
    [f"{flag}=y" for flag in REQUIRED] + ["BR2_PACKAGE_PYTHON3_SSL=y"],
    [f"{flag}=y" for flag in REQUIRED] + ["# BR2_PACKAGE_PYTHON3_SSL is not set"],
])
def test_missing_disabled_duplicate_or_conflicting_flags_fail_closed(tmp_path, bad):
    with pytest.raises(ValueError, match="BR2_PACKAGE_PYTHON3"):
        validate(tmp_path, bad)


def test_builder_checks_effective_config_after_olddefconfig_before_compile():
    script = (ROOT / "tools/vm/Build-VeraOSVm.ps1").read_text(encoding="utf-8")
    pos_defconfig = script.index("olddefconfig")
    pos_verifier = script.index("Verify-VeraOSResolvedConfig.py")
    pos_compile = script.index('BR2_JLEVEL="$VERAOS_JOBS"')
    assert pos_defconfig < pos_verifier < pos_compile
    assert 'VERAOS_REQUIRE_RESIDENT_CORE:-0' in script
    assert "--contract" in script

def test_contract_cannot_relax_sqlite_or_ssl(tmp_path):
    config = tmp_path / ".config"
    config.write_text("\n".join(f"{flag}=y" for flag in REQUIRED) + "\n")
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"requires": {
        "python_stdlib_flags": ["BR2_PACKAGE_PYTHON3_SQLITE"]
    }}))
    MODULE.__spec__.loader.exec_module(MODULE)
    with pytest.raises(ValueError, match="required resident Python modules"):
        MODULE.verify(config, contract)


def test_command_line_fail_closed(tmp_path):
    import subprocess
    import sys

    config = tmp_path / ".config"
    config.write_text("BR2_PACKAGE_PYTHON3=y\nBR2_PACKAGE_PYTHON3_SQLITE=y\n")
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"requires": {
        "python_stdlib_flags": list(REQUIRED[1:])
    }}))
    cmd = [sys.executable, str(CHECK), "--config", str(config),
           "--contract", str(contract)]
    failed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert failed.returncode == 2
    assert "VERAOS_RESOLVED_CONFIG_HOLD" in failed.stderr
    config.write_text("\n".join(f"{flag}=y" for flag in REQUIRED) + "\n")
    passed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert passed.returncode == 0
    assert json.loads(passed.stdout)["image_built"] is False
