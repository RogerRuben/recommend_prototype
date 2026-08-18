# -*- coding: utf-8 -*-
"""Constraint projection produces traceable before/after changes."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_constraint import compile_conditional_constraint  # noqa: E402
from app.constraint_projection import project_constraints  # noqa: E402


DEFINITIONS = {
    "has_cooling": {"parameter_id": "has_cooling", "label": "是否液冷", "value_type": "boolean"},
    "cooling_flow": {"parameter_id": "cooling_flow", "label": "冷却液流量", "value_type": "number",
                     "min_value": -1, "max_value": 30},
}


def main():
    rules = compile_conditional_constraint("has_cooling", 1, "cooling_flow", -1, 0, 30)["rules"]
    projection = project_constraints({"has_cooling": 0, "cooling_flow": 10}, DEFINITIONS, rules)
    repair = projection["repairs"][0]
    assert repair["type"] == "conditional_deactivation", repair
    assert repair["before"] == 10 and repair["after"] == -1, repair

    # A trace change can be derived from the repair, matching the move detail shape.
    trace_change = {"parameter_id": repair["parameter"], "before": repair["before"], "after": repair["after"]}
    assert trace_change == {"parameter_id": "cooling_flow", "before": 10, "after": -1}

    print(json.dumps({"status": "PASS", "message": "约束投影产生可追溯的before/after变更"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
