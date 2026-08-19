# -*- coding: utf-8 -*-
"""Mapped enum anchors support string model encodings, not only numeric ones."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator, filters_to_anchors  # noqa: E402


PARAMETER_DEFINITIONS = {
    "attr_mat": {
        "parameter_id": "attr_mat", "label": "材料", "value_type": "enum",
        "search_type": "unordered_enum", "min_value": None, "max_value": None,
        "allowed_values_json": '["不锈钢","钛合金"]',
        "model_value_mapping_json": '{"不锈钢":"SS","钛合金":"TI"}',
        "auto_adjustable": 1, "enabled": 1,
    },
}


def main():
    bounds = filters_to_anchors(
        [{"parameter_id": "attr_mat", "operator": "text_equals", "value1": "不锈钢"}],
        PARAMETER_DEFINITIONS, "all",
    )
    assert bounds["attr_mat"]["allowed"] == ["SS"], bounds

    gen = HistorySeededGenerator(None, None, None, None)
    locked, conflicts = gen._anchor_demands(
        {"attr_mat": "TI"}, bounds, PARAMETER_DEFINITIONS,
    )
    assert locked["attr_mat"] == "SS", locked
    assert not conflicts, conflicts

    locked2, _conflicts2 = gen._anchor_demands(
        {"attr_mat": "SS"}, bounds, PARAMETER_DEFINITIONS,
    )
    assert locked2["attr_mat"] == "SS", locked2

    print(json.dumps({"status": "PASS", "message": "字符串模型编码的枚举也能正确锚定"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
