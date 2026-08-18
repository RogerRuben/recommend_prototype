# -*- coding: utf-8 -*-
"""Conditional-attribute template compiles to the two correct affine bounds."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_constraint import affine_bound, compile_conditional_constraint, expected_range  # noqa: E402


def _evaluate_bounds(rules, controller_value):
    """Return (lower_bound, upper_bound) implied by a compiled rule pair."""
    lower = upper = None
    for rule in rules:
        bound = affine_bound(rule, controller_value)
        if rule["operator"] == "gte":
            lower = bound
        elif rule["operator"] == "lte":
            upper = bound
    return lower, upper


def main():
    # Standard case: inactive=-1, active=[0,30].
    c = compile_conditional_constraint("has_cooling", 1, "cooling_flow", -1, 0, 30)
    assert len(c["rules"]) == 2
    lower, upper = _evaluate_bounds(c["rules"], 0)
    assert abs(lower - (-1)) < 1e-9 and abs(upper - (-1)) < 1e-9, (lower, upper)
    lower, upper = _evaluate_bounds(c["rules"], 1)
    assert abs(lower - 0) < 1e-9 and abs(upper - 30) < 1e-9, (lower, upper)
    assert expected_range(c["template_metadata"], 0) == (-1.0, -1.0)
    assert expected_range(c["template_metadata"], 1) == (0.0, 30.0)

    # General case: inactive=0, active=[5,20].
    c2 = compile_conditional_constraint("has_cooling", 1, "cooling_flow", 0, 5, 20)
    lower, upper = _evaluate_bounds(c2["rules"], 0)
    assert abs(lower - 0) < 1e-9 and abs(upper - 0) < 1e-9, (lower, upper)
    lower, upper = _evaluate_bounds(c2["rules"], 1)
    assert abs(lower - 5) < 1e-9 and abs(upper - 20) < 1e-9, (lower, upper)

    # Both rules share the same group and metadata.
    assert c["rules"][0]["constraint_group"] == c["rules"][1]["constraint_group"]
    meta = json.loads(c["rules"][0]["template_metadata_json"])
    assert meta["template"] == "conditional_numeric_applicability"
    assert meta["inactive_value"] == -1

    print(json.dumps({"status": "PASS", "message": "条件属性模板编译为正确affine上下界"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
