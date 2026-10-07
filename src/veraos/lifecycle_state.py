from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable


SCHEMA = "VERAOS_LIFECYCLE_STATE_V1"
DEFAULT_LIFECYCLE_ROOT = Path("/var/lib/veraos/lifecycle")
STATE_FILENAME = "boot-epoch.json"


class LifecycleStateError(ValueError):
    pass


@dataclass(frozen=True)
class LifecycleState:
    schema: str
    boot_ordinal: int
    previous_boot_ordinal: int
    observed_at_unix: float
    canonical_memory: bool
    supabase_replacement: bool


def _load_existing(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleStateError("existing lifecycle state is unreadable") from exc
    if not isinstance(value, dict):
        raise LifecycleStateError("existing lifecycle state must be an object")
    if value.get("schema") != SCHEMA:
        raise LifecycleStateError("existing lifecycle state schema mismatch")
    ordinal = value.get("boot_ordinal")
    if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1:
        raise LifecycleStateError("existing boot ordinal must be a positive integer")
    if value.get("canonical_memory") is not False:
        raise LifecycleStateError("lifecycle state cannot claim canonical memory")
    if value.get("supabase_replacement") is not False:
        raise LifecycleStateError("lifecycle state cannot claim Supabase replacement")
    return value


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except (AttributeError, OSError):
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        if hasattr(os, "sync"):
            os.sync()
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


def advance_lifecycle_state(
    state_root: Path = DEFAULT_LIFECYCLE_ROOT,
    *,
    now: Callable[[], float] = time.time,
) -> LifecycleState:
    path = state_root / STATE_FILENAME
    existing = _load_existing(path)
    previous = 0 if existing is None else int(existing["boot_ordinal"])
    state = LifecycleState(
        schema=SCHEMA,
        boot_ordinal=previous + 1,
        previous_boot_ordinal=previous,
        observed_at_unix=float(now()),
        canonical_memory=False,
        supabase_replacement=False,
    )
    _atomic_write_json(path, asdict(state))
    return state


def persistence_marker(state: LifecycleState) -> str:
    return (
        "VERAOS_PERSISTENCE_READY_V1 "
        f"boot_ordinal={state.boot_ordinal} "
        f"previous_boot_ordinal={state.previous_boot_ordinal} "
        "canonical_memory=false "
        "supabase_replacement=false"
    )
