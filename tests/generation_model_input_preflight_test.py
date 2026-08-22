# -*- coding: utf-8 -*-
"""Generation preflight repairs unspecified model fields and never terminates search."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator  # noqa: E402


PARAMETER_DEFINITIONS = {
    "attr_004": {"parameter_id": "attr_004", "label": "锁舌长度", "value_type": "number",
                 "search_type": "continuous", "min_value": 0, "max_value": 10,
                 "decimal_places": 2, "enabled": 1, "auto_adjustable": 1},
    "attr_006": {"parameter_id": "attr_006", "label": "重量", "value_type": "number",
                 "search_type": "auto", "min_value": 4.2, "max_value": 6,
                 "allowed_values_json": "[4.2,4.5,5.0,5.5,6.0]",
                 "decimal_places": 1, "enabled": 1, "auto_adjustable": 1},
}


def mock_evaluate(params, base_params=None, target_protocol=None):
    capability = 50.0
    price = 10.0
    feasibility = 0.9
    return {
        "predicted_price_wan": price, "price_interval_wan": [price, price],
        "capability_score": capability, "conservative_capability_score": capability,
        "protocol_score_interval": [capability, capability],
        "support_at_80": None, "support_at_100": None, "score_uncertainty_width": 0.0,
        "feasibility_probability": feasibility,
        "physical_gate": {"passed": True, "decision": "pass", "probability": feasibility, "probability_threshold": 0.65},
        "cost_effectiveness": capability / max(price, 1e-9),
        "parameters": dict(params),
        "anomaly_assessment": {"status": "in_domain", "is_anomaly": False, "score": 0.0, "items": []},
        "rule_messages": [], "coupling_assessments": [], "hard_risk_reasons": [],
        "learned_boundary_violations": [], "risk_contributors": [], "requirement_assessment": {},
        "model_versions": {"effectiveness": "mock", "price": "mock"},
        "model_audit": {"effectiveness": {}, "price": {}},
    }


class _MockEffectiveness(object):
    couplings = []
    coupling_edges = []
    learned_boundaries = []


class _MockRuntime(object):
    schema = {"product_code": "SYNTH", "product_name": "合成产品"}
    effectiveness = _MockEffectiveness()

    def all_feature_specs(self):
        return [
            {"key": "attr_004", "label": "锁舌长度", "required": True, "missing_policy": "reject"},
            {"key": "attr_006", "label": "重量", "required": True, "missing_policy": "reject"},
        ]


class _MockStore(object):
    def __init__(self, seeds):
        self.seeds = seeds

    def parameter_map(self):
        return PARAMETER_DEFINITIONS

    def historical_agreements(self, target_protocol=None):
        return self.seeds

    def tag_map(self):
        return {}

    def tag_rule_branches(self, selected_tags, max_branches=24):
        return [{"rules": [], "tag_groups": {}, "unresolved_tags": []}]

    def coupling_rows(self):
        return []

    def constraint_rows(self):
        return []

    def runtime_parameters(self, params):
        return dict(params)

    def derive_tags(self, params, evaluation=None, inherited_tags=None):
        return []

    def tag_evidence(self, params, evaluation=None, inherited_tags=None):
        return {}

    def _positioning(self, tags):
        return "通用技术方案"

    @staticmethod
    def _compare(left, operator, right):
        return False


def main():
    # All seeds miss attr_004 -> preflight completes the unspecified field and
    # generation still spends budget. The explicit attr_006 anchor is untouched.
    bad_seeds = [
        {"agreement_id": "H-01", "params": {"attr_006": 4.2}, "tags": []},
        {"agreement_id": "H-02", "params": {"attr_006": 5.0}, "tags": []},
    ]
    gen_bad = HistorySeededGenerator(_MockStore(bad_seeds), _MockRuntime(), mock_evaluate, None)
    request = {"min_capability": 50, "frozen_parameters": [], "selected_tags": [],
               "indicator_filters": [{"parameter_id": "attr_006", "operator": "lte", "value1": 3}],
               "indicator_filter_mode": "all", "sort_by": "comprehensive", "count": 2, "target_protocol": None}
    result_bad = gen_bad.generate(request, count=2, seed=5, budget=100, search_mode="fast")
    assert result_bad["stopping_reason"] != "generation_input_preflight_failed", result_bad
    assert result_bad["actual_budget_used"] > 0, result_bad
    assert result_bad["preflight"]["eligible_seed_count"] == 1
    assert result_bad["preflight"]["seeds"][0]["completion_repairs"] == [
        {"parameter_id": "attr_004", "source": "reference_midpoint"}
    ]
    assert result_bad["final_selected_count"] >= 1, result_bad
    assert result_bad["actual_rounds"] > 0, result_bad
    assert all(item["params"]["attr_006"] <= 3 for item in result_bad["candidates"]), result_bad

    # Complete and repairable seeds both remain searchable.
    good_seeds = [
        {"agreement_id": "H-01", "params": {"attr_004": 5.0, "attr_006": 4.2}, "tags": []},
        {"agreement_id": "H-02", "params": {"attr_006": 5.0}, "tags": []},
    ]
    gen_good = HistorySeededGenerator(_MockStore(good_seeds), _MockRuntime(), mock_evaluate, None)
    result_good = gen_good.generate(request, count=1, seed=5, budget=100, search_mode="fast")
    assert result_good.get("preflight", {}).get("eligible_seed_count") == 2, result_good.get("preflight")
    assert result_good["actual_budget_used"] > 0, result_good

    # Total model rejection still returns parameter-only Exploratory results.
    def reject_all(*args, **kwargs):
        raise ValueError("model service rejected out-of-domain input")

    exploratory = HistorySeededGenerator(_MockStore(good_seeds), _MockRuntime(), reject_all, None).generate(
        request, count=1, seed=5, budget=20, search_mode="fast"
    )
    assert exploratory["actual_budget_used"] > 0, exploratory
    assert exploratory["final_selected_count"] >= 1, exploratory
    assert exploratory["exploratory_candidate_count"] >= 1, exploratory
    assert exploratory["candidates"][0]["generation_level"] == "exploratory", exploratory
    assert exploratory["candidates"][0]["model_evaluation_available"] is False, exploratory

    print(json.dumps({"status": "PASS", "message": "生成前模型输入预检可修复且不再终止搜索"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
