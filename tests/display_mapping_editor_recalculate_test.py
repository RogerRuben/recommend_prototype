# -*- coding: utf-8 -*-
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/"app"/"static"/"app.js").read_text(encoding="utf-8")
assert "function currentParams()" in s and "canonicalInputValue(parameter(el.dataset.key),el.value)" in s
assert "parameters:currentParams()" in s
assert "data-business-min" in s
assert "min_value)+'\" max=\"'" not in s
print("PASS editor recalculation sends canonical values without range blocking")
