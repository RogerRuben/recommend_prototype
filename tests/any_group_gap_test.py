# -*- coding: utf-8 -*-
"""ANY/AND parameter_group.gap must equal the group's demand_penalty contribution."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.requirement_assessment import assess_requirements  # noqa: E402


def _item(params):
    return {"agreement_id": "X", "params": params, "tags": [],
            "predicted_price_wan": None, "historical_price_wan": None, "capability_score": None}


def main():
    definitions = {
        "a": {"parameter_id": "a", "label": "A", "value_type": "number", "min_value": 0, "max_value": 100},
        "b": {"parameter_id": "b", "label": "B", "value_type": "number", "min_value": 0, "max_value": 100},
    }
    filters = [
        {"parameter_id": "a", "operator": "gte", "value1": 100},
        {"parameter_id": "b", "operator": "gte", "value1": 100},
    ]

    # ANY: closest alternative (a gap = (100-98)/100 = 0.02) drives the penalty.
    any_assessment = assess_requirements(_item({"a": 98, "b": 10}), {"indicator_filters": filters, "indicator_filter_mode": "any"}, definitions, {})
    assert abs(any_assessment["indicator_logic"]["gap"] - 0.02) < 1e-9, any_assessment["indicator_logic"]["gap"]
    assert abs(any_assessment["demand_penalty"] - 0.02) < 1e-9, any_assessment["demand_penalty"]

    # AND: the gap is the sum of the failed rules' gaps.
    and_assessment = assess_requirements(_item({"a": 98, "b": 10}), {"indicator_filters": filters, "indicator_filter_mode": "all"}, definitions, {})
    assert abs(and_assessment["indicator_logic"]["gap"] - (0.02 + 0.9)) < 1e-9, and_assessment["indicator_logic"]["gap"]
    assert abs(and_assessment["demand_penalty"] - 0.92) < 1e-9, and_assessment["demand_penalty"]

    print(json.dumps({"status": "PASS", "message": "ANY组gap=最近alternative，与demand_penalty一致"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
