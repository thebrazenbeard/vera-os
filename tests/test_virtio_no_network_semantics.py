"""Linux may create inactive sit0 even for a QEMU machine with -nic none."""
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))


def configure(tmp_path,names,flags=0x80):
    tmp_path.mkdir(parents=True,exist_ok=True)
    for name in names:
        p=tmp_path/name
        p.mkdir()
        if name=="sit0":
            (p/"flags").write_text(hex(flags))
    return tmp_path


def test_only_loopback_with_dormant_kernel_sit0_is_acceptable(tmp_path):
    from veraos.virtio_guest_probe import require_no_guest_nic
    require_no_guest_nic(configure(tmp_path,["lo","sit0"]))
    assert require_no_guest_nic(configure(tmp_path/"second",["lo"])) is None


def test_ethernet_or_active_sit_tunnel_is_forbidden(tmp_path):
    from veraos.virtio_guest_probe import require_no_guest_nic
    with pytest.raises(RuntimeError,match="NIC"):
        require_no_guest_nic(configure(tmp_path/"eth",["lo","eth0"]))
    with pytest.raises(RuntimeError,match="NIC"):
        require_no_guest_nic(configure(tmp_path/"up",["lo","sit0"],flags=0x81))
    with pytest.raises(RuntimeError,match="NIC"):
        require_no_guest_nic(configure(tmp_path/"missing",["sit0"]))
