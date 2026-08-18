# -*- coding: utf-8 -*-
"""Requirement assessment reports an inactive subordinate as 无该属性, gap 1.0."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_constraint import compile_conditional_constraint  # noqa: E402
from app.requirement_assessment import assess_requirements  # noqa: E402


DEFINITIONS = {
    "cooling_flow": {"parameter_id": "cooling_flow", "label": "冷却液流量", "value_type": "number",
                     "min_value": -1, "max_value": 30},
}


def _rules():
    return compile_conditional_constraint("has_cooling", 1, "cooling_flow", -1, 0, 30)["rules"]


def main():
    item = {"params": {"has_cooling": 0, "cooling_flow": -1}, "tags": [],
            "predicted_price_wan": None, "historical_price_wan": None, "capability_score": None}
    request = {"indicator_filters": [{"parameter_id": "cooling_flow", "operator": "gte", "value1": 10}],
               "indicator_filter_mode": "all"}
    assessment = assess_requirements(item, request, DEFINITIONS, {}, constraint_rules=_rules())

    condition = [c for c in assessment["conditions"] if c.get("parameter_id") == "cooling_flow"][0]
    assert condition["actual_state"] == "inactive", condition
    assert condition["inactive_reason"]["controller"] == "has_cooling", condition
    assert condition["gap"] == 1.0, condition
    assert assessment["demand_penalty"] == 1.0, assessment["demand_penalty"]

    print(json.dumps({"status": "PASS", "message": "inactive从属指标按无该属性展示，penalty固定为1.0"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
