# -*- coding: utf-8 -*-
"""DataMaster validation hardening: group refs, array/object types, conditional refs."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_master import validate_business_data  # noqa: E402


def _base(parameters, parameter_groups=None, constraints=None):
    return {
        "products": [{"product_code": "P1", "product_name": "产品1", "enabled": 1}],
        "parameters": parameters,
        "parameter_groups": parameter_groups or [],
        "tags": [], "tag_rules": [], "couplings": [], "constraints": constraints or [],
        "agreements": [],
    }


def main():
    # Unknown group reference.
    errors, _warnings = validate_business_data(_base(
        [{"parameter_id": "A1", "label": "A1", "parameter_group": "不存在", "value_type": "number"}],
        parameter_groups=[{"group_name": "G", "enabled": 1}],
    ))
    assert any("不存在" in e for e in errors), errors

    # allowed_values_json must be an array.
    errors2, _w = validate_business_data(_base([
        {"parameter_id": "A1", "label": "A1", "value_type": "enum", "allowed_values_json": '{"a":1}'},
    ]))
    assert any("允许值必须是JSON数组" in e for e in errors2), errors2

    # model_value_mapping_json must be an object.
    errors3, _w = validate_business_data(_base([
        {"parameter_id": "A1", "label": "A1", "value_type": "enum", "model_value_mapping_json": '[1,2]'},
    ]))
    assert any("模型值映射必须是JSON对象" in e for e in errors3), errors3

    # Conditional metadata references missing parameters.
    errors4, _w = validate_business_data(_base(
        [{"parameter_id": "A1", "label": "A1", "value_type": "number"}],
        constraints=[{
            "rule_id": "R1", "rule_name": "R1", "left_parameter": "A1", "operator": "gte",
            "rule_kind": "conditional_lower", "constraint_group": "G",
            "template_metadata_json": json.dumps({"controller": "MISSING", "target": "A1"}),
        }],
    ))
    assert any("MISSING" in e for e in errors4), errors4

    print(json.dumps({"status": "PASS", "message": "DataMaster校验已覆盖分组引用、数组/对象类型与条件关系引用"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
