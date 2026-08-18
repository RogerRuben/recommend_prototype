# -*- coding: utf-8 -*-
"""Boolean third state (无该属性 -> -1) matches through the DataMaster mapping."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.recommender import filter_match  # noqa: E402
from app.value_semantics import mapping_target  # noqa: E402


DEF = {
    "parameter_id": "has_cooling", "label": "是否液冷", "value_type": "boolean",
    "model_value_mapping_json": {"有": 1, "无": 0, "无该属性": -1},
}


def main():
    assert mapping_target("无该属性", DEF) == -1
    assert mapping_target("有", DEF) == 1

    # Filtering by the third state matches the inactive value and its encodings.
    rule = {"parameter_id": "has_cooling", "operator": "boolean_is", "value1": "无该属性"}
    assert filter_match({"has_cooling": -1}, rule, DEF) is True
    assert filter_match({"has_cooling": "-1.0"}, rule, DEF) is True
    assert filter_match({"has_cooling": 0}, rule, DEF) is False

    # Two-value semantics still work, with and without a definition.
    assert filter_match({"has_cooling": 1}, {"parameter_id": "has_cooling", "operator": "boolean_is", "value1": "有"}, DEF) is True
    assert filter_match({"has_cooling": 1.0}, {"parameter_id": "has_cooling", "operator": "boolean_is", "value1": "有"}) is True
    assert filter_match({"has_cooling": 0}, {"parameter_id": "has_cooling", "operator": "boolean_is", "value1": "有"}, DEF) is False

    print(json.dumps({"status": "PASS", "message": "布尔第三态(无该属性/-1)筛选语义完整"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
