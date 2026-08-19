# -*- coding: utf-8 -*-
"""Strict < and > at engineering boundaries must be treated as infeasible."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.anchor_feasibility import assess_explicit_filter_feasibility  # noqa: E402


def main():
    defs_min = {"weight": {"parameter_id": "weight", "label": "重量", "min_value": 4.2, "max_value": 10}}
    strict_below = assess_explicit_filter_feasibility([
        {"parameter_id": "weight", "operator": "lt", "value1": 4.2},
    ], defs_min, mode="all")
    assert strict_below["strictly_feasible"] is False, strict_below
    assert strict_below["conflicts"][0]["reason"] == "requested_upper_below_engineering_min", strict_below

    inclusive_below = assess_explicit_filter_feasibility([
        {"parameter_id": "weight", "operator": "lte", "value1": 4.2},
    ], defs_min, mode="all")
    assert inclusive_below["strictly_feasible"] is True, inclusive_below

    defs_max = {"weight": {"parameter_id": "weight", "label": "重量", "min_value": 2, "max_value": 10}}
    strict_above = assess_explicit_filter_feasibility([
        {"parameter_id": "weight", "operator": "gt", "value1": 10},
    ], defs_max, mode="all")
    assert strict_above["strictly_feasible"] is False, strict_above
    assert strict_above["conflicts"][0]["reason"] == "requested_lower_above_engineering_max", strict_above

    inclusive_above = assess_explicit_filter_feasibility([
        {"parameter_id": "weight", "operator": "gte", "value1": 10},
    ], defs_max, mode="all")
    assert inclusive_above["strictly_feasible"] is True, inclusive_above

    print(json.dumps({"status": "PASS", "message": "严格边界 < > 与工程边界无交集时正确判定不可行"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
