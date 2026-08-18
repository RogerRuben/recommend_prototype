# -*- coding: utf-8 -*-
"""Fast beam must accumulate multi-attribute changes across rounds (A->A+B->A+B+C)."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator  # noqa: E402


PARAMETER_DEFINITIONS = {
    "attr_a": {"parameter_id": "attr_a", "label": "属性A", "value_type": "number",
               "search_type": "integer", "min_value": 0, "max_value": 10,
               "decimal_places": 0, "enabled": 1, "auto_adjustable": 1, "allowed_values_json": None},
    "attr_b": {"parameter_id": "attr_b", "label": "属性B", "value_type": "number",
               "search_type": "integer", "min_value": 0, "max_value": 10,
               "decimal_places": 0, "enabled": 1, "auto_adjustable": 1, "allowed_values_json": None},
    "attr_c": {"parameter_id": "attr_c", "label": "属性C", "value_type": "number",
               "search_type": "integer", "min_value": 0, "max_value": 10,
               "decimal_places": 0, "enabled": 1, "auto_adjustable": 1, "allowed_values_json": None},
}

SEEDS = [
    {"agreement_id": "H-01", "params": {"attr_a": 10, "attr_b": 10, "attr_c": 10}, "tags": []},
    {"agreement_id": "H-02", "params": {"attr_a": 10, "attr_b": 9, "attr_c": 10}, "tags": []},
]


def _capability(params):
    return 40.0 + 10.0 * (1 if float(params["attr_a"]) <= 8.0 else 0.0) \
        + 10.0 * (1 if float(params["attr_b"]) <= 8.0 else 0.0) \
        + 10.0 * (1 if float(params["attr_c"]) <= 8.0 else 0.0)


def mock_evaluate(params, base_params=None, target_protocol=None):
    capability = _capability(params)
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
        return []

    def derive_tags(self, params, evaluation=None, inherited_tags=None):
        return []

    def tag_evidence(self, params, evaluation=None, inherited_tags=None):
        return {}

    def _positioning(self, tags):
        return "通用技术方案"

    @staticmethod
    def _compare(left, operator, right):
        if operator == "gt":
            return left > right
        if operator == "gte":
            return left >= right
        if operator == "lt":
            return left < right
        if operator == "lte":
            return left <= right
        if operator == "eq":
            return abs(left - right) <= 1e-9
        return False


def main():
    gen = HistorySeededGenerator(_MockStore(), _MockRuntime(), mock_evaluate, mock_evaluate_batch)
    request = {"min_capability": 65, "selected_tags": [], "indicator_filters": [],
               "indicator_filter_mode": "all", "sort_by": "comprehensive",
               "count": 6, "target_protocol": None}
    result = gen.generate(request, count=6, seed=11, budget=360, search_mode="fast")
    candidates = result.get("candidates", [])
    assert candidates, "generator returned no candidates"

    best = max(candidates, key=lambda c: _capability(c["params"]))
    assert best["params"]["attr_a"] <= 8 and best["params"]["attr_b"] <= 8 and best["params"]["attr_c"] <= 8, \
        "fast beam must accumulate all three attributes, got %s" % best["params"]

    trace = best.get("generation_trace") or {}
    changed_from_origin = set(trace.get("changed_from_origin") or [])
    assert {"attr_a", "attr_b", "attr_c"} <= changed_from_origin, \
        "changed_from_origin must include all three attributes, got %s" % changed_from_origin

    # Trace must carry origin / parent / iteration / before / after.
    assert trace.get("origin_seed_id"), "trace missing origin_seed_id"
    assert trace.get("iteration", 0) >= 1, "trace missing iteration"
    assert "parameters_before_move" in trace, "trace missing parameters_before_move"
    assert "changed_from_parent" in trace, "trace missing changed_from_parent"

    print(json.dumps({
        "status": "PASS", "message": "Fast Beam 多轮累计 A->A+B->A+B+C",
        "best_params": best["params"], "best_iteration": trace.get("iteration"),
        "changed_from_origin": sorted(changed_from_origin),
        "search_iterations": result.get("search_iterations"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
