# -*- coding: utf-8 -*-
"""Continuous indicator gap and partial ranking by demand_penalty."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.requirement_assessment import assess_requirements  # noqa: E402
from app.recommender import rank_agreements  # noqa: E402


def _item(name, capability=None, price=None, params=None, tags=None):
    return {
        "agreement_id": name, "agreement_name": name, "agreement_source": "historical",
        "is_generated": False, "model_evaluation_available": capability is not None,
        "capability_score": capability, "predicted_price_wan": price,
        "cost_effectiveness": (capability / price) if (capability is not None and price) else None,
        "feasibility_probability": 0.8, "physical_gate": {"passed": True},
        "hard_risk_reasons": [], "params": params or {}, "tags": tags or [],
        "conservative_capability_score": capability,
    }


def main():
    definitions = {
        "power": {"parameter_id": "power", "label": "功率", "value_type": "number", "min_value": 0, "max_value": 100},
        "temp": {"parameter_id": "temp", "label": "温度", "value_type": "number", "min_value": 0, "max_value": 100},
    }

    # Continuous gap: 99 vs 100 is far closer than 10 vs 100, so the penalty differs.
    req = {"indicator_filters": [{"parameter_id": "power", "operator": "gte", "value1": 100}], "indicator_filter_mode": "all"}
    near = assess_requirements(_item("A", params={"power": 99}), req, definitions, {})
    far = assess_requirements(_item("B", params={"power": 10}), req, definitions, {})
    assert near["demand_penalty"] < far["demand_penalty"], (near["demand_penalty"], far["demand_penalty"])

    # ANY group failure uses the closest alternative's gap, not a flat 1.0.
    req_any = {"indicator_filters": [
        {"parameter_id": "power", "operator": "gte", "value1": 100},
        {"parameter_id": "temp", "operator": "gte", "value1": 50},
    ], "indicator_filter_mode": "any"}
    # power=10/temp=49 -> temp is only 1 away (gap 0.01)
    close_alt = assess_requirements(_item("C", params={"power": 10, "temp": 49}), req_any, definitions, {})
    # power=98/temp=10 -> temp is 40 away, power 2 away -> min gap 0.02
    far_alt = assess_requirements(_item("D", params={"power": 98, "temp": 10}), req_any, definitions, {})
    assert close_alt["demand_penalty"] < far_alt["demand_penalty"], (close_alt["demand_penalty"], far_alt["demand_penalty"])

    # Partial candidates rank by demand gap before the user's sort key.
    items = [
        _item("FAR", capability=70, price=18),
        _item("NEAR", capability=99, price=10.2),
    ]
    ranked = rank_agreements(items, {"max_price": 10, "min_capability": 100}, {}, definitions=definitions, tag_map={})
    assert [i["agreement_id"] for i in ranked] == ["NEAR", "FAR"], [i["agreement_id"] for i in ranked]

    print(json.dumps({"status": "PASS", "message": "技术指标连续gap + 部分满足按需求距离排序"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
