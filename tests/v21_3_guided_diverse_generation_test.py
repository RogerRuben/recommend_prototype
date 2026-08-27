# -*- coding: utf-8 -*-
"""V21.3 guided recommendation and lineage-aware diversity regressions."""
from __future__ import print_function

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.demand_branch import compile_explicit_demand_branches, combine_generation_branches
from app.local_generator import HistorySeededGenerator
from app.recommendation_explanation import annotate_candidate_recommendations


def test_initial_ui_requires_explicit_recommendation():
    source = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    init_line = next(line for line in source.splitlines() if line.strip().startswith("async function init()"))
    assert "recommend(false)" not in init_line
    assert "hasRecommended:false" in source and "recommendationDirty:false" in source
    assert "推荐工作流程" not in html
    assert 'id="demandSummary"' in html and 'id="recommendBtn"' in html
    assert "先告诉我们您更关注什么" in html
    tour = source[source.index("function playTour(){"):source.index("function playDetailTour(){")]
    assert tour.count("title:") == 3
    scenario_handler = next(line for line in source.splitlines() if line.strip().startswith("function applyScenarioPolicy("))
    protocol_handler = next(line for line in source.splitlines() if 'q("targetProtocol").onchange' in line)
    assert "recommend(false)" not in scenario_handler
    assert "recommend(false)" not in protocol_handler


def test_candidate_reasons_are_relative_and_distinct():
    items = [
        {"predicted_price_wan": 10, "capability_score": 80, "cost_effectiveness": 8,
         "technical_match_score": 82, "tag_match_score": 90, "strict_filter_satisfied": True},
        {"predicted_price_wan": 12, "capability_score": 100, "cost_effectiveness": 8.333,
         "technical_match_score": 88, "tag_match_score": 88, "strict_filter_satisfied": True},
        {"predicted_price_wan": 10.5, "capability_score": 95, "cost_effectiveness": 9.048,
         "technical_match_score": 100, "tag_match_score": 100, "strict_filter_satisfied": True},
    ]
    annotate_candidate_recommendations(items, {"scenario": "balanced"})
    assert items[0]["price_rank"] == 1
    assert items[1]["capability_rank"] == 1
    assert items[2]["cost_effectiveness_rank"] == 1
    assert len(set(item["recommendation_reason"]["code"] for item in items)) == 3
    assert all(item["recommendation_reason"]["summary"] for item in items)


def test_cost_and_performance_reasons_use_actual_extremes():
    cost_items = [
        {"predicted_price_wan": 10, "capability_score": 80, "cost_effectiveness": 8,
         "technical_match_score": 90, "tag_match_score": 90, "strict_filter_satisfied": True},
        {"predicted_price_wan": 10.5, "capability_score": 90, "cost_effectiveness": 8.57,
         "technical_match_score": 85, "tag_match_score": 85, "strict_filter_satisfied": True},
    ]
    annotate_candidate_recommendations(cost_items, {"scenario": "cost"})
    assert cost_items[0]["recommendation_reason"]["code"] == "lowest_price"
    assert cost_items[1]["recommendation_reason"]["code"] == "near_low_price_more_capability"
    performance_items = [dict(item) for item in cost_items]
    annotate_candidate_recommendations(performance_items, {"scenario": "performance"})
    assert performance_items[1]["recommendation_reason"]["code"] == "highest_capability"


def test_or_filters_compile_to_independent_branches():
    definitions = {"attr_A": {"label": "材料"}, "attr_B": {"label": "锁定方式"}}
    filters = [
        {"parameter_id": "attr_A", "operator": "eq", "value1": "X"},
        {"parameter_id": "attr_B", "operator": "eq", "value1": "Y"},
    ]
    explicit = compile_explicit_demand_branches(filters, "any", definitions)
    combined = combine_generation_branches(explicit, [{"rules": [], "tag_groups": {}}])
    assert [item["demand_branch_id"] for item in combined] == ["BRANCH-01", "BRANCH-02"]
    assert combined[0]["explicit_filters"] == [filters[0]]
    assert combined[1]["explicit_filters"] == [filters[1]]


def _record(value, branch, seed, quality=0.0):
    return {"params": {"x": value}, "_search_key": (0.0, quality, 0.0, 0.0, 0.0, 0.0, 0.0),
            "strict_filter_satisfied": True, "demand_branch_id": branch,
            "seed_id": seed, "family_id": "%s:%s" % (branch, seed), "_risk_signature": ()}


def test_beam_and_final_selection_preserve_branch_coverage():
    generator = HistorySeededGenerator(None, None, None)
    definitions = {"x": {"value_type": "number", "search_type": "continuous", "min_value": 0, "max_value": 100}}
    records = [_record(i * 3, "BRANCH-A", "H01", i * 0.01) for i in range(8)]
    records += [_record(70, "BRANCH-B", "H07", 0.08), _record(90, "BRANCH-C", "H12", 0.10)]
    beam = generator._beam_select(records, definitions, width=5)
    assert {item["demand_branch_id"] for item in beam} >= {"BRANCH-A", "BRANCH-B", "BRANCH-C"}
    selected = generator._coverage_first_select(records, 5, definitions)
    assert {item["demand_branch_id"] for item in selected} >= {"BRANCH-A", "BRANCH-B", "BRANCH-C"}
    assert generator._diverse_strict_count(records[:5], definitions, required_branch_ids=["BRANCH-A", "BRANCH-B"]) == 0
    assert generator._diverse_strict_count(records, definitions, required_branch_ids=["BRANCH-A", "BRANCH-B"]) > 0
    same_location_other_family = _record(0.5, "BRANCH-A", "H02", 0.02)
    assert generator._diverse_strict_count(records[:5] + [same_location_other_family], definitions) == 0


def test_real_generator_carries_or_branch_and_family_identity():
    sys.path.insert(0, str(ROOT / "tests"))
    from beam_multi_round_test import _MockRuntime, _MockStore, mock_evaluate, mock_evaluate_batch
    generator = HistorySeededGenerator(_MockStore(), _MockRuntime(), mock_evaluate, mock_evaluate_batch)
    request = {
        "selected_tags": [], "indicator_filter_mode": "any",
        "indicator_filters": [
            {"parameter_id": "attr_a", "operator": "lte", "value1": 2},
            {"parameter_id": "attr_b", "operator": "lte", "value1": 2},
        ],
        "sort_by": "comprehensive", "target_protocol": None,
    }
    result = generator.generate(request, count=2, seed=19, budget=24, search_mode="fast")
    candidates = result["candidates"]
    assert len(candidates) == 2
    assert {item["demand_branch_id"] for item in candidates} == {"BRANCH-01", "BRANCH-02"}
    assert all(item["family_id"] and item["seed_id"] for item in candidates)
    assert all(item["solution_direction"]["branch_id"] in ("BRANCH-01", "BRANCH-02") for item in candidates)


if __name__ == "__main__":
    test_initial_ui_requires_explicit_recommendation()
    test_candidate_reasons_are_relative_and_distinct()
    test_cost_and_performance_reasons_use_actual_extremes()
    test_or_filters_compile_to_independent_branches()
    test_beam_and_final_selection_preserve_branch_coverage()
    test_real_generator_carries_or_branch_and_family_identity()
    print("PASS V21.3 guided recommendation and diverse generation")
