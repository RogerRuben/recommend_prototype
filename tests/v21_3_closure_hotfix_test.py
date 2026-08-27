# -*- coding: utf-8 -*-
"""V21.3 closure hotfix regressions from independent remote review."""
from __future__ import print_function

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_constraint import compile_conditional_relationship_v2
from app.demand_branch import compile_conflict_core_branches
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
    assert [branch["demand_branch_id"] for branch in branches] == ["CONFLICT-01", "CONFLICT-02"], branches
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


def test_conflict_core_preserves_common_filters_and_combines_independent_groups():
    definitions = dict((key, {"label": key}) for key in "ABCDE")
    filters = [
        {"parameter_id": key, "operator": "eq", "value1": key.lower()}
        for key in "ABCDE"
    ]
    branches = compile_conflict_core_branches(
        filters, [{"A", "B"}, {"C", "D"}], definitions, max_branches=24
    )
    key_sets = [set(rule["parameter_id"] for rule in branch["explicit_filters"]) for branch in branches]
    assert key_sets == [
        {"A", "C", "E"}, {"A", "D", "E"}, {"B", "C", "E"}, {"B", "D", "E"},
    ], key_sets
    assert all("E" in keys for keys in key_sets)
    assert all(branch["assessment_filters"] == filters for branch in branches)


def test_large_conflict_core_keeps_maximal_sets_and_cap_prefers_least_relaxation():
    keys = ["K%02d" % index for index in range(13)]
    filters = [{"parameter_id": key, "operator": "eq", "value1": index}
               for index, key in enumerate(keys)]
    branches = compile_conflict_core_branches(filters, [set(keys)], max_branches=24)
    assert len(branches) == 13, branches
    assert all(len(branch["explicit_filters"]) == 12 for branch in branches), branches

    asymmetric = [
        {"parameter_id": "A", "operator": "eq", "value1": 1},
        {"parameter_id": "B", "operator": "eq", "value1": 1},
        {"parameter_id": "C", "operator": "eq", "value1": 1},
    ]
    least_relaxed = compile_conflict_core_branches(
        asymmetric, [{"A", "B"}, {"A", "C"}], max_branches=1
    )
    assert {rule["parameter_id"] for rule in least_relaxed[0]["explicit_filters"]} == {"B", "C"}, least_relaxed


def test_hard_feasible_domain_coupling_enters_conflict_core():
    definitions = {
        "a": {"parameter_id": "a", "label": "A", "value_type": "number", "search_type": "continuous",
              "min_value": 0, "max_value": 20, "default_value": 5, "enabled": 1, "auto_adjustable": 1},
        "b": {"parameter_id": "b", "label": "B", "value_type": "number", "search_type": "continuous",
              "min_value": 0, "max_value": 30, "default_value": 5, "enabled": 1, "auto_adjustable": 1},
        "c": {"parameter_id": "c", "label": "C", "value_type": "number", "search_type": "continuous",
              "min_value": 0, "max_value": 10, "default_value": 5, "enabled": 1, "auto_adjustable": 1},
    }

    class CouplingStore(_Store):
        def coupling_rows(self):
            return [{"coupling_id": "FD-1", "coupling_type": "feasible_domain", "severity": "error",
                     "parameter_a": "a", "parameter_b": "b", "multiplier": 2, "offset": 0,
                     "domain_operator": "lte", "message": "B不得高于2A"}]

    generator = HistorySeededGenerator(CouplingStore(definitions), _Runtime(), _evaluate, None)
    request = {"indicator_filter_mode": "all", "selected_tags": [], "indicator_filters": [
        {"parameter_id": "a", "operator": "lte", "value1": 3},
        {"parameter_id": "b", "operator": "gte", "value1": 10},
        {"parameter_id": "c", "operator": "lte", "value1": 5},
    ]}
    branches = generator._generation_branches(request, definitions)
    assert len(branches) == 2, branches
    assert all(any(rule["parameter_id"] == "c" for rule in branch["explicit_filters"]) for branch in branches)
    assert all(any(conflict["source"] == "feasible_domain_coupling" for conflict in branch["explicit_conflicts"])
               for branch in branches)


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

    eliminated = HistorySeededGenerator._branch_search_states(records, ["A", "B"], 1, branch_effort={
        "A": {"seed_attempts": 2, "round_opportunities": 1, "quality_eligible_centers": 5,
              "selected_beam_centers": 5},
        "B": {"seed_attempts": 2, "round_opportunities": 0, "quality_eligible_centers": 0,
              "selected_beam_centers": 0,
              "proposal_attempts": 0, "last_alive_round": 0},
    })
    assert eliminated["B"]["status"] == "exhausted_by_quality", eliminated


