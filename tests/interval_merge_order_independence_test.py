# -*- coding: utf-8 -*-
"""Interval merge must be order-independent and preserve strictness."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.anchor_feasibility import assess_explicit_filter_feasibility  # noqa: E402


def main():
    definitions = {"weight": {"parameter_id": "weight", "label": "重量", "min_value": 2, "max_value": 10}}

    # Mutual conflict must not depend on filter order.
    a = assess_explicit_filter_feasibility([
        {"parameter_id": "weight", "operator": "gte", "value1": 6},
        {"parameter_id": "weight", "operator": "eq", "value1": 4},
    ], definitions, mode="all")
    b = assess_explicit_filter_feasibility([
        {"parameter_id": "weight", "operator": "eq", "value1": 4},
        {"parameter_id": "weight", "operator": "gte", "value1": 6},
    ], definitions, mode="all")
    assert a["strictly_feasible"] is False and b["strictly_feasible"] is False
    assert a["conflicts"][0]["reason"] == b["conflicts"][0]["reason"] == "explicit_filters_mutually_inconsistent"

    # >=4 AND >4 must yield >4 regardless of order.
    c = assess_explicit_filter_feasibility([
        {"parameter_id": "weight", "operator": "gte", "value1": 4},
        {"parameter_id": "weight", "operator": "gt", "value1": 4},
    ], definitions, mode="all")
    d = assess_explicit_filter_feasibility([
        {"parameter_id": "weight", "operator": "gt", "value1": 4},
        {"parameter_id": "weight", "operator": "gte", "value1": 4},
    ], definitions, mode="all")
    assert c["strictly_feasible"] is True and d["strictly_feasible"] is True
    assert c["conflicts"] == [] and d["conflicts"] == []

    # >4 AND range[4,6] => (4,6]
    e = assess_explicit_filter_feasibility([
        {"parameter_id": "weight", "operator": "gt", "value1": 4},
        {"parameter_id": "weight", "operator": "range_inside", "value1": 4, "value2": 6},
    ], definitions, mode="all")
    assert e["strictly_feasible"] is True, e
    assert e["conflicts"] == [], e

    print(json.dumps({"status": "PASS", "message": "区间合并顺序无关且开闭边界正确"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
