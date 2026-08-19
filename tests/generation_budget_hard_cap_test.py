# -*- coding: utf-8 -*-
"""Candidate evaluation budget is a strict hard cap and limits are canonicalized."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.generation_tasks import GenerationTaskManager  # noqa: E402
from app.local_generator import HistorySeededGenerator  # noqa: E402


PARAMETER_DEFINITIONS = {
    "attr_a": {"parameter_id": "attr_a", "label": "属性A", "value_type": "number",
               "search_type": "integer", "min_value": 0, "max_value": 10,
               "decimal_places": 0, "enabled": 1, "auto_adjustable": 1, "allowed_values_json": None},
    "env": {"parameter_id": "env", "label": "环境温度", "value_type": "number",
            "search_type": "integer", "min_value": -60, "max_value": 60,
            "decimal_places": 0, "enabled": 1, "auto_adjustable": 1, "allowed_values_json": None},
}

SEEDS = [
    {"agreement_id": "H-01", "params": {"attr_a": 10, "env": 40}, "tags": []},
    {"agreement_id": "H-02", "params": {"attr_a": 9, "env": 35}, "tags": []},
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


class _TaskRuntime(object):
    schema = {"product_code": "P1"}

    def manifest(self):
        return {"model_versions": {"effectiveness": "e1", "price": "p1"}}


class _TaskStore(object):
    def master_data_version(self):
        return "v1"


class _TaskSessions(object):
    def add_batch(self, session_id, items, fingerprint=None):
        return "BATCH", items


class _TaskApp(object):
    def __init__(self):
        self.runtime = _TaskRuntime()
        self.store = _TaskStore()
        self.sessions = _TaskSessions()
        self.calls = 0

    def _generate_sync(self, request, progress_callback=None):
        self.calls += 1
        return {"candidates": [{"agreement_id": "G1", "params": {}}], "count": 1, "message": "ok"}

    def generation_budget_limit(self):
        return 300

    def generation_rounds_limit(self):
        return 15


def main():
    # Local generator: budget is a hard cap even when count would previously inflate it.
    gen = HistorySeededGenerator(_MockStore(), _MockRuntime(), mock_evaluate, None)
    request = {"min_capability": 50, "frozen_parameters": [], "selected_tags": [],
               "indicator_filters": [], "indicator_filter_mode": "all",
               "sort_by": "comprehensive", "count": 30, "target_protocol": None}
    result = gen.generate(request, count=30, seed=5, budget=60, search_mode="fast")
    assert result["generation_budget"] == 60, result["generation_budget"]
    assert result["actual_budget_used"] <= 60, result["actual_budget_used"]

    tiny = gen.generate(request, count=10, seed=5, budget=1, search_mode="fast")
    assert tiny["generation_budget"] == 1, tiny["generation_budget"]
    assert tiny["actual_budget_used"] <= 1, tiny["actual_budget_used"]

    # Task manager canonicalizes raw rounds before fingerprinting.
    app = _TaskApp()
    mgr = GenerationTaskManager(app)
    base = {"session_id": "s1", "selected_tags": [], "max_price": None,
            "indicator_filters": [], "indicator_filter_mode": "all", "count": 5,
            "target_protocol": None, "generation_budget": 50}
    first = mgr.start(dict(base, generation_rounds=100))
    second = mgr.start(dict(base, generation_rounds=1000))
    assert first["task_id"] == second["task_id"], "clamped rounds must produce the same fingerprint"
    stored = mgr.tasks[first["task_id"]]["request"]
    assert stored["generation_rounds"] == 15, stored["generation_rounds"]
    assert stored["generation_budget"] == 50, stored["generation_budget"]

    print(json.dumps({"status": "PASS", "message": "生成预算为硬上限，rounds/budget 在指纹前规范化"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
