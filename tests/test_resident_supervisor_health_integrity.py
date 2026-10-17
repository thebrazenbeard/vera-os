"""Fail closed on spoofed or incomplete resident health; source-only supervisor test."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veraos.resident import ResidentSupervisor


def _health(**changes):
    valid = {
        "schema": "VERAOS_RESIDENT_STATUS_V1",
        "pid": 8421,
        "status": "COMPOSED_NO_COGNITION",
        "canonical_runtime_qualified": False,
        "cognition_route_qualified": False,
        "protected_effect_authority": False,
    }
    valid.update(changes)
    return valid


def _check(health):
    supervisor = ResidentSupervisor(
        [sys.executable], health=lambda: health,
    )
    supervisor.child = Mock(pid=8421)
    supervisor.child.poll.return_value = None
    return supervisor.tick(12.0)


def test_valid_no_provider_health_is_recognized():
    assert _check(_health()) == "COMPOSED_NO_COGNITION"


@pytest.mark.parametrize("change", [
    {"schema": None},
    {"schema": "OTHER"},
    {"pid": 8422},
    {"status": "RUNNING"},
    {"status": "ADMITTED"},
    {"status": ""},
    {"canonical_runtime_qualified": True},
    {"cognition_route_qualified": True},
    {"protected_effect_authority": True},
    {"protected_effect_authority": 0},
])
def test_supervisor_refuses_incomplete_or_forged_health(change):
    assert _check(_health(**change)) == "RUNNING_UNVERIFIED"


def test_supervisor_refuses_missing_boolean_and_schema_fields():
    for field in (
        "schema", "canonical_runtime_qualified",
        "cognition_route_qualified", "protected_effect_authority",
    ):
        health = _health()
        del health[field]
        assert _check(health) == "RUNNING_UNVERIFIED"
