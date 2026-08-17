# -*- coding: utf-8 -*-
"""Adaptive Beam Search must accumulate multi-round, multi-attribute changes.

The mock objective only improves materially when *both* attributes drop to the
band, and the single-attribute neighbourhood can only move one attribute per
step (integer attributes with a tiny fitted std make the two-variable moves
round back to no change).  The best candidate must therefore differ from the
seed in both attributes, reached across multiple rounds, and its trajectory must
record the parent it was built from.
"""
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
}

SEEDS = [
    {"agreement_id": "H-01", "params": {"attr_a": 10, "attr_b": 10}, "tags": []},
    {"agreement_id": "H-02", "params": {"attr_a": 10, "attr_b": 9}, "tags": []},
]


def _capability(params):
    a = float(params["attr_a"])
    b = float(params["attr_b"])
    return 40.0 + (10.0 if a <= 8.0 else 0.0) + (10.0 if b <= 8.0 else 0.0)


def mock_evaluate(params, base_params=None, target_protocol=None):
    capability = _capability(params)
    price = 10.0
    feasibility = 0.9
    return {
        "predicted_price_wan": price,
        "price_interval_wan": [price, price],
        "capability_score": capability,
        "conservative_capability_score": capability,
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


def run(count=6, budget=500):
    gen = HistorySeededGenerator(_MockStore(), _MockRuntime(), mock_evaluate, mock_evaluate_batch)
    # min_capability=55 is only reachable when BOTH attributes drop to the band,
    # so "strict" is meaningful and the search cannot stop after one round.
    request = {"min_capability": 55, "selected_tags": [], "indicator_filters": [],
               "indicator_filter_mode": "all", "sort_by": "comprehensive",
               "count": count, "target_protocol": None}
    return gen.generate(request, count=count, seed=11, budget=budget, search_mode="fast")


def main():
    result = run()
    candidates = result.get("candidates", [])
    assert candidates, "generator returned no candidates"
    best = max(candidates, key=lambda c: _capability(c["params"]))
    trace = best.get("generation_trace") or {}

    a, b = float(best["params"]["attr_a"]), float(best["params"]["attr_b"])
    assert a <= 8.0 and b <= 8.0, "best candidate must reduce both attributes, got %s" % best["params"]

    changed_from_origin = set(trace.get("changed_from_origin") or [])
    assert "attr_a" in changed_from_origin and "attr_b" in changed_from_origin, (
        "best candidate must show both attributes in changed_from_origin, got %s" % trace)

    # Cumulative trajectory: a candidate built on a parent (not the seed) in a
    # later round must record a non-empty changed_from_parent and a parent that
    # already differs from the seed.
    accumulated = [c for c in candidates if (c.get("generation_trace") or {}).get("changed_from_parent")]
    assert accumulated, "no candidate records a parent→child move"
    parent_before = accumulated[0]["generation_trace"].get("parameters_before_move") or {}
    assert (parent_before.get("attr_a") != 10) or (parent_before.get("attr_b") != 10), (
        "accumulated candidate's parent must already differ from the seed, got %s" % parent_before)

    print(json.dumps({
        "status": "PASS",
        "message": "Beam 支持多轮累计多属性修改，并记录父子轨迹",
        "best_params": best["params"],
        "best_capability": _capability(best["params"]),
        "best_iteration": trace.get("iteration"),
        "best_changed_from_origin": sorted(changed_from_origin),
        "search_iterations": result.get("search_iterations"),
        "candidate_count": len(candidates),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
