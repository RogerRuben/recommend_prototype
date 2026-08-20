# -*- coding: utf-8 -*-
"""Numeric-looking allowed values never participate in str-float arithmetic."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator, _nearest_numeric_business_value  # noqa: E402

assert _nearest_numeric_business_value(["0", "1"], 0.8) == "1"
params = {"xx": 0.8}
definition = {"parameter_id": "xx", "value_type": "enum", "search_type": "ordered_discrete", "auto_adjustable": 1}
locked, conflicts = HistorySeededGenerator(object(), object(), None)._anchor_demands(
    params, {"xx": {"allowed": ["0", "1"]}}, {"xx": definition}
)
assert not conflicts
assert locked["xx"] == "1" and isinstance(locked["xx"], str), locked
print("PASS numeric string allowed anchor")
