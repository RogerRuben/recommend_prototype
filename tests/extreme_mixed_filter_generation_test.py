# -*- coding: utf-8 -*-
"""Extreme mixed door-lock request: enum/boolean anchors must survive generation."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator, filters_to_anchors  # noqa: E402


PARAMETER_DEFINITIONS = {
    "attr_001": {
        "parameter_id": "attr_001", "label": "是否应急解锁", "value_type": "boolean",
        "search_type": "boolean", "min_value": -1, "max_value": 1,
        "model_value_mapping_json": '{"无":0,"有":1,"无该属性":-1}',
        "auto_adjustable": 1, "enabled": 1,
    },
    "attr_003": {
        "parameter_id": "attr_003", "label": "锁体材料", "value_type": "enum",
        "search_type": "unordered_enum", "min_value": 0, "max_value": 3,
        "allowed_values_json": '["不锈钢","钛合金","高强铝合金"]',
        "model_value_mapping_json": '{"不锈钢":1.0,"钛合金":2.0,"高强铝合金":0.0}',
        "auto_adjustable": 1, "enabled": 1,
    },
    "attr_006": {
        "parameter_id": "attr_006", "label": "重量", "value_type": "number",
        "search_type": "continuous", "min_value": 0, "max_value": 10,
        "decimal_places": 1, "auto_adjustable": 1, "enabled": 1,
    },
    "attr_other": {
        "parameter_id": "attr_other", "label": "其他可调项", "value_type": "number",
        "search_type": "continuous", "min_value": 0, "max_value": 10,
        "decimal_places": 1, "auto_adjustable": 1, "enabled": 1,
    },
}

SEEDS = [
    {"agreement_id": "D-01", "params": {"attr_001": 1.0, "attr_003": 2.0, "attr_006": 4.2, "attr_other": 5.0}, "tags": []},
    {"agreement_id": "D-02", "params": {"attr_001": 0.0, "attr_003": 0.0, "attr_006": 5.1, "attr_other": 3.0}, "tags": []},
]


def mock_evaluate(params, base_params=None, target_protocol=None):
    capability = 40.0 + 10.0 * (1 if float(params.get("attr_006", 5) or 5) <= 2.2 else 0.0)
    price = 12.0
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
    schema = {"product_code": "DOOR", "product_name": "门锁产品"}
    effectiveness = _MockEffectiveness()


class _MockStore(object):
    def parameter_map(self):
        return PARAMETER_DEFINITIONS

    def historical_agreements(self, target_protocol=None):
        return SEEDS

    def tag_map(self):
        return {"passive": {"tag_name": "被动", "weight": 1.0}}

    def tag_rule_branches(self, selected_tags, max_branches=24):
        return [{
            "rules": [{"parameter_id": "attr_003", "operator": "text_equals", "value1": "不锈钢"}],
            "tag_groups": {"passive": ["attr_003"]},
            "unresolved_tags": [],
        }]

    def coupling_rows(self):
        return []

    def constraint_rows(self):
        return []

    def derive_tags(self, params, evaluation=None, inherited_tags=None):
        return ["passive"] if float(params.get("attr_003", -1)) == 1.0 else []

    def tag_evidence(self, params, evaluation=None, inherited_tags=None):
        return {}

    def _positioning(self, tags):
        return "门锁技术方案"

    @staticmethod
    def _compare(left, operator, right):
        return False


def main():
    request = {
        "max_price": 12,
        "selected_tags": ["passive"],
        "indicator_filter_mode": "all",
        "indicator_filters": [
            {"parameter_id": "attr_001", "operator": "boolean_is", "value1": "无"},
            {"parameter_id": "attr_003", "operator": "text_equals", "value1": "不锈钢"},
            {"parameter_id": "attr_006", "operator": "lte", "value1": 2.2},
        ],
        "frozen_parameters": [],
        "sort_by": "comprehensive", "count": 4, "target_protocol": None,
    }

    # 1. The generator anchor compiler understands the door-lock enum/boolean.
    direct_bounds = filters_to_anchors(request["indicator_filters"], PARAMETER_DEFINITIONS, "all")
    assert direct_bounds["attr_003"]["allowed"] == [1.0], direct_bounds
    assert direct_bounds["attr_001"]["min"] == 0.0 and direct_bounds["attr_001"]["max"] == 0.0, direct_bounds
    assert direct_bounds["attr_006"]["max"] == 2.2, direct_bounds

    gen = HistorySeededGenerator(_MockStore(), _MockRuntime(), mock_evaluate, None)

    # 2. Tag branch must use the same compiler.
    branch_bounds, _branch_request, _info = gen._tag_branch_for_seed(request, 0)
    assert branch_bounds["attr_003"]["allowed"] == [1.0], branch_bounds

    # 3. The extreme request must not silently come back empty without diagnostics.
    result = gen.generate(request, count=4, seed=7, budget=300, search_mode="fast")
    if not result.get("candidates"):
        assert result.get("rejection_details") or result.get("stopping_reason"), "empty result must explain itself"
    else:
        for candidate in result["candidates"]:
            assert candidate["params"]["attr_003"] == 1.0, candidate["params"]
            assert candidate["params"]["attr_001"] == 0.0, candidate["params"]
            assert candidate["params"]["attr_006"] <= 2.2 + 1e-9, candidate["params"]
        assert result.get("candidates"), "expected at least best-effort candidates"

    print(json.dumps({"status": "PASS", "message": "极端门锁混合条件：枚举/布尔/重量锚定生效且不静默空结果"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
