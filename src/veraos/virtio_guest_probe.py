"""One-off, explicitly selected QEMU PID1 model-transport qualification.

This diagnostic is NEVER the normal VeraOS boot. Its test-only provider
descriptor is not a trusted production model qualification or admission.
"""
from __future__ import annotations
import importlib
import os
from pathlib import Path
import sys
import threading
import time
from urllib.request import urlopen
import json

from .pid1 import mount_kernel_filesystems,prepare_loopback
from .resident import component_paths
from .virtio_model import MODEL,find_port,VirtioRPC,open_loopback_compat

STAGE=Path("/opt/veraos/components")
STATE=Path("/var/lib/veraos/resident")
BASE_URL="http://127.0.0.1:18766/v1"


def require_no_guest_nic(sysfs: Path = Path("/sys/class/net")) -> None:
    """Only lo and the DOWN kernel sit0 placeholder are allowed.

    Linux may instantiate sit0 without any actual virtual NIC; reject
    ethernet/tap/veth/wlan devices and a sit0 marked administratively UP.
    QEMU also independently supplies -nic none and Docker --network none.
    """
    names=sorted(p.name for p in sysfs.glob("*"))
    if "lo" not in names or any(name not in ("lo","sit0") for name in names):
        raise RuntimeError("unexpected guest network NIC: "+repr(names))
    if "sit0" in names:
        try:
            flags=int((sysfs/"sit0"/"flags").read_text().strip(),16)
        except (OSError,ValueError) as exc:
            raise RuntimeError("cannot verify inactive sit0 NIC") from exc
        if flags & 0x1:  # IFF_UP
            raise RuntimeError("unexpected active sit0 tunnel NIC")


def prepare_probe_state_root(root: Path = STATE) -> Path:
    """Create bounded local development state; refuse redirected state roots."""
    if root.is_symlink():
        raise RuntimeError("probe state root must not be a symlink")
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError("probe state root is not a private directory")
    if os.name != "nt":
        root.chmod(0o700)
    return root


def probe() -> None:
    mount_kernel_filesystems()
    if not prepare_loopback():
        raise RuntimeError("guest local interface unavailable")
    require_no_guest_nic()
    print("VERAOS_DEV_MODEL_GUEST_NO_NIC",flush=True)
    deadline=time.monotonic()+25
    while True:
        try:
            port=find_port()
            break
        except RuntimeError:
            if time.monotonic()>deadline:
                raise
            time.sleep(.5)
    rpc=VirtioRPC.open(port)
    server=None
    store=None
    try:
        server=open_loopback_compat(rpc,port=18766)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        print("VERAOS_DEV_VIRTIO_LOOPBACK_READY",flush=True)
        with urlopen(BASE_URL+"/models",timeout=25) as response:
            inventory=json.load(response)
        if inventory.get("data")!=[{"id":MODEL}]:
            raise RuntimeError("Pinned guest model inventory mismatch")
        print("VERAOS_DEV_PINNED_MODEL_VERIFIED",flush=True)
        sys.path[:0]=component_paths(STAGE)
        portal=importlib.import_module("portal")
        pre_active=importlib.import_module("pre_active")
        from .native_cognition import admit_local_text_route,execute_text_request

        prepare_probe_state_root(STATE)
        store=pre_active.Store(STATE/"qwen4b-development-probe.sqlite3")
        # TEST-ONLY record, not an authentic independent model admission.
        descriptor={
            "schema":"VERA_OS_COGNITION_PROVIDER_V1",
            "provider_id":"dev:virtio-qwen4b",
            "provider_kind":"LOCAL_MODEL",
            "capabilities":["text"],
            "transport":{"kind":"OPENAI_COMPATIBLE_HTTP","attachment":BASE_URL},
            "qualification":{
                "status":"PASS","issuer":"thebrazenbeard/vera-os",
                "subject_sha256":"0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0",
                "suite_sha256":"0"*64,
            },
            "authority":{
                "identity_authority":False,
                "canonical_memory_write_authority":False,
                "protected_effect_authority":False,
                "browser_authority":False,
            },
            "admission":{
                "status":"VERAOS_ROUTE_ELIGIBLE",
                "route_class":"COGNITION_ONLY",
                "selector_owner":"thebrazenbeard/portal",
            },
        }
        route=admit_local_text_route(
            store=store,portal=portal,provider=descriptor,
            base_url=BASE_URL,model=MODEL,timeout_seconds=115,
        )
        response=execute_text_request(
            route,task="Reply briefly with the exact words VERAOS LOCAL MODEL READY.",
            request_id="dev-virtio-real-qwen4b-v1",now=time.time(),
        )
        if response.get("status")!="COMPLETED" or not response.get("final_text"):
            raise RuntimeError("Pre-Active did not complete an actual response: "+repr(response))
        print("VERAOS_DEV_ACTUAL_MODEL_PREACTIVE_COMPLETED run_id="+response["run_id"],flush=True)
        print("VERAOS_DEV_MODEL_RESPONSE="+repr(response["final_text"][:160]),flush=True)
        again=execute_text_request(
            route,task="Reply briefly with the exact words VERAOS LOCAL MODEL READY.",
            request_id="dev-virtio-real-qwen4b-v1",now=time.time()+1,
        )
        if again.get("run_id")!=response["run_id"]:
            raise RuntimeError("Pre-Active did not reuse durable run")
        print("VERAOS_DEV_IDEMPOTENT_REPLAY_PASS",flush=True)
    finally:
        if store is not None:
            store.close()
        if server is not None:
            server.shutdown()
            server.server_close()
        rpc.close()


def main() -> None:
    try:
        probe()
    except Exception as exc:
        print("VERAOS_DEV_MODEL_PROBE_FAILED="+type(exc).__name__+":"+str(exc)[:180],flush=True)
    # Keep PID1 alive for serial-log readback; isolated runner timeout shuts down.
    while True:
        time.sleep(5)


if __name__=="__main__":
    main()
