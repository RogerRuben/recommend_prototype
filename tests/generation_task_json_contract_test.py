# -*- coding: utf-8 -*-
"""GenerationTaskManager public payload must be strict-JSON serializable."""
from __future__ import print_function

import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.generation_tasks import GenerationTaskManager  # noqa: E402
from app.local_generator import HistorySeededGenerator  # noqa: E402


PARAMETER_DEFINITIONS = {
    "weight": {"parameter_id": "weight", "label": "重量", "value_type": "number",
               "search_type": "continuous", "min_value": 4.2, "max_value": 10,
               "decimal_places": 1, "enabled": 1, "auto_adjustable": 1},
    "other": {"parameter_id": "other", "label": "其他", "value_type": "number",
              "search_type": "continuous", "min_value": 0, "max_value": 10,
              "decimal_places": 1, "enabled": 1, "auto_adjustable": 1},
}

SEEDS = [
    {"agreement_id": "H-01", "params": {"weight": 5.0, "other": 3.0}, "tags": []},
]


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


def _assert_no_nonfinite(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            _assert_no_nonfinite(value)
    elif isinstance(obj, list):
        for value in obj:
            _assert_no_nonfinite(value)
    elif isinstance(obj, float):
        assert math.isfinite(obj), obj


def main():
    gen = HistorySeededGenerator(_MockStore(), _MockRuntime(), mock_evaluate, None)
    request = {"selected_tags": [], "indicator_filters": [
        {"parameter_id": "weight", "operator": "lte", "value1": 3},
    ], "indicator_filter_mode": "all", "min_capability": 50, "count": 1, "target_protocol": None}
    result = gen.generate(request, count=1, seed=5, budget=100, search_mode="fast")
    task = {
        "task_id": "GENTASK-TEST", "status": "completed", "progress": 100,
        "message": "ok", "session_id": "s1", "created_at": time.time(), "updated_at": time.time(),
        "error": None, "fingerprint": "fp", "batch_id": "b1", "search_profile": {},
        "result": result,
    }
    mgr = GenerationTaskManager(None)
    payload = mgr.public(task)
    _assert_no_nonfinite(payload)
    json.dumps(payload, allow_nan=False)

    print(json.dumps({"status": "PASS", "message": "生成任务 public payload 严格 JSON 可序列化"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
