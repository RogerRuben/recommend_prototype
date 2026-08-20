# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
assert 'type="number" step="1" min="' not in source
assert 'type="number" step="1"'+" min=" not in source
assert "data-business-min" in source and "data-business-max" in source
print("PASS reference ranges do not become browser validation")
