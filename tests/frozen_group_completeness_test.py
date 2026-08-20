# -*- coding: utf-8 -*-
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/"app"/"static"/"app.js").read_text(encoding="utf-8")
start=s.index("function renderFrozenParams()")
end=s.index("function refreshFrozenSummary()")
segment=s[start:end]
assert 'model_role!=="price_only"' not in segment
assert "groups[g.group_name]=[]" in segment
assert "本身不参与自动调整" in segment and "frozen-item:not(:disabled)" in segment
print("PASS frozen groups include all business roles and non-adjustable visibility")
