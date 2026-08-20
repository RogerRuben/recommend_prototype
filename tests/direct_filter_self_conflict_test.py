# -*- coding: utf-8 -*-
"""Contradictory direct filters remain structured and never become a midpoint."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.anchor_feasibility import assess_explicit_filter_feasibility  # noqa: E402
from app.local_generator import filters_to_anchors, merge_bounds  # noqa: E402

rules = [
    {"parameter_id": "weight", "operator": "gte", "value1": 6},
    {"parameter_id": "weight", "operator": "lte", "value1": 4},
]
definitions = {"weight": {"parameter_id": "weight", "label": "重量", "min_value": 0, "max_value": 10}}
merged = merge_bounds({}, filters_to_anchors(rules, definitions))
assert merged["weight"]["min"] == 6 and merged["weight"]["max"] == 4, merged
assert not (merged["weight"]["min"] == merged["weight"]["max"] == 5), merged
assert merged["weight"]["conflict_reason"] == "explicit_filters_mutually_inconsistent"
feasibility = assess_explicit_filter_feasibility(rules, definitions)
assert feasibility["strictly_feasible"] is False
assert feasibility["blocking_conflicts"][0]["reason"] == "explicit_filters_mutually_inconsistent"
print("PASS direct filter self conflict")
