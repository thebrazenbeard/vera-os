from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from veraos.virtio_model import MODEL,PORT_NAME


def test_model_is_under_four_decimal_gigabytes_and_boot_opt_in():
    from importlib.util import spec_from_file_location,module_from_spec
    import sys
    path=ROOT/"tools/vm/ollama_virtio_relay.py"
    spec=spec_from_file_location("relay_packaged",path)
    mod=module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.MODEL_BYTES<4_000_000_000
    assert mod.MODEL==MODEL=="qwen3:4b-instruct"
    assert len(mod.MODEL_DIGEST)==64
    assert PORT_NAME=="org.veraos.model.v1"
    init=(ROOT/"buildroot/board/veraos/x86_64/rootfs-overlay/sbin/vera-virtio-probe").read_text()
    normal=(ROOT/"buildroot/board/veraos/x86_64/rootfs-overlay/sbin/vera-init").read_text()
    assert "virtio_guest_probe" in init
    assert "virtio_guest_probe" not in normal
    assert "model" not in normal
    post=(ROOT/"buildroot/board/veraos/x86_64/post-build.sh").read_text()
    assert 'chmod 0755 "$target_dir/sbin/vera-virtio-probe"' in post


def test_descriptor_remains_development_only():
    source=(ROOT/"src/veraos/virtio_guest_probe.py").read_text()
    assert "TEST-ONLY record" in source
    assert "VERAOS_DEV_MODEL" in source
    assert "VERAOS_DEV_ACTUAL_MODEL_PREACTIVE_COMPLETED" in source
    assert "require_no_guest_nic()" in source
    assert "model_route_qualified" not in source
