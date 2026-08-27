# -*- coding: utf-8 -*-
"""V21.3 closure hotfix regressions from independent remote review."""
from __future__ import print_function

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_constraint import compile_conditional_relationship_v2
from app.local_generator import HistorySeededGenerator
from app.recommendation_explanation import annotate_candidate_recommendations


DEFINITIONS = {
    "state": {"parameter_id": "state", "label": "安装状态", "value_type": "number",
              "search_type": "continuous", "min_value": 0, "max_value": 5,
              "default_value": 2, "decimal_places": 0, "enabled": 1, "auto_adjustable": 1,
              "allowed_values_json": "[-1, 0, 1, 2, 3, 4, 5]",
              "display_value_mapping_json": '{"-1":"无该属性"}',
              "special_value_keys_json": '["-1"]'},
    "other": {"parameter_id": "other", "label": "其它参数", "value_type": "number",
              "search_type": "integer", "min_value": 0, "max_value": 10,
              "default_value": 5, "decimal_places": 0, "enabled": 1, "auto_adjustable": 1},
}


def _evaluate(params, base_params=None, target_protocol=None):
    capability = 70.0 + float(params.get("other", 0))
    return {
        "predicted_price_wan": 10.0, "price_interval_wan": [10.0, 10.0],
        "capability_score": capability, "conservative_capability_score": capability,
        "protocol_score_interval": [capability, capability], "support_at_80": None,
        "support_at_100": None, "score_uncertainty_width": 0.0,
        "feasibility_probability": 0.9,
        "physical_gate": {"passed": True, "decision": "pass", "probability": 0.9, "probability_threshold": 0.65},
        "cost_effectiveness": capability / 10.0, "parameters": dict(params),
        "anomaly_assessment": {"status": "in_domain", "is_anomaly": False, "score": 0.0, "items": []},
        "rule_messages": [], "coupling_assessments": [], "hard_risk_reasons": [],
        "learned_boundary_violations": [], "risk_contributors": [],
        "model_versions": {"effectiveness": "mock", "price": "mock"},
        "model_audit": {"effectiveness": {}, "price": {}},
    }


class _Effectiveness(object):
    couplings = []
    coupling_edges = []
    learned_boundaries = []


class _Runtime(object):
    schema = {"product_code": "SYNTH", "product_name": "合成产品"}
    effectiveness = _Effectiveness()


class _Store(object):
    def __init__(self, definitions=None, rules=None):
        self._definitions = definitions or DEFINITIONS
        self._rules = rules or []

    def parameter_map(self): return self._definitions
    def historical_agreements(self, target_protocol=None):
        return [
            {"agreement_id": "H-01", "params": {"state": 2, "other": 8}, "tags": []},
            {"agreement_id": "H-02", "params": {"state": 3, "other": 4}, "tags": []},
        ]
    def tag_map(self): return {}
    def tag_rule_branches(self, selected_tags, max_branches=24): return [{"rules": [], "tag_groups": {}, "unresolved_tags": []}]
    def coupling_rows(self): return []
    def constraint_rows(self): return self._rules
    def derive_tags(self, params, evaluation=None, inherited_tags=None): return []
    def tag_evidence(self, params, evaluation=None, inherited_tags=None): return {}
    def _positioning(self, tags): return "通用技术方案"
    @staticmethod
    def _compare(left, operator, right):
        return {"gte": left >= right, "gt": left > right, "lte": left <= right,
                "lt": left < right, "eq": abs(left - right) <= 1e-9}.get(operator, False)


def test_special_is_survives_final_strict_rerank():
    generator = HistorySeededGenerator(_Store(), _Runtime(), _evaluate, None)
    result = generator.generate({
        "selected_tags": [], "indicator_filter_mode": "all",
        "indicator_filters": [{"parameter_id": "state", "operator": "special_is", "value1": -1}],
        "sort_by": "comprehensive", "target_protocol": None,
    }, count=3, seed=17, budget=40, search_mode="fast")
    assert result["strict_candidate_count"] >= 3, result
    assert result["final_selected_count"] >= 2, result
    assert all(item["params"]["state"] == -1 for item in result["candidates"]), result["candidates"]


def test_cross_parameter_conditional_and_conflict_splits_directions():
    definitions = {
        "controller": {"parameter_id": "controller", "label": "结构方式", "value_type": "boolean",
                       "search_type": "boolean", "default_value": 1, "enabled": 1, "auto_adjustable": 1},
        "module": {"parameter_id": "module", "label": "模块能力", "value_type": "number",
                   "search_type": "continuous", "min_value": 0, "max_value": 10,
                   "default_value": 5, "enabled": 1, "auto_adjustable": 1},
    }
    rules = compile_conditional_relationship_v2(
        "controller", {"operator": "equals", "business_value": "无", "model_value": 0},
        "module", {"mode": "not_applicable", "business_value": "无该属性", "model_value": -1},
        {"mode": "range", "min": 0, "max": 10},
    )["rules"]
    generator = HistorySeededGenerator(_Store(definitions, rules), _Runtime(), _evaluate, None)
    request = {"indicator_filter_mode": "all", "indicator_filters": [
        {"parameter_id": "controller", "operator": "boolean_is", "value1": 0},
        {"parameter_id": "module", "operator": "gte", "value1": 5},
    ], "selected_tags": []}
    branches = generator._generation_branches(request, definitions)
    assert [branch["demand_branch_id"] for branch in branches] == ["BRANCH-01", "BRANCH-02"], branches
    assert all(branch["assessment_filters"] == request["indicator_filters"] for branch in branches)
    assert all(branch["explicit_conflicts"] for branch in branches)

    # A broad target request that accepts the inactive value is compatible and
    # must remain one ordinary AND branch.
    compatible = dict(request)
    compatible["indicator_filters"] = [
        request["indicator_filters"][0],
        {"parameter_id": "module", "operator": "lte", "value1": 5},
    ]
    compatible_branches = generator._generation_branches(compatible, definitions)
    assert [branch["demand_branch_id"] for branch in compatible_branches] == ["BRANCH-ALL"], compatible_branches


