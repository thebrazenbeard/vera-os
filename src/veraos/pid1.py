from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any, Callable

from .boot_contract import validate_boot_contract
from .composition import validate_manifest
from .portfolio_awareness import validate_capability_map
from .portfolio_implementation import validate_implementation_plan
from .lifecycle_state import (
    DEFAULT_LIFECYCLE_ROOT,
    advance_lifecycle_state,
    persistence_marker,
)


DEFAULT_BOOT_CONTRACT = Path("/etc/veraos/architecture/VERA_OS_BOOT_CONTRACT_V1.json")
DEFAULT_COMPOSITION = Path("/etc/veraos/architecture/VERA_OS_PORTFOLIO_COMPOSITION_V1.json")
DEFAULT_CAPABILITY_MAP = Path("/etc/veraos/architecture/VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json")
DEFAULT_IMPLEMENTATION_PLAN = Path("/etc/veraos/architecture/VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json")
DEFAULT_RUN_ROOT = Path("/run/veraos")


@dataclass(frozen=True)
class BootState:
    schema: str
    pid: int
    product: str
    base_identity: str
    reasoning_owner: str
    provider_router: str
    cognition_provider_required: bool
    trained_vera_model_required: bool
    browser_first_class: bool
    ambient_protected_effect_authority: bool
    portfolio_total: int
    portfolio_integrated: int
    portfolio_excluded: int
    portfolio_implementation_plan_validated: bool


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def prepare_boot_state(
    boot_contract: dict[str, Any],
    composition: dict[str, Any],
    capability_map: dict[str, Any],
    implementation_plan: dict[str, Any],
    *,
    pid: int | None = None,
) -> BootState:
    validate_boot_contract(boot_contract)
    validate_manifest(composition)
    validate_capability_map(capability_map)
    validate_implementation_plan(implementation_plan, capability_map, composition)

    repositories = composition["repositories"]
    integrated = sum(item["disposition"] == "INTEGRATED" for item in repositories)
    excluded = sum(item["disposition"] == "EXCLUDED" for item in repositories)

    runtime = boot_contract["runtime"]
    browser = boot_contract["browser"]
    authority = boot_contract["authority"]
    product = boot_contract["product"]
    return BootState(
        schema="VERAOS_BOOT_READY_V1",
        pid=os.getpid() if pid is None else pid,
        product=product["name"],
        base_identity=product["base_identity"],
        reasoning_owner=runtime["reasoning_owner"],
        provider_router=runtime["provider_router"],
        cognition_provider_required=runtime["cognition_provider_required_for_boot"],
        trained_vera_model_required=runtime["trained_vera_model_required_for_boot"],
        browser_first_class=browser["first_class_capability_required"],
        ambient_protected_effect_authority=authority["ambient_protected_effect_authority"],
        portfolio_total=len(repositories),
        portfolio_integrated=integrated,
        portfolio_excluded=excluded,
        portfolio_implementation_plan_validated=True,
    )


def boot_marker(state: BootState) -> str:
    return (
        "VERAOS_BOOT_READY_V1 "
        f"pid={state.pid} "
        f"base={state.base_identity} "
        f"total={state.portfolio_total} "
        f"integrated={state.portfolio_integrated} "
        f"excluded={state.portfolio_excluded} "
        f"portfolio_plan_validated={str(state.portfolio_implementation_plan_validated).lower()} "
        "cognition_required=false "
        f"browser_first_class={str(state.browser_first_class).lower()} "
        "ambient_protected_effect_authority=false"
    )


def _mount(source: str, target: str, fs_type: str, options: str | None = None) -> None:
    Path(target).mkdir(parents=True, exist_ok=True)
    command = ["mount", "-t", fs_type]
    if options:
        command += ["-o", options]
    command += [source, target]
    subprocess.run(command, check=True)


def mount_kernel_filesystems() -> None:
    mounts = [
        ("proc", "/proc", "proc", None),
        ("sysfs", "/sys", "sysfs", None),
        ("devpts", "/dev/pts", "devpts", "gid=5,mode=620"),
        ("tmpfs", "/run", "tmpfs", "mode=755,nosuid,nodev"),
    ]
    for source, target, fs_type, options in mounts:
        if not os.path.ismount(target):
            _mount(source, target, fs_type, options)


def _install_signal_handlers(stop: dict[str, bool]) -> None:
    def handle(_signum: int, _frame: object) -> None:
        stop["requested"] = True

    signal.signal(signal.SIGTERM, handle)
    signal.signal(signal.SIGINT, handle)


def _reap_children() -> None:
    while True:
        try:
            child, _status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if child == 0:
            return


def run_supervisor(
    *,
    run_root: Path = DEFAULT_RUN_ROOT,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    stop = {"requested": False}
    _install_signal_handlers(stop)
    while not stop["requested"]:
        _reap_children()
        heartbeat = {
            "schema": "VERAOS_PID1_HEARTBEAT_V1",
            "pid": os.getpid(),
            "observed_at_unix": time.time(),
        }
        (run_root / "heartbeat.json").write_text(
            json.dumps(heartbeat, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        sleep(1.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boot-contract", type=Path, default=DEFAULT_BOOT_CONTRACT)
    parser.add_argument("--composition", type=Path, default=DEFAULT_COMPOSITION)
    parser.add_argument("--capability-map", type=Path, default=DEFAULT_CAPABILITY_MAP)
    parser.add_argument("--implementation-plan", type=Path, default=DEFAULT_IMPLEMENTATION_PLAN)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument(
        "--lifecycle-root",
        type=Path,
        default=DEFAULT_LIFECYCLE_ROOT,
    )
    parser.add_argument("--allow-non-pid1", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if os.getpid() != 1 and not args.allow_non_pid1:
        raise SystemExit("vera-init must run as PID 1")

    if os.getpid() == 1:
        mount_kernel_filesystems()

    args.run_root.mkdir(parents=True, exist_ok=True)
    contract = _load_json(args.boot_contract)
    composition = _load_json(args.composition)
    capability_map = _load_json(args.capability_map)
    implementation_plan = _load_json(args.implementation_plan)
    state = prepare_boot_state(
        contract,
        composition,
        capability_map,
        implementation_plan,
    )
    lifecycle_state = advance_lifecycle_state(args.lifecycle_root)
    (args.run_root / "boot-state.json").write_text(
        json.dumps(asdict(state), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    marker = boot_marker(state)
    print(marker, flush=True)
    print(persistence_marker(lifecycle_state), flush=True)

    if args.allow_non_pid1:
        return 0
    run_supervisor(run_root=args.run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
