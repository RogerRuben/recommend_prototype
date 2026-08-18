# -*- coding: utf-8 -*-
"""Structural moves (conditional controller changes) are marked and excluded when locked/inactive."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_constraint import compile_conditional_constraint  # noqa: E402
from app.coupling_pairs import build_coupling_pairs  # noqa: E402


DEFINITIONS = {
    "has_cooling": {"parameter_id": "has_cooling", "label": "是否液冷", "auto_adjustable": 1},
    "cooling_flow": {"parameter_id": "cooling_flow", "label": "冷却液流量", "auto_adjustable": 1},
    "power": {"parameter_id": "power", "label": "功率", "auto_adjustable": 1},
}


def main():
    cond_rules = compile_conditional_constraint("has_cooling", 1, "cooling_flow", -1, 0, 30)["rules"]
    pairs = build_coupling_pairs(["has_cooling", "cooling_flow", "power"], set(), DEFINITIONS, conditional_rules=cond_rules)
    structural = [p for p in pairs if p["source"] == "conditional_relationship"]
    assert structural, pairs
    assert {structural[0]["a"], structural[0]["b"]} == {"has_cooling", "cooling_flow"}, structural

    # A locked subordinate must not form a conditional structural pair.
    locked_pairs = build_coupling_pairs(["has_cooling", "cooling_flow"], {"cooling_flow"}, DEFINITIONS, conditional_rules=cond_rules)
    assert not any(p["source"] == "conditional_relationship" for p in locked_pairs), locked_pairs

    print(json.dumps({"status": "PASS", "message": "条件控制器-从属联动标记为结构调整，锁定/不活跃不进入动作"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