def test_quality_eligible_branches_rotate_when_branch_count_exceeds_beam_width():
    generator = HistorySeededGenerator(_Store({}), _Runtime(), _evaluate, None)
    records = []
    branch_ids = ["BRANCH-%02d" % index for index in range(1, 13)]
    for index, branch_id in enumerate(branch_ids):
        records.append({
            "demand_branch_id": branch_id,
            "family_id": branch_id + ":SEED",
            "params": {"x": index},
            "_search_key": (0.0, 0.01 + index * 0.001, 0.0, 0.0, 0.0, 0.0, 0.0),
            "strict_filter_satisfied": True,
        })
    effort = dict((branch_id, {
        "seed_attempts": 1, "round_opportunities": 0,
        "quality_eligible_centers": 0, "selected_beam_centers": 0,
        "beam_admissions": 0, "proposal_attempts": 0, "last_alive_round": None,
    }) for branch_id in branch_ids)

    first = generator._beam_select(records, {}, width=10, branch_effort=effort)
    generator._update_branch_beam_effort(first, records, branch_ids, effort, 0)
    first_ids = {item["demand_branch_id"] for item in first}
    waiting = set(branch_ids) - first_ids
    assert len(waiting) == 2, first_ids
    states = generator._branch_search_states(records, branch_ids, 0, branch_effort=effort)
    assert all(states[branch_id]["quality_eligible_centers"] > 0 for branch_id in waiting), states
    assert all(states[branch_id]["status"] == "waiting_for_capacity" for branch_id in waiting), states

    for branch_id in first_ids:
        effort[branch_id]["round_opportunities"] += 1
    second_pool = generator._beam_candidate_pool(first, records, branch_ids)
    second = generator._beam_select(second_pool, {}, width=10, branch_effort=effort)
    second_ids = {item["demand_branch_id"] for item in second}
    assert waiting.issubset(second_ids), (waiting, second_ids)
    generator._update_branch_beam_effort(second, records, branch_ids, effort, 1)
    assert all(effort[branch_id]["selected_beam_centers"] > 0 for branch_id in waiting), effort
    for branch_id in second_ids:
        effort[branch_id]["round_opportunities"] += 1
    assert all(effort[branch_id]["round_opportunities"] > 0 for branch_id in waiting), effort


def test_generate_stops_when_impossible_branch_is_eliminated_by_quality():
    sys.path.insert(0, str(ROOT / "tests"))
    from beam_multi_round_test import _MockRuntime, _MockStore, mock_evaluate

    class QualityEliminationGenerator(HistorySeededGenerator):
        def _record_from_params(self, params, base, request, *args, **kwargs):
            record = super(QualityEliminationGenerator, self)._record_from_params(
                params, base, request, *args, **kwargs
            )
            filters = request.get("indicator_filters") or []
            if filters and filters[0].get("parameter_id") == "attr_b":
                record["strict_filter_satisfied"] = False
                record["best_effort"] = True
                record["generation_level"] = "best_effort"
                record["_search_key"] = (0.0, 99.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            return record

        def _diverse_strict_count(self, records, definitions, historical=None, distance=0.018, required_branch_ids=None):
            strict_a = [item for item in records if item.get("strict_filter_satisfied")
                        and item.get("demand_branch_id") == "BRANCH-01"]
            return 5 if strict_a else 0

    generator = QualityEliminationGenerator(_MockStore(), _MockRuntime(), mock_evaluate, None)
    result = generator.generate({
        "selected_tags": [], "indicator_filter_mode": "any",
        "indicator_filters": [
            {"parameter_id": "attr_a", "operator": "lte", "value1": 2},
            {"parameter_id": "attr_b", "operator": "lte", "value1": 2},
        ],
        "sort_by": "comprehensive", "target_protocol": None, "generation_rounds": 7,
    }, count=5, seed=23, budget=120, search_mode="fast")
    assert result["branch_search_states"]["BRANCH-02"]["status"] == "exhausted_by_quality", result
    assert result["stopping_reason"] == "requested_count_met", result
    assert result["actual_rounds"] < result["max_rounds"], result


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

    mapped = [{
        "rank": 1, "strict_filter_satisfied": False,
        "requirement_assessment": {"conditions": [
            {"kind": "parameter", "parameter_id": "state", "key": "state", "label": "状态",
             "target": 1, "actual": -1, "gap": 1, "status": "unmatched"}
        ]},
    }]
    annotate_candidate_recommendations(mapped, {"scenario": "balanced"}, definitions={
        "state": {"value_type": "boolean", "display_value_mapping_json": '{"-1":"无该属性","1":"有"}'},
    })
    summary = mapped[0]["recommendation_reason"]["summary"]
    assert "当前值无该属性" in summary and "目标有" in summary and "-1" not in summary, summary


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
    test_conflict_core_preserves_common_filters_and_combines_independent_groups()
    test_large_conflict_core_keeps_maximal_sets_and_cap_prefers_least_relaxation()
    test_hard_feasible_domain_coupling_enters_conflict_core()
    test_impossible_branch_becomes_best_effort_only_after_minimum_effort()
    test_quality_eligible_branches_rotate_when_branch_count_exceeds_beam_width()
    test_generate_stops_when_impossible_branch_is_eliminated_by_quality()
    test_non_strict_reasons_are_candidate_specific()
    test_onboarding_clear_and_single_branch_direction_contracts()
    print("PASS V21.3 closure hotfix")