def test_cross_parameter_affine_hard_conflict_uses_interval_feasibility():
    definitions = {
        "left": {"parameter_id": "left", "label": "左值", "value_type": "number", "search_type": "continuous",
                 "min_value": 0, "max_value": 20, "default_value": 5, "enabled": 1, "auto_adjustable": 1},
        "right": {"parameter_id": "right", "label": "右值", "value_type": "number", "search_type": "continuous",
                  "min_value": 0, "max_value": 20, "default_value": 5, "enabled": 1, "auto_adjustable": 1},
    }
    hard_rule = {"rule_id": "HARD-1", "rule_kind": "affine", "severity": "error",
                 "left_parameter": "left", "operator": "gte", "right_parameter": "right",
                 "multiplier": 1, "offset": 0, "message": "左值不得低于右值"}
    generator = HistorySeededGenerator(_Store(definitions, [hard_rule]), _Runtime(), _evaluate, None)
    impossible = {"indicator_filter_mode": "all", "selected_tags": [], "indicator_filters": [
        {"parameter_id": "left", "operator": "lte", "value1": 3},
        {"parameter_id": "right", "operator": "gte", "value1": 8},
    ]}
    assert len(generator._generation_branches(impossible, definitions)) == 2
    feasible = {"indicator_filter_mode": "all", "selected_tags": [], "indicator_filters": [
        {"parameter_id": "left", "operator": "gte", "value1": 5},
        {"parameter_id": "right", "operator": "lte", "value1": 10},
    ]}
    assert len(generator._generation_branches(feasible, definitions)) == 1


def test_impossible_branch_becomes_best_effort_only_after_minimum_effort():
    records = []
    for index in range(5):
        records.append({"demand_branch_id": "A", "strict_filter_satisfied": True})
    records.extend([
        {"demand_branch_id": "B", "strict_filter_satisfied": False},
        {"demand_branch_id": "B", "strict_filter_satisfied": False},
    ])
    early = HistorySeededGenerator._branch_search_states(records, ["A", "B"], 1)
    settled = HistorySeededGenerator._branch_search_states(records, ["A", "B"], 2)
    assert early["B"]["status"] == "still_searching"
    assert settled["A"]["status"] == "strict_found"
    assert settled["B"]["status"] == "best_effort_only"


def test_non_strict_reasons_are_candidate_specific():
    items = [
        {"rank": 1, "strict_filter_satisfied": False, "predicted_price_wan": 9, "capability_score": 70,
         "requirement_assessment": {"matched_count": 1, "unmatched_count": 1, "total_count": 2,
                                    "conditions": [{"key": "weight", "label": "重量", "target": 3, "actual": 3.4, "gap": .4, "status": "unmatched"}]}},
        {"rank": 2, "strict_filter_satisfied": False, "predicted_price_wan": 11, "capability_score": 90,
         "solution_direction": {"branch_id": "BRANCH-02", "title": "优先满足锁定方式", "summary": "围绕锁定方式进行探索。"},
         "requirement_assessment": {"matched_count": 1, "unmatched_count": 1, "total_count": 2,
                                    "conditions": [{"key": "material", "label": "材料", "target": "A", "actual": "B", "gap": 1, "status": "unmatched"}]}},
        {"rank": 3, "strict_filter_satisfied": False, "model_evaluation_available": False, "is_generated": True,
         "requirement_assessment": {"conditions": []}},
    ]
    annotate_candidate_recommendations(items, {"scenario": "balanced"})
    codes = [item["recommendation_reason"]["code"] for item in items]
    assert len(set(codes)) == len(items), codes
    assert items[0]["recommendation_reason"]["code"].startswith("closest_")
    assert items[1]["recommendation_reason"]["code"] == "direction_BRANCH-02"
    assert items[2]["recommendation_reason"]["code"] == "exploration_rank_3"


def test_onboarding_clear_and_single_branch_direction_contracts():
    source = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    clear_handler = next(line for line in source.splitlines() if 'q("clearLiveBtn").onclick' in line)
    assert "state.hasRecommended&&!state.recommendationDirty" in clear_handler
    assert "renderRecommendationOnboarding()" in clear_handler
    assert 'id="clearLiveBtn" class="link-button full hidden"' in html
    generator_source = (ROOT / "app" / "local_generator.py").read_text(encoding="utf-8")
    assert 'show_solution_direction = len(active_demand_branch_ids) > 1' in generator_source
    assert 'for branch in generation_branches:' in generator_source
    assert 'self._attach_lineage(emergency, emergency_base, emergency_branch_info)' in generator_source


if __name__ == "__main__":
    test_special_is_survives_final_strict_rerank()
    test_cross_parameter_conditional_and_conflict_splits_directions()
    test_cross_parameter_affine_hard_conflict_uses_interval_feasibility()
    test_impossible_branch_becomes_best_effort_only_after_minimum_effort()
    test_non_strict_reasons_are_candidate_specific()
    test_onboarding_clear_and_single_branch_direction_contracts()
    print("PASS V21.3 closure hotfix")
