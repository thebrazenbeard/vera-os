from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from veraos.portal_registry import write_portal_project_registry


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the private VeraOS capability catalog as a "
            "Project Runner/P.O.R.T.A.L.-compatible awareness-only registry."
        )
    )
    parser.add_argument(
        "--capability-map",
        type=Path,
        default=(
            ROOT
            / "architecture"
            / "capabilities"
            / "VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    capability_map = json.loads(args.capability_map.read_text(encoding="utf-8"))
    digest = write_portal_project_registry(args.output, capability_map)
    payload = json.loads(args.output.read_text(encoding="utf-8"))

    result = {
        "schema": "VERA_OS_PORTAL_PRIVATE_REGISTRY_EXPORT_V1",
        "output": str(args.output),
        "sha256": digest,
        "projects": len(payload["projects"]),
        "schedulable": sum(
            project["scheduling_state"] == "SCHEDULABLE"
            for project in payload["projects"]
        ),
        "claim_ceiling": (
            "PRIVATE_PORTFOLIO_AWARENESS_ONLY; "
            "NO_SCHEDULING_ACTIVATION; NO_ROUTE_AUTHORITY; "
            "NO_PROTECTED_EFFECT_AUTHORITY"
        ),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
