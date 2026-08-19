# -*- coding: utf-8 -*-
"""Generation preflight must accept canonical string model encodings."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator  # noqa: E402


PARAMETER_DEFINITIONS = {
    "attr_mat": {
        "parameter_id": "attr_mat", "label": "材料", "value_type": "enum",
        "search_type": "unordered_enum", "min_value": None, "max_value": None,
        "allowed_values_json": '["不锈钢","钛合金"]',
        "model_value_mapping_json": '{"不锈钢":"SS","钛合金":"TI"}',
        "auto_adjustable": 1, "enabled": 1,
    },
}


class _Runtime(object):
    schema = {"product_code": "P1"}

    def all_feature_specs(self):
        return [{"key": "attr_mat", "label": "材料", "required": True, "missing_policy": "reject"}]


class _Store(object):
    def runtime_parameters(self, params):
        return dict(params)


def main():
    gen = HistorySeededGenerator(_Store(), _Runtime(), None, None)
    preflight = gen._generation_input_preflight(
        [{"params": {"attr_mat": "SS"}, "base": {"agreement_id": "H-01"}}],
        PARAMETER_DEFINITIONS,
    )
    assert preflight is not None, preflight
    assert preflight["eligible_seed_count"] == 1, preflight
    assert preflight["seeds"][0]["eligible"] is True, preflight["seeds"]
    assert preflight["unmapped_values"] == {}, preflight["unmapped_values"]

    print(json.dumps({"status": "PASS", "message": "字符串模型编码不会在生成预检中被误判未映射"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
