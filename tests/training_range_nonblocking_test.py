# -*- coding: utf-8 -*-
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.range_diagnostics import build_range_diagnostics

items = build_range_diagnostics({"xx": 1}, {}, [
    {"key": "xx", "model_kind": "effectiveness", "min": 0, "max": 5, "training_min": 2, "training_max": 4}
], {"xx": 1})
assert items[0]["model_contracts"]["effectiveness"]["inside"] is True
assert items[0]["training_ranges"]["effectiveness"]["inside"] is False
print("PASS training range is separate advisory metadata")
