# -*- coding: utf-8 -*-
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/"app"/"static"/"app.js").read_text(encoding="utf-8")
assert "esc(optionValue(def,s.value))" in s
assert "value1:v1?canonicalInputValue(d,v1.value):null" in s
assert "value1:v1?v1.value:null" not in s
print("PASS filter options separate canonical value from display label")
