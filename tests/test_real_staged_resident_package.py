"""Actual 431-file pinned stage -> disposable directory-rootfs byte acceptance.

Simulated package file layout only; no Buildroot, guest, installation, QEMU.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

import pytest
from test_resident_canonical_task import STAGE

ROOT = Path(__file__).resolve().parents[1]
FULL_STAGE = STAGE.parent
SPEC=importlib.util.spec_from_file_location(
    "actual_resident_file_audit",ROOT/"tools/vm/Verify-VeraOSResidentFiles.py")
audit=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

pytestmark=pytest.mark.skipif(
    not (FULL_STAGE/"VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json").is_file(),
    reason="Independently staged exact repo set unavailable"
)


@pytest.fixture
def rootfs(tmp_path):
    target=tmp_path/"rootfs"
    shutil.copytree(STAGE,target/"opt/veraos/components")
    receipt=target/"etc/veraos/architecture/VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json"
    receipt.parent.mkdir(parents=True)
    shutil.copyfile(FULL_STAGE/"VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json",receipt)
    return target


def verify(rootfs):
    reader=audit._rootfs("directory",rootfs,ROOT)
    return audit.verify_image(FULL_STAGE,ROOT,reader)


def test_exact_staged_source_files_byte_match_rootfs_layout(rootfs):
    proof=verify(rootfs)
    assert proof["resident_files_verified"]==431
    import hashlib
    assert proof["stage_receipt_sha256"]==hashlib.sha256(
        (FULL_STAGE/"VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json").read_bytes()
    ).hexdigest()
    assert proof["guest_import_qualified"] is False
    assert proof["graphical_desktop_qualified"] is False
    assert proof["protected_effect_authority"] is False


def test_rootfs_modified_import_bytes_fail_audit(rootfs):
    f=rootfs/"opt/veraos/components/vera_mono/packages/vera_core/src/vera_core/local_conversation.py"
    f.write_bytes(f.read_bytes()+b"\n# false appended source\n")
    with pytest.raises(audit.ResidentIntegrityError,match="source byte mismatch"):
        verify(rootfs)


def test_rootfs_wrong_embedded_receipt_or_missing_portal_module_fail(rootfs):
    receipt=rootfs/"etc/veraos/architecture/VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json"
    receipt.write_bytes(receipt.read_bytes()+b" ")
    with pytest.raises(audit.ResidentIntegrityError,match="Embedded receipt"):
        verify(rootfs)
    shutil.copyfile(FULL_STAGE/"VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json",receipt)
    (rootfs/"opt/veraos/components/portal/portal/vera_task_handoff.py").unlink()
    with pytest.raises(audit.ResidentIntegrityError,match="source byte mismatch"):
        verify(rootfs)
