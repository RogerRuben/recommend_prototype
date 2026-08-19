# -*- coding: utf-8 -*-
"""Requirement count must be one per explicit user condition, not per group."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.requirement_assessment import assess_requirements  # noqa: E402


def _item(params, tags=None):
    return {
        "agreement_id": "X", "agreement_name": "X", "agreement_source": "historical",
        "params": params, "tags": tags or [], "predicted_price_wan": 12.8,
        "historical_price_wan": 12.8, "capability_score": 80,
    }


def main():
    definitions = {
        "attr_001": {"parameter_id": "attr_001", "label": "是否应急解锁", "value_type": "boolean"},
        "attr_003": {"parameter_id": "attr_003", "label": "锁体材料", "value_type": "enum", "allowed_values_json": '["不锈钢","钛合金","高强铝合金"]', "model_value_mapping_json": '{"不锈钢":1.0,"钛合金":2.0,"高强铝合金":0.0}'},
        "attr_006": {"parameter_id": "attr_006", "label": "重量", "value_type": "number", "min_value": 0, "max_value": 10},
    }
    request = {
        "max_price": 12,
        "selected_tags": ["passive"],
        "indicator_filter_mode": "all",
        "indicator_filters": [
            {"parameter_id": "attr_001", "operator": "boolean_is", "value1": "无"},
            {"parameter_id": "attr_003", "operator": "text_equals", "value1": "不锈钢"},
            {"parameter_id": "attr_006", "operator": "lte", "value1": 2.2},
        ],
    }
    tag_map = {"passive": {"tag_name": "被动", "weight": 1.0}}
    item = _item({"attr_001": 0, "attr_003": 1.0, "attr_006": 4.2}, tags=[])
    result = assess_requirements(item, request, definitions, tag_map)

    # One explicit user condition per chip: price + tag + three indicator filters.
    assert result["total_count"] == 5, result["total_count"]
    assert result["matched_count"] == 2, result["matched_count"]  # 应急锁 + 锁体材料
    assert result["unmatched_count"] == 3, result["unmatched_count"]
    assert len(result["conditions"]) == 5, [c["kind"] for c in result["conditions"]]
    assert not any(c["kind"] == "parameter_group" for c in result["conditions"])
    assert result["indicator_logic"]["mode"] == "all"
    assert result["indicator_logic"]["satisfied"] is False
    assert result["strict_satisfied"] is False

    # OR group: each alternative is still counted, but group satisfaction is logical.
    or_request = {
        "indicator_filter_mode": "any",
        "indicator_filters": [
            {"parameter_id": "attr_006", "operator": "lte", "value1": 2.2},
            {"parameter_id": "attr_003", "operator": "text_equals", "value1": "不锈钢"},
        ],
    }
    or_result = assess_requirements(_item({"attr_006": 4.2, "attr_003": 1.0}), or_request, definitions, {})
    assert or_result["total_count"] == 2, or_result["total_count"]
    assert or_result["matched_count"] == 1, or_result["matched_count"]
    assert or_result["indicator_logic"]["satisfied"] is True, or_result["indicator_logic"]
    assert or_result["strict_satisfied"] is True, or_result

    print(json.dumps({"status": "PASS", "message": "需求计数=用户输入条件数，AND/OR逻辑独立保留"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
