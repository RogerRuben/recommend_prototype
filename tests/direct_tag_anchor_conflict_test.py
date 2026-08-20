# -*- coding: utf-8 -*-
"""A direct user condition wins over a contradictory tag suggestion."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator, merge_bounds  # noqa: E402


class Store(object):
    def parameter_map(self):
        return {}


bounds = merge_bounds({"weight": {"min": 6}}, {"weight": {"max": 4}})
rule = bounds["weight"]
assert rule["max"] == 4 and "min" not in rule, rule
assert rule["direct_user_wins"] is True and rule["conflict_reason"] == "tag_direct_conflict", rule
params = {"weight": 8}
locked, conflicts = HistorySeededGenerator(Store(), object(), None)._anchor_demands(
    params, bounds, {"weight": {"parameter_id": "weight", "search_type": "continuous", "auto_adjustable": 1}}
)
assert locked["weight"] == 4 and locked["weight"] != 5, (locked, conflicts)
print("PASS direct user anchor wins over tag")
