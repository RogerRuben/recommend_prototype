# -*- coding: utf-8 -*-
"""Frozen subordinate + inactive controller produces a conflict, never a silent -1."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_constraint import compile_conditional_constraint  # noqa: E402
from app.constraint_projection import active_parameter_set, project_constraints  # noqa: E402


DEFINITIONS = {
    "has_cooling": {"parameter_id": "has_cooling", "label": "是否液冷", "value_type": "boolean", "auto_adjustable": 1},
    "cooling_flow": {"parameter_id": "cooling_flow", "label": "冷却液流量", "value_type": "number",
                     "min_value": -1, "max_value": 30, "auto_adjustable": 1},
    "power": {"parameter_id": "power", "label": "功率", "value_type": "number", "min_value": 0, "max_value": 500, "auto_adjustable": 1},
}


def _rules():
    return compile_conditional_constraint("has_cooling", 1, "cooling_flow", -1, 0, 30)["rules"]


def main():
    rules = _rules()

    # Frozen cooling_flow=10 cannot satisfy cooling_flow=-1 under has_cooling=0.
    r = project_constraints({"has_cooling": 0, "cooling_flow": 10}, DEFINITIONS, rules, locked={"cooling_flow"})
    assert r["parameters"]["cooling_flow"] == 10, "frozen value must not be silently overwritten"
    assert r["conflicts"] and r["conflicts"][0]["type"] == "frozen_conditional_conflict", r["conflicts"]

    # Active search space excludes the inactive subordinate even when locked elsewhere.
    aspace = active_parameter_set({"has_cooling": 0, "cooling_flow": -1, "power": 120}, DEFINITIONS, rules, locked={"env"})
    assert "cooling_flow" not in aspace["active_parameters"], aspace
    assert "cooling_flow" in aspace["inactive_parameters"], aspace
    assert "power" in aspace["active_parameters"], aspace
    assert "has_cooling" in aspace["active_parameters"], aspace

    print(json.dumps({"status": "PASS", "message": "冻结条件冲突不静默覆盖，且inactive退出搜索空间"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
