"""Fixed dev-only process worker for bounded in-memory fixture data.

Run only through the opt-in Pilot.run_dev_process() launcher. This subprocess
shares its parent Linux UID; it is NOT an OS sandbox or authenticated worker.
It receives no pilot root, task ID, filesystem path, effect grant or secrets.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys


MAX_INPUT_BYTES = 8192


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] not in {"inspect", "digest"}:
        return 2
    worker = args[0]
    data = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        return 2
    result: dict[str, str | int | list[str]] = {
        "worker": worker, "pid": os.getpid(),
        # CPython may synthesize LC_CTYPE during locale coercion with env={}.
        # Report names only: no environment values are ever returned.
        "env_keys": sorted(os.environ),
    }
    if worker == "inspect":
        if not 1 <= len(data) <= 4 or any(c < 48 or c > 57 for c in data):
            return 2
        size = int(data.decode("ascii"))
        if size > MAX_INPUT_BYTES:
            return 2
        result["size"] = size
    else:
        result["sha256"] = hashlib.sha256(data).hexdigest()
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
