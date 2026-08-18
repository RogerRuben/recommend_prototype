# -*- coding: utf-8 -*-
"""Active search space: inactive subordinates are excluded from every move."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_constraint import compile_conditional_constraint  # noqa: E402
from app.constraint_projection import active_parameter_set  # noqa: E402


DEFINITIONS = {
    "has_cooling": {"parameter_id": "has_cooling", "label": "是否液冷", "value_type": "boolean", "auto_adjustable": 1},
    "cooling_flow": {"parameter_id": "cooling_flow", "label": "冷却液流量", "value_type": "number",
                     "min_value": -1, "max_value": 30, "auto_adjustable": 1},
    "cooling_pressure": {"parameter_id": "cooling_pressure", "label": "冷却压力", "value_type": "number",
                         "min_value": -1, "max_value": 10, "auto_adjustable": 1},
    "power": {"parameter_id": "power", "label": "功率", "value_type": "number", "min_value": 0, "max_value": 500, "auto_adjustable": 1},
}


def _rules():
    lower = compile_conditional_constraint("has_cooling", 1, "cooling_flow", -1, 0, 30)
    pressure = compile_conditional_constraint("has_cooling", 1, "cooling_pressure", -1, 0, 10)
    return lower["rules"] + pressure["rules"]


def main():
    aspace = active_parameter_set({"has_cooling": 0, "cooling_flow": -1, "cooling_pressure": -1, "power": 120},
                                  DEFINITIONS, _rules(), locked={"env"})
    assert "cooling_flow" not in aspace["active_parameters"], aspace
    assert "cooling_pressure" not in aspace["active_parameters"], aspace
    assert sorted(aspace["inactive_parameters"]) == ["cooling_flow", "cooling_pressure"], aspace
    assert "power" in aspace["active_parameters"] and "has_cooling" in aspace["active_parameters"], aspace

    print(json.dumps({"status": "PASS", "message": "inactive从属指标全部退出搜索空间，控制器仍可搜索"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
