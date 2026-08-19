# -*- coding: utf-8 -*-
"""Public feasibility diagnostics must never contain NaN/Infinity/-Infinity."""
from __future__ import print_function

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.anchor_feasibility import assess_explicit_filter_feasibility  # noqa: E402


def _assert_no_nonfinite(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            _assert_no_nonfinite(value)
    elif isinstance(obj, list):
        for value in obj:
            _assert_no_nonfinite(value)
    elif isinstance(obj, float):
        assert math.isfinite(obj), obj


def main():
    definitions = {"weight": {"parameter_id": "weight", "label": "重量", "min_value": 4.2, "max_value": 10}}
    result = assess_explicit_filter_feasibility([
        {"parameter_id": "weight", "operator": "lte", "value1": 3},
    ], definitions, mode="all")
    conflict = result["conflicts"][0]
    assert conflict["requested_min"] is None, conflict
    assert conflict["requested_max"] == 3, conflict
    assert conflict["requested_min_inclusive"] is True, conflict
    assert conflict["requested_max_inclusive"] is True, conflict

    _assert_no_nonfinite(result)
    # Must be strict-JSON serializable.
    json.dumps(result, allow_nan=False)

    print(json.dumps({"status": "PASS", "message": "可行性诊断 JSON 契约无非有限数"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
