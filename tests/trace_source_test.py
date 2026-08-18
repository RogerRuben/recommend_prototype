# -*- coding: utf-8 -*-
"""Generation trace changes carry a source and reason, distinguishing projection/lock/search."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import _change_reason_type, _change_source  # noqa: E402


def main():
    projection_repairs = [{"parameter": "cooling_flow", "type": "conditional_deactivation", "before": 15, "after": -1}]
    locked = {"env"}
    assert _change_source("cooling_flow", projection_repairs, locked) == "constraint_projection"
    assert _change_source("env", projection_repairs, locked) == "user_frozen"
    assert _change_source("power", projection_repairs, locked) == "search"
    assert _change_reason_type("cooling_flow", projection_repairs, locked) == "conditional_deactivation"
    assert _change_reason_type("env", projection_repairs, locked) == "user_locked"

    print(json.dumps({"status": "PASS", "message": "trace变更区分投影/冻结/搜索来源"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
