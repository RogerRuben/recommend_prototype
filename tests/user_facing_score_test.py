# -*- coding: utf-8 -*-
"""min_capability uses the center capability_score, not the P10 estimate."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.recommender import agreement_matches, rank_agreements  # noqa: E402


def _item(name, capability, p10, price):
    return {
        "agreement_id": name, "agreement_name": name, "agreement_source": "historical",
        "is_generated": False, "model_evaluation_available": True,
        "capability_score": capability, "conservative_capability_score": p10,
        "predicted_price_wan": price, "cost_effectiveness": capability / price,
        "feasibility_probability": 0.8, "physical_gate": {"passed": True},
        "hard_risk_reasons": [], "params": {"attr_001": 1}, "tags": [],
    }


def main():
    a = _item("A", capability=105, p10=80, price=11.5)
    b = _item("B", capability=100, p10=95, price=13.0)

    request = {"min_capability": 103}
    # A's center capability (105) satisfies, B's center capability (100) does not.
    assert agreement_matches(a, request) is True, "A (center 105) must satisfy min_capability=103"
    assert agreement_matches(b, request) is False, "B (center 100) must not satisfy min_capability=103"

    # Ranking must also use the center capability for the capability sort key.
    ranked = rank_agreements([a, b], {"sort_by": "capability", "sort_order": "desc"}, {})
    assert ranked[0]["agreement_id"] == "A", "A (center 105) should rank above B (center 100)"

    print(json.dumps({"status": "PASS", "message": "用户效能筛选与排序统一为中心效能"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
