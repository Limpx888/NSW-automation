"""Quick CLI to demo rank_causes without the API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.reasoning.rank_causes import explain_rules, rank_causes

DEMO = {
    "material": "solder_paste",
    "pattern": "dot",
    "amount": "too_small",
    "frequency": "continuous",
    "recent_change": "nozzle",
    "location": "multiple",
    "powder_type": "T6",
    "nozzle_id_um": 60,
}


def main() -> None:
    payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else DEMO
    result = rank_causes(payload)
    print(explain_rules(result))
    print()
    print("Ranked causes")
    for cause in result["ranked_causes"]:
        print(f"  {cause['likelihood_pct']:5.1f}%  {cause['name']}")
    print()
    print("Check first")
    for step in result["action_plan"]:
        print(f"  {step['step']}. {step['instruction']}")


if __name__ == "__main__":
    main()
