# -*- coding: utf-8 -*-
"""Historical products must never be dropped by the model engineering gate.

A stored historical agreement is a real reference product.  Even when the
current effectiveness model reports ``physical_gate.passed = False`` (a mature
expert boundary, a severe coupling mismatch or a low feasibility probability),
the product must stay visible and only surface that risk as a warning.  Only
newly generated schemes are eliminated by the model gate.  User-specified
filters (price / capability / cost-effectiveness / feasibility) still apply to
both, and ``min_feasibility`` compares against the user's value directly —
never ``max(DEFAULT_FEASIBILITY_GATE, value)``.
"""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.recommender import agreement_matches, rank_agreements


def _item(agreement_id, source, feasibility, gate_passed, decision, hard=False, price=12.0):
    return {
        "agreement_id": agreement_id,
        "agreement_name": agreement_id,
        "agreement_source": source,
        "is_generated": source not in ("historical", "imported"),
        "historical_price_wan": price,
        "predicted_price_wan": price,
        "capability_score": 80.0,
        "conservative_capability_score": 78.0,
        "feasibility_probability": feasibility,
        "cost_effectiveness": 6.5,
        "physical_gate": {"passed": gate_passed, "decision": decision, "probability": feasibility},
        "hard_risk_reasons": ["违反硬规则"] if hard else [],
        "params": {"attr_001": 1, "attr_005": 8500, "attr_007": 54},
        "tags": [],
        "model_evaluation_available": True,
    }


def main():
    # Historical product with a failed mature-boundary gate is kept.
    hist = _item("HIST-003", "historical", 0.87, False, "reject_mature_expert_boundary")
    assert agreement_matches(hist, {}) is True, "历史成品不应被成熟专家边界淘汰"

    # Historical product with a hard violation is still kept (risk shown, not dropped).
    hist_hard = _item("HIST-004", "historical", 0.52, False, "reject_hard_violation", hard=True)
    assert agreement_matches(hist_hard, {}) is True, "历史成品不应被硬违规淘汰"

    # Generated scheme with a failed gate is dropped.
    gen = _item("GEN-1", "live_generated", 0.87, False, "reject_mature_expert_boundary")
    assert agreement_matches(gen, {}) is False, "生成方案仍应被工程门控淘汰"

    gen_hard = _item("GEN-2", "live_generated", 0.90, True, "pass", hard=True)
    assert agreement_matches(gen_hard, {}) is False, "带硬违规的生成方案仍应被淘汰"

    # min_feasibility compares against the user's value directly, no implicit 0.65 floor.
    low = _item("HIST-LOW", "historical", 0.5, False, "reject_low_feasibility_probability")
    assert agreement_matches(low, {"min_feasibility": 0.4}) is True, "用户设0.4时应保留0.5的历史成品"
    assert agreement_matches(low, {"min_feasibility": 0.8}) is False, "用户设0.8时应淘汰0.5的历史成品"

    # Service online + no filters: the historical count must not shrink because of model evaluation.
    items = [
        _item("A", "historical", 0.91, True, "pass"),
        _item("B", "historical", 0.82, False, "reject_mature_expert_boundary"),
        _item("C", "historical", 0.74, False, "reject_severe_coupling"),
        _item("D", "historical", 0.52, False, "reject_hard_violation", hard=True),
    ]
    ranked = rank_agreements(items, {}, {})
    assert len(ranked) == 4, "无筛选条件时4条历史成品应全部保留，实际 %d" % len(ranked)

    # Soft recommendation: user thresholds no longer delete historical products;
    # they are kept and the fully-satisfied ones rank first.
    ranked2 = rank_agreements(items, {"min_feasibility": 0.8}, {})
    assert len(ranked2) == 4, "min_feasibility=0.8 仍应保留4条历史成品（软匹配），实际 %d" % len(ranked2)
    assert set(item["agreement_id"] for item in ranked2[:2]) == {"A", "B"}, "完全满足的 A/B 应排在前面"

    print(json.dumps({"status": "PASS", "message": "历史成品不受模型工程门控淘汰，用户条件软匹配排序"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
