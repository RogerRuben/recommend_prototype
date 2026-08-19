# -*- coding: utf-8 -*-
"""AND conditions on the same parameter must be merged before feasibility."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.anchor_feasibility import assess_explicit_filter_feasibility  # noqa: E402


def main():
    definitions = {"weight": {"parameter_id": "weight", "label": "重量", "min_value": 2, "max_value": 10}}

    conflict = assess_explicit_filter_feasibility([
        {"parameter_id": "weight", "operator": "gte", "value1": 6},
        {"parameter_id": "weight", "operator": "lte", "value1": 4},
    ], definitions, mode="all")
    assert conflict["strictly_feasible"] is False, conflict
    assert conflict["conflicts"][0]["reason"] == "explicit_filters_mutually_inconsistent", conflict

    feasible = assess_explicit_filter_feasibility([
        {"parameter_id": "weight", "operator": "gte", "value1": 6},
        {"parameter_id": "weight", "operator": "lte", "value1": 7},
    ], definitions, mode="all")
    assert feasible["strictly_feasible"] is True, feasible

    print(json.dumps({"status": "PASS", "message": "同一参数AND条件联合判定，互斥条件被识别"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
