# -*- coding: utf-8 -*-
"""Display labels persist as strings and reject structured values."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.display_mapping import normalize_display_mapping  # noqa: E402

assert normalize_display_mapping({"0": 123, "1": 456}, [0, 1]) == {"0": "123", "1": "456"}
assert normalize_display_mapping({0: False, 1: True}, [0, 1]) == {"0": "False", "1": "True"}
for invalid in ({"0": None}, {"0": {"text": "无"}}, {"0": ["无"]}):
    try:
        normalize_display_mapping(invalid, [0, 1])
        raise AssertionError("structured/null label should fail")
    except ValueError:
        pass
print("PASS display mapping scalar normalization")
