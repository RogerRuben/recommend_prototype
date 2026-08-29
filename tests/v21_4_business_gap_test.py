# -*- coding: utf-8 -*-
"""V21.4 user-visible gaps must use original business units."""
from __future__ import print_function

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.recommendation_explanation import annotate_candidate_recommendations
from app.requirement_assessment import assess_requirements


def _assessment(definition, rule, actual):
    key = rule["parameter_id"]
    return assess_requirements(
        {"params": {key: actual}, "tags": []},
        {"indicator_filters": [rule], "indicator_filter_mode": "all"},
        definitions={key: definition},
    )


def test_numeric_business_gap_is_not_normalized_gap():
    definition = {
        "parameter_id": "attr_006", "label": "重量", "unit": "kg",
        "value_type": "number", "search_type": "continuous",
        "min_value": 2.4, "max_value": 4.2,
    }
    assessment = _assessment(
        definition,
        {"parameter_id": "attr_006", "operator": "lte", "value1": 3.5},
        4.2,
    )
    condition = assessment["conditions"][0]
    assert condition["matched"] is False
    assert abs(condition["business_gap"] - 0.7) < 1e-9, condition
    assert abs(condition["normalized_gap"] - (0.7 / 1.8)) < 1e-6, condition
    assert condition["gap"] == condition["normalized_gap"]

    item = {
        "rank": 1, "strict_filter_satisfied": False,
        "predicted_price_wan": 10, "capability_score": 80,
        "requirement_assessment": assessment,
    }
    annotate_candidate_recommendations([item], {"scenario": "balanced"}, {"attr_006": definition})
    summary = item["recommendation_reason"]["summary"]
    assert "4.2kg" in summary and "3.5kg" in summary, summary
    assert "高于要求0.7kg" in summary, summary
    assert "0.389" not in summary, summary


def test_gte_between_and_equal_business_gap():
    definition = {
        "parameter_id": "x", "label": "尺寸", "unit": "mm",
        "value_type": "number", "search_type": "continuous",
        "min_value": 0, "max_value": 10,
    }
    gte = _assessment(definition, {"parameter_id": "x", "operator": "gte", "value1": 3.5}, 2.8)
    assert abs(gte["conditions"][0]["business_gap"] - 0.7) < 1e-9
    between = _assessment(definition, {"parameter_id": "x", "operator": "range_inside", "value1": 2, "value2": 4}, 5)
    assert between["conditions"][0]["business_gap"] == 1
    equal = _assessment(definition, {"parameter_id": "x", "operator": "lte", "value1": 3.5}, 3.5)
    assert equal["conditions"][0]["matched"] is True
    assert equal["conditions"][0]["business_gap"] == 0


def test_enum_boolean_and_special_states_have_no_numeric_business_gap():
    enum_def = {
        "parameter_id": "material", "label": "材料", "value_type": "enum",
        "search_type": "unordered_enum", "allowed_values_json": '["A","B"]',
    }
    enum_assessment = _assessment(enum_def, {"parameter_id": "material", "operator": "eq", "value1": "A"}, "B")
    assert enum_assessment["conditions"][0]["business_gap"] is None

    bool_def = {"parameter_id": "enabled", "label": "启用", "value_type": "boolean", "search_type": "boolean"}
    bool_assessment = _assessment(bool_def, {"parameter_id": "enabled", "operator": "boolean_is", "value1": 1}, 0)
    assert bool_assessment["conditions"][0]["business_gap"] is None

    special_def = {
        "parameter_id": "state", "label": "状态", "value_type": "number", "search_type": "continuous",
        "min_value": 0, "max_value": 10, "special_value_keys_json": "[-1]",
        "display_value_mapping_json": '{"-1":"无该属性","1":"有"}',
    }
    special_assessment = _assessment(special_def, {"parameter_id": "state", "operator": "eq", "value1": 1}, -1)
    assert special_assessment["conditions"][0]["business_gap"] is None


if __name__ == "__main__":
    test_numeric_business_gap_is_not_normalized_gap()
    test_gte_between_and_equal_business_gap()
    test_enum_boolean_and_special_states_have_no_numeric_business_gap()
    print("PASS V21.4 business gap semantics")

