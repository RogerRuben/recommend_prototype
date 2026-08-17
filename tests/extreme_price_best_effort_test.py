# -*- coding: utf-8 -*-
"""Extreme price targets must not collapse the result set to zero.

A fixed mock model has a theoretical minimum price of ~11.2 万.  As ``max_price``
moves from 12 → 11 → 10 → 5 the strict-solution count may drop to zero, but the
generator must keep returning at least one Best-Effort / closest-exploration
candidate as long as the model can still evaluate records.  An empty result is
only legitimate when evaluation itself fails.
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
    {"agreement_id": "H-01", "params": {"attr_a": 5, "attr_b": 5}, "tags": []},
    {"agreement_id": "H-02", "params": {"attr_a": 6, "attr_b": 4}, "tags": []},
    {"agreement_id": "H-03", "params": {"attr_a": 4, "attr_b": 6}, "tags": []},
]


def _price(params):
    return 11.2 + 0.15 * float(params["attr_a"]) + 0.15 * float(params["attr_b"])


def mock_evaluate(params, base_params=None, target_protocol=None):
    price = _price(params)
    capability = 50.0 + 2.0 * float(params["attr_a"]) + 2.0 * float(params["attr_b"])
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


def run(max_price, count=6):
    gen = HistorySeededGenerator(_MockStore(), _MockRuntime(), mock_evaluate, mock_evaluate_batch)
    request = {
        "max_price": max_price,
        "selected_tags": [], "indicator_filters": [], "indicator_filter_mode": "all",
        "sort_by": "comprehensive", "count": count, "target_protocol": None,
    }
    return gen.generate(request, count=count, seed=7, budget=400, search_mode="fast")


def main():
    reports = {}
    for max_price in (12, 11, 10, 5):
        result = run(max_price)
        candidates = result.get("candidates", [])
        strict = [c for c in candidates if c.get("strict_filter_satisfied")]
        best_effort = [c for c in candidates if not c.get("strict_filter_satisfied")]
        reports[str(max_price)] = {
            "candidate_count": len(candidates),
            "strict": len(strict),
            "best_effort": len(best_effort),
            "evaluated_count": result.get("evaluated_count"),
            "usable_count": result.get("usable_count"),
            "fallback_used": bool(result.get("fallback_used")),
            "min_price": round(min((_price(c["params"]) for c in candidates), default=None) or 0, 3),
        }

    # 12 万 is reachable -> strict solution exists.
    assert reports["12"]["strict"] >= 1, reports
    # 11 / 10 / 5 are below the 11.2 万 floor -> no strict, but best-effort survives.
    for max_price in ("11", "10", "5"):
        assert reports[max_price]["strict"] == 0, reports
        assert reports[max_price]["candidate_count"] >= 1, "target %s 万 must not collapse to 0" % max_price
    # The closest exploration result is near the theoretical 11.2 万 floor.
    assert reports["5"]["min_price"] < 12.0, reports

    print(json.dumps({
        "status": "PASS",
        "message": "极端价格目标不产生空结果",
        "reports": reports,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
