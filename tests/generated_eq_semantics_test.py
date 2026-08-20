# -*- coding: utf-8 -*-
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.anchor_feasibility import validate_anchor_integrity
from app.recommender import filter_match

definition = {"parameter_id": "xx", "value_type": "number", "decimal_places": 3}
rule = {"parameter_id": "xx", "operator": "eq", "value1": "1"}
for value in (1, 1.0, "1", "1.0"):
    assert filter_match({"xx": value}, rule, definition)
    assert not validate_anchor_integrity({"xx": value}, [rule], {"xx": definition})
print("PASS equality semantics are shared by recommendation and anchor invariant")
