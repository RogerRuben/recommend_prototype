# -*- coding: utf-8 -*-
"""End-to-end replay: real generator output's generation_path must reproduce final params."""
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
    "env": {"parameter_id": "env", "label": "环境温度", "value_type": "number",
            "search_type": "integer", "min_value": -60, "max_value": 60,
            "decimal_places": 0, "enabled": 1, "auto_adjustable": 1, "allowed_values_json": None},
}

SEEDS = [
    {"agreement_id": "H-01", "params": {"attr_a": 10, "attr_b": 5, "env": 40}, "tags": []},
    {"agreement_id": "H-02", "params": {"attr_a": 9, "attr_b": 4, "env": 35}, "tags": []},
]


def mock_evaluate(params, base_params=None, target_protocol=None):
    capability = 40.0 + 10.0 * (1 if float(params["attr_a"]) <= 8.0 else 0.0)
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
        return False


def _seed_params(seed_id):
    for seed in SEEDS:
        if seed["agreement_id"] == seed_id:
            return dict(seed["params"])
    raise AssertionError("unknown seed %s" % seed_id)


def main():
    gen = HistorySeededGenerator(_MockStore(), _MockRuntime(), mock_evaluate, None)
    request = {"min_capability": 50, "frozen_parameters": [], "selected_tags": [],
               "indicator_filters": [], "indicator_filter_mode": "all",
               "sort_by": "comprehensive", "count": 2, "target_protocol": None}
    result = gen.generate(request, count=2, seed=5, budget=300, search_mode="fast")
    candidates = result.get("candidates") or []
    assert candidates, "expected generated candidates for replay"

    replayed_any = False
    for candidate in candidates:
        trace = candidate.get("generation_trace") or {}
        path = trace.get("generation_path") or []
        seed_id = trace.get("seed_agreement_id")
        assert seed_id, "candidate missing seed_agreement_id"
        assert path, "candidate missing generation_path"
        params = _seed_params(seed_id)
        for node in path:
            for change in (node.get("move") or {}).get("changes") or []:
                params[change["parameter_id"]] = change["after"]
        assert params == candidate["params"], "replay mismatch for %s: %s != %s" % (candidate["agreement_id"], params, candidate["params"])
        replayed_any = True
    assert replayed_any

    print(json.dumps({"status": "PASS", "message": "真实生成路径可回放并精确到达最终参数"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
