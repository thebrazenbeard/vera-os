"""The QEMU-only PID1 probe must create a durable store directory."""
import os
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))


def test_probe_creates_state_root_before_preactive_store(tmp_path):
    from veraos.virtio_guest_probe import prepare_probe_state_root
    directory=tmp_path/"resident"/"state"
    assert not directory.exists()
    assert prepare_probe_state_root(directory)==directory
    assert directory.is_dir()
    assert prepare_probe_state_root(directory)==directory
    text=(ROOT/"src/veraos/virtio_guest_probe.py").read_text(encoding="utf8")
    assert text.index("prepare_probe_state_root(STATE)")<text.index("store=pre_active.Store")


def test_probe_rejects_redirected_state_symlink(tmp_path):
    from veraos.virtio_guest_probe import prepare_probe_state_root
    real=tmp_path/"real";real.mkdir()
    link=tmp_path/"redirected"
    try:
        link.symlink_to(real,target_is_directory=True)
    except (OSError,NotImplementedError):
        pytest.skip("Symlink privilege unavailable")
    with pytest.raises(RuntimeError,match="symlink"):
        prepare_probe_state_root(link)
