# -*- coding: utf-8 -*-
"""Demand anchors must create missing seed parameters when the user explicitly requests them."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator, filters_to_anchors  # noqa: E402


PARAMETER_DEFINITIONS = {
    "attr_006": {
        "parameter_id": "attr_006", "label": "重量", "value_type": "number",
        "search_type": "continuous", "min_value": 0, "max_value": 10,
        "decimal_places": 1, "auto_adjustable": 1, "enabled": 1,
    },
    "attr_003": {
        "parameter_id": "attr_003", "label": "锁体材料", "value_type": "enum",
        "search_type": "unordered_enum", "min_value": 0, "max_value": 3,
        "allowed_values_json": '["不锈钢","钛合金","高强铝合金"]',
        "model_value_mapping_json": '{"不锈钢":1.0,"钛合金":2.0,"高强铝合金":0.0}',
        "auto_adjustable": 1, "enabled": 1,
    },
}


def main():
    gen = HistorySeededGenerator(None, None, None, None)

    # Missing numeric field requested by the user is created from the demand.
    bounds = filters_to_anchors(
        [{"parameter_id": "attr_006", "operator": "lte", "value1": 2.2}],
        PARAMETER_DEFINITIONS, "all",
    )
    params = {}
    locked, conflicts = gen._anchor_demands(params, bounds, PARAMETER_DEFINITIONS)
    assert locked["attr_006"] == 2.2, locked
    assert params["attr_006"] == 2.2, params
    assert not conflicts, conflicts

    # Missing enum field is created as the canonical business value.
    enum_bounds = filters_to_anchors(
        [{"parameter_id": "attr_003", "operator": "text_equals", "value1": "不锈钢"}],
        PARAMETER_DEFINITIONS, "all",
    )
    params2 = {}
    locked2, conflicts2 = gen._anchor_demands(params2, enum_bounds, PARAMETER_DEFINITIONS)
    assert locked2["attr_003"] == "不锈钢", locked2
    assert params2["attr_003"] == "不锈钢", params2
    assert not conflicts2, conflicts2

    print(json.dumps({"status": "PASS", "message": "缺失Seed字段由用户明确条件自动创建并 canonicalize"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
