# -*- coding: utf-8 -*-
"""Shared requirement assessment: evidence, OR/AND, unknown, and soft history."""
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
    definitions = {"protection_grade": {"parameter_id": "protection_grade", "label": "防护等级", "value_type": "ip_grade"},
                   "power": {"parameter_id": "power", "label": "功率", "value_type": "number"}}

    # Case A: both candidates show, each with a different unmet condition.
    request_a = {"max_price": 12, "min_capability": 100}
    a = assess_requirements(_item("A", capability=98, price=11.5), request_a, definitions, {})
    b = assess_requirements(_item("B", capability=103, price=13.0), request_a, definitions, {})
    assert a["strict_satisfied"] is False and a["unmatched_count"] == 1  # capability unmet
    assert b["strict_satisfied"] is False and b["unmatched_count"] == 1  # price unmet
    kinds_a = {c["kind"] for c in a["conditions"] if c["status"] == "unmatched"}
    kinds_b = {c["kind"] for c in b["conditions"] if c["status"] == "unmatched"}
    assert kinds_a == {"capability"}, kinds_a
    assert kinds_b == {"price"}, kinds_b

    # Case B: AND indicator filters -> 1/2 matched, not strict.
    request_b = {"indicator_filters": [
        {"parameter_id": "protection_grade", "operator": "gte", "value1": "IP65"},
        {"parameter_id": "power", "operator": "gte", "value1": 100},
    ], "indicator_filter_mode": "all"}
    b_item = _item("H", capability=100, price=10, params={"protection_grade": "IP64", "power": 110})
    assess_b = assess_requirements(b_item, request_b, definitions, {})
    assert assess_b["strict_satisfied"] is False

    # Case C: OR indicator filters -> one satisfied makes the group satisfied.
    request_c = {"indicator_filters": [
        {"parameter_id": "protection_grade", "operator": "gte", "value1": "IP65"},
        {"parameter_id": "low_temp", "operator": "boolean_is", "value1": "有"},
    ], "indicator_filter_mode": "any"}
    c_item = _item("C", capability=100, price=10, params={"protection_grade": "IP64", "low_temp": 1})
    assess_c = assess_requirements(c_item, request_c, definitions, {})
    group = [c for c in assess_c["conditions"] if c["kind"] == "parameter_group"]
    assert group and group[0]["matched"] is True, "OR group must be satisfied when one side matches"

    # Case D-ish / unknown: capability absent -> unknown, not unmatched.
    request_unknown = {"min_capability": 100}
    unk = assess_requirements(_item("U", capability=None, price=10), request_unknown, definitions, {})
    assert unk["unknown_count"] == 1 and unk["unmatched_count"] == 0, unk

    # Soft historical recommendation keeps non-matching history and ranks strict first.
    items = [
        _item("OK", capability=110, price=11),
        _item("GAP", capability=80, price=9),
    ]
    ranked = rank_agreements(items, {"max_price": 12, "min_capability": 100}, {}, definitions=definitions, tag_map={})
    assert len(ranked) == 2, "soft recommendation must keep both historical items"
    assert ranked[0]["agreement_id"] == "OK", "fully satisfied must rank first"
    assert ranked[1].get("requirement_assessment", {}).get("strict_satisfied") is False

    print(json.dumps({"status": "PASS", "message": "统一需求评估与软匹配历史推荐"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
