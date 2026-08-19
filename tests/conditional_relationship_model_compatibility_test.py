# -*- coding: utf-8 -*-
"""Conditional relationship save-time compatibility against parameter contract."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_compatibility import validate_conditional_relationship  # noqa: E402


def main():
    definitions = {
        "attr_004": {"parameter_id": "attr_004", "label": "冷却液流量", "min_value": 0, "max_value": 30},
    }
    bad = validate_conditional_relationship({
        "template": "conditional_applicability_v2",
        "controller": "attr_001", "target": "attr_004",
        "then": {"mode": "not_applicable", "model_value": -1},
        "otherwise": {"mode": "range", "min": 0, "max": 30},
    }, definitions)
    assert bad["compatible"] is False, bad
    assert any("attr_004" in e and "-1" in e for e in bad["errors"]), bad

    good = validate_conditional_relationship({
        "template": "conditional_applicability_v2",
        "controller": "attr_001", "target": "attr_004",
        "then": {"mode": "not_applicable", "model_value": 0},
        "otherwise": {"mode": "range", "min": 0, "max": 30},
    }, definitions)
    assert good["compatible"] is True, good

    print(json.dumps({"status": "PASS", "message": "条件关系保存前模型兼容检查已生效"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
