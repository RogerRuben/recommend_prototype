# -*- coding: utf-8 -*-
"""Conditional constraint projection: inactive collapse and active restoration."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_constraint import compile_conditional_constraint  # noqa: E402
from app.constraint_projection import project_constraints  # noqa: E402


DEFINITIONS = {
    "has_cooling": {"parameter_id": "has_cooling", "label": "是否液冷", "value_type": "boolean"},
    "cooling_flow": {"parameter_id": "cooling_flow", "label": "冷却液流量", "value_type": "number",
                     "min_value": -1, "max_value": 30},
}


def _rules():
    return compile_conditional_constraint("has_cooling", 1, "cooling_flow", -1, 0, 30)["rules"]


def main():
    rules = _rules()

    # Active controller: a legal value is left untouched.
    r1 = project_constraints({"has_cooling": 1, "cooling_flow": 10}, DEFINITIONS, rules)
    assert r1["parameters"]["cooling_flow"] == 10, r1
    assert r1["inactive_parameters"] == []

    # Controller 1 -> 0 collapses the subordinate to -1.
    r2 = project_constraints({"has_cooling": 0, "cooling_flow": 10}, DEFINITIONS, rules)
    assert r2["parameters"]["cooling_flow"] == -1, r2
    assert r2["inactive_parameters"] == ["cooling_flow"]
    assert any(rep["type"] == "conditional_deactivation" for rep in r2["repairs"])

    # Controller 0 -> 1 restores a legal active value (seed history first).
    r3 = project_constraints({"has_cooling": 1, "cooling_flow": -1}, DEFINITIONS, rules, seed_values={"cooling_flow": 15})
    assert r3["parameters"]["cooling_flow"] == 15, r3
    r3b = project_constraints({"has_cooling": 1, "cooling_flow": -1}, DEFINITIONS, rules)
    assert 0 <= r3b["parameters"]["cooling_flow"] <= 30, r3b

    print(json.dumps({"status": "PASS", "message": "条件约束投影：不适用折叠与激活恢复正确"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
