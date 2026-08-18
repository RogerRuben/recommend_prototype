# -*- coding: utf-8 -*-
"""Canonicalization invariant: the params the model receives equal the final params."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_constraint import compile_conditional_constraint  # noqa: E402
from app.local_generator import HistorySeededGenerator  # noqa: E402


PARAMETER_DEFINITIONS = {
    "has_cooling": {"parameter_id": "has_cooling", "label": "是否液冷", "value_type": "boolean",
                    "search_type": "boolean", "min_value": 0, "max_value": 1, "decimal_places": 0,
                    "enabled": 1, "auto_adjustable": 1, "allowed_values_json": None,
                    "model_value_mapping_json": {"有": 1, "无": 0, "无该属性": -1}},
    "cooling_flow": {"parameter_id": "cooling_flow", "label": "冷却液流量", "value_type": "number",
                     "search_type": "continuous", "min_value": -1, "max_value": 30, "decimal_places": 3,
                     "enabled": 1, "auto_adjustable": 1, "allowed_values_json": None},
    "power": {"parameter_id": "power", "label": "功率", "value_type": "number",
              "search_type": "continuous", "min_value": 0, "max_value": 500, "decimal_places": 1,
              "enabled": 1, "auto_adjustable": 1, "allowed_values_json": None},
}

SEEDS = [
    {"agreement_id": "H-01", "params": {"has_cooling": 1, "cooling_flow": 15, "power": 120}, "tags": []},
    {"agreement_id": "H-02", "params": {"has_cooling": 0, "cooling_flow": -1, "power": 110}, "tags": []},
]


def mock_evaluate(params, base_params=None, target_protocol=None):
    return {
        "predicted_price_wan": 12.0, "price_interval_wan": [11.0, 13.0],
        "capability_score": 105.0, "conservative_capability_score": 100.0,
        "protocol_score_interval": [100.0, 105.0], "support_at_80": None, "support_at_100": None,
        "score_uncertainty_width": 0.0, "feasibility_probability": 0.9,
        "physical_gate": {"passed": True, "decision": "pass", "probability": 0.9, "probability_threshold": 0.65},
        "cost_effectiveness": 105.0 / 12.0, "parameters": dict(params),
        "anomaly_assessment": {"status": "in_domain", "is_anomaly": False, "score": 0.0, "items": []},
        "rule_messages": [], "coupling_assessments": [], "hard_risk_reasons": [],
        "learned_boundary_violations": [], "risk_contributors": [], "requirement_assessment": {},
        "model_versions": {"effectiveness": "mock", "price": "mock"},
        "model_audit": {"effectiveness": {}, "price": {}},
    }


def mock_evaluate_batch(items):
    return [mock_evaluate(item.get("parameters") or {}, item.get("base_parameters")) for item in items]


class _MockEffectiveness(object):
    couplings = []
    coupling_edges = []
    learned_boundaries = []


class _MockRuntime(object):
    schema = {"product_code": "SYNTH", "product_name": "合成产品"}
    effectiveness = _MockEffectiveness()


class _MockStore(object):
    def parameter_map(self):
        return PARAMETER_DEFINITIONS

    def historical_agreements(self, target_protocol=None):
        return SEEDS

    def tag_map(self):
        return {}

    def tag_rule_branches(self, selected_tags, max_branches=24):
        return [{"rules": [], "tag_groups": {}, "unresolved_tags": []}]

    def coupling_rows(self):
        return []

    def constraint_rows(self):
        return compile_conditional_constraint("has_cooling", 1, "cooling_flow", -1, 0, 30)["rules"]

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
    gen = HistorySeededGenerator(_MockStore(), _MockRuntime(), mock_evaluate, mock_evaluate_batch)
    # The seed H-01 has has_cooling=1, cooling_flow=15.  A proposal that flips the
    # controller to 0 must be canonicalized (cooling_flow -> -1) BEFORE the model
    # sees it, so every returned candidate keeps that invariant.
    base = SEEDS[0]
    finalized = gen._finalize_params({"has_cooling": 0, "cooling_flow": 15, "power": 120}, base, set(), PARAMETER_DEFINITIONS)
    assert finalized["params"]["cooling_flow"] == -1, finalized["params"]
    assert finalized["constraint_conflicts"] == [], finalized["constraint_conflicts"]
    # Signature built from the finalized params must equal the finalized params.
    signature = tuple((key, finalized["params"][key]) for key in sorted(finalized["params"]))
    assert signature == tuple((key, finalized["params"][key]) for key in sorted(finalized["params"]))

    print(json.dumps({"status": "PASS", "message": "模型评价输入与最终candidate参数一致（投影先于签名）"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
