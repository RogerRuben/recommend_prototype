# -*- coding: utf-8 -*-
"""Coupling pair pool prioritises DataMaster couplings over adjacent exploration."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_constraint import compile_conditional_constraint  # noqa: E402
from app.coupling_pairs import build_coupling_pairs, exploration_pairs  # noqa: E402


def _defs(keys):
    return {key: {"parameter_id": key, "auto_adjustable": 1} for key in keys}


def main():
    keys = ["A", "B", "C", "D", "has_cooling", "cooling_flow"]
    definitions = _defs(keys)

    # DataMaster A-D coupling must beat the adjacent A-B/B-C/C-D ordering.
    datamaster = [{"parameter_a": "A", "parameter_b": "D", "strength": 1.0}]
    learned = [{"target": "B", "sources": [{"key": "C", "weight": 2.0}]}]
    pairs = build_coupling_pairs(["A", "B", "C", "D"], set(), definitions,
                                 datamaster_rows=datamaster, learned_couplings=learned)
    assert pairs[0]["source"] == "datamaster_coupling" and {pairs[0]["a"], pairs[0]["b"]} == {"A", "D"}, pairs
    assert pairs[1]["source"] == "learned_coupling" and {pairs[1]["a"], pairs[1]["b"]} == {"B", "C"}, pairs

    # Exploration pairs are the lowest priority fallback.
    exp = exploration_pairs(["A", "B", "C", "D"], set(), definitions, limit=3)
    assert exp and exp[0]["priority"] == 4 and exp[0]["source"] == "exploration"

    # Conditional controller<->subordinate is priority 3.
    cond_rules = compile_conditional_constraint("has_cooling", 1, "cooling_flow", -1, 0, 30)["rules"]
    cond_pairs = build_coupling_pairs(["has_cooling", "cooling_flow"], set(), definitions, conditional_rules=cond_rules)
    assert cond_pairs and cond_pairs[0]["source"] == "conditional_relationship" and cond_pairs[0]["priority"] == 3, cond_pairs

    print(json.dumps({"status": "PASS", "message": "耦合对按DataMaster>学习>条件关系>探索排序"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
