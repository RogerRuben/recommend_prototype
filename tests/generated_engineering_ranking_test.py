# -*- coding: utf-8 -*-
"""Generated candidates keep their engineering hard penalty when re-ranked."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.recommender import rank_agreements  # noqa: E402


def _gen(name, hard_penalty, conflicts, capability=110, price=9):
    return {
        "agreement_id": name, "agreement_name": name, "agreement_source": "live_generated",
        "is_generated": True, "model_evaluation_available": True,
        "capability_score": capability, "predicted_price_wan": price,
        "cost_effectiveness": capability / price, "feasibility_probability": 0.8,
        "physical_gate": {"passed": True}, "hard_risk_reasons": [],
        "params": {"attr_001": 1}, "tags": [],
        "conservative_capability_score": capability,
        "search_metrics": {"hard_penalty": hard_penalty},
        "engineering_conflicts": conflicts,
        "best_effort": bool(conflicts) or hard_penalty > 0,
    }


def main():
    safe = _gen("SAFE", 0.0, [])
    hard = _gen("HARD", 2.0, ["工程规则：存在严重耦合不匹配"])
    # Reverse input order to prove the ranking, not list order, decides.
    ranked = rank_agreements([hard, safe], {"max_price": 12, "min_capability": 100}, {}, definitions={}, tag_map={})
    ids = [i["agreement_id"] for i in ranked]
    assert ids == ["SAFE", "HARD"], ids

    by_id = {i["agreement_id"]: i for i in ranked}
    assert by_id["SAFE"]["strict_filter_satisfied"] is True
    assert by_id["HARD"]["strict_filter_satisfied"] is False
    assert by_id["HARD"]["fit_penalty"] > by_id["SAFE"]["fit_penalty"]

    print(json.dumps({"status": "PASS", "message": "生成方案的工程硬penalty在重排序后仍保留"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
