# -*- coding: utf-8 -*-
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.range_diagnostics import build_range_diagnostics

d = build_range_diagnostics({"x": 3}, {"x": {"label": "重量", "unit": "kg", "min_value": 4.2, "max_value": 10}}, [
    {"key": "x", "model_kind": "price", "min": 2, "max": 12},
    {"key": "x", "model_kind": "effectiveness", "min": 4, "max": 11, "training_min": 4.5, "training_max": 9},
], {"x": 3})[0]
assert d["parameter_id"] == "x" and d["label"] == "重量" and d["actual"] == 3
assert d["business_reference"]["source"] == "data_master"
assert d["model_contracts"]["price"]["source"] == "price_schema"
assert d["model_contracts"]["effectiveness"]["source"] == "effectiveness_schema"
assert d["training_ranges"]["effectiveness"]["source"] == "effectiveness_training"
print("PASS range diagnostics retain parameter and source")
