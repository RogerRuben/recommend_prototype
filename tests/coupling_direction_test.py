# -*- coding: utf-8 -*-
"""Coupling pairs carry a real relation direction, not priority%2."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.coupling_pairs import build_coupling_pairs  # noqa: E402


def _defs(keys):
    return {key: {"parameter_id": key, "auto_adjustable": 1} for key in keys}


def main():
    definitions = _defs(["A", "B", "C"])

    datamaster = [{"parameter_a": "A", "parameter_b": "B", "coupling_type": "negative", "strength": 1.0}]
    pairs = build_coupling_pairs(["A", "B"], set(), definitions, datamaster_rows=datamaster)
    assert pairs[0]["relation_type"] == "opposite_direction" and pairs[0]["direction"] == "opposite", pairs[0]

    pairs2 = build_coupling_pairs(["A", "B"], set(), definitions,
                                  datamaster_rows=[{"parameter_a": "A", "parameter_b": "B", "coupling_type": "positive"}])
    assert pairs2[0]["direction"] == "same", pairs2[0]

    learned = [{"target": "B", "sources": [{"key": "C", "weight": -1.5}]}]
    pairs3 = build_coupling_pairs(["B", "C"], set(), definitions, learned_couplings=learned)
    assert pairs3[0]["direction"] == "opposite", pairs3[0]

    print(json.dumps({"status": "PASS", "message": "耦合对带真实方向（同向/反向），不再用priority奇偶"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
