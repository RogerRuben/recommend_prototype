# -*- coding: utf-8 -*-
"""Generator demand anchors must use the same Value Semantics as RequirementAssessment."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator, filters_to_anchors  # noqa: E402


PARAMETER_DEFINITIONS = {
    "attr_003": {
        "parameter_id": "attr_003", "label": "锁体材料", "value_type": "enum",
        "search_type": "unordered_enum", "min_value": 0, "max_value": 3,
        "allowed_values_json": '["不锈钢","钛合金","高强铝合金"]',
        "model_value_mapping_json": '{"不锈钢":1.0,"钛合金":2.0,"高强铝合金":0.0}',
        "auto_adjustable": 1, "enabled": 1,
    },
    "attr_001": {
        "parameter_id": "attr_001", "label": "是否应急解锁", "value_type": "boolean",
        "search_type": "boolean", "min_value": -1, "max_value": 1,
        "model_value_mapping_json": '{"无该属性":-1,"有":1,"无":0}',
        "auto_adjustable": 1, "enabled": 1,
    },
}


class _MockStore(object):
    def parameter_map(self):
        return PARAMETER_DEFINITIONS

    def tag_map(self):
        return {}

    def tag_rule_branches(self, selected_tags, max_branches=24):
        return [{
            "rules": [{"parameter_id": "attr_003", "operator": "text_equals", "value1": "不锈钢"}],
            "tag_groups": {"passive": ["attr_003"]},
            "unresolved_tags": [],
        }]

    def constraint_rows(self):
        return []


class _MockRuntime(object):
    pass


def main():
    # Direct anchor compilation: mapped enum label -> encoded 1.0.
    bounds = filters_to_anchors(
        [{"parameter_id": "attr_003", "operator": "text_equals", "value1": "不锈钢"}],
        PARAMETER_DEFINITIONS, "all",
    )
    assert bounds.get("attr_003", {}).get("allowed") == [1.0], bounds

    # Boolean third state survives as an allowed model value, not collapsed to 0/1.
    bounds3 = filters_to_anchors(
        [{"parameter_id": "attr_001", "operator": "boolean_is", "value1": "无该属性"}],
        PARAMETER_DEFINITIONS, "all",
    )
    assert bounds3.get("attr_001", {}).get("allowed") == [-1.0], bounds3

    gen = HistorySeededGenerator(_MockStore(), _MockRuntime(), None, None)
    params = {"attr_003": 2.0, "attr_001": 0.0}
    locked, conflicts = gen._anchor_demands(params, bounds, PARAMETER_DEFINITIONS)
    assert locked["attr_003"] == 1.0, locked
    assert not conflicts, conflicts

    locked3, conflicts3 = gen._anchor_demands({"attr_001": 1.0}, bounds3, PARAMETER_DEFINITIONS)
    assert locked3["attr_001"] == -1.0, locked3
    assert not conflicts3, conflicts3

    # Tag branch must reuse the same compiler: a passive tag's enum rule anchors too.
    branch_bounds, _branch_request, _info = gen._tag_branch_for_seed({"selected_tags": ["passive"], "indicator_filters": [], "indicator_filter_mode": "all"}, 0)
    assert branch_bounds.get("attr_003", {}).get("allowed") == [1.0], branch_bounds

    print(json.dumps({"status": "PASS", "message": "枚举/布尔第三态/标签规则统一编译为生成锚定"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
