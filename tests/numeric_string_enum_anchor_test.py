# -*- coding: utf-8 -*-
"""Explicit numeric-looking enum anchors keep their canonical business type."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator, filters_to_anchors  # noqa: E402

definition = {"parameter_id": "level", "value_type": "enum", "search_type": "ordered_discrete",
              "allowed_values_json": '["1","2","3"]', "auto_adjustable": 1}
bounds = filters_to_anchors(
    [{"parameter_id": "level", "operator": "text_equals", "value1": "1"}],
    {"level": definition},
)
params = {"level": 2.4}
generator = HistorySeededGenerator(object(), object(), None)
locked, conflicts = generator._anchor_demands(params, bounds, {"level": definition})
assert not conflicts and locked["level"] == "1" and isinstance(locked["level"], str), locked
generator._round_values(params, {"level": definition}, locked)
assert params["level"] == "1" and isinstance(params["level"], str), params
print("PASS numeric string enum anchor")
