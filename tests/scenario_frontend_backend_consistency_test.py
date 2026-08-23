# -*- coding: utf-8 -*-
"""V21.2 scenario policy is the shared source for UI, ranking and seed matching."""
from __future__ import print_function

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator  # noqa: E402
from app.recommender import rank_agreements  # noqa: E402
from app.scenario_policy import ScenarioPolicyService  # noqa: E402


class FakeStore(object):
    def parameter_map(self):
        return {"attr": {"parameter_id": "attr", "label": "指标", "value_type": "number", "min_value": 0, "max_value": 10}}

    def tag_map(self):
        return {}

    def constraint_rows(self):
        return []


def item(name, price, capability, attr=5):
    return {
        "agreement_id": name, "agreement_name": name, "agreement_source": "historical",
        "params": {"attr": attr}, "tags": [], "predicted_price_wan": price,
        "historical_price_wan": price, "capability_score": capability,
        "feasibility_probability": 0.9, "physical_gate": {"passed": True},
    }


def main():
    service = ScenarioPolicyService(ROOT / "config" / "scenario_config.json")
    catalog = service.catalog()
    assert catalog["default_scenario"] == "balanced"
    assert [entry["scenario"] for entry in catalog["scenarios"]] == ["balanced", "cost", "performance"]

    cost_request, cost = service.apply({"scenario": "cost"})
    assert cost["applied_ranking"] == {
        "sort_key": "price", "sort_direction": "asc",
        "display_name": "需求匹配优先 · 同等匹配下价格最低",
        "source": "scenario_default", "source_display_name": "成本优先场景推荐",
    }
    performance_request, performance = service.apply({"scenario": "performance"})
    assert performance["applied_ranking"]["sort_key"] == "capability"
    assert performance["applied_ranking"]["sort_direction"] == "desc"
    assert performance["applied_ranking"]["display_name"] == "需求匹配优先 · 同等匹配下效能最高"

    override_request, override = service.apply({
        "scenario": "cost", "sort_source": "user_override",
        "ranking_policy": {"sort_key": "capability", "sort_direction": "desc"},
    })
    assert override["applied_ranking"]["source"] == "user_override"
    assert override["applied_ranking"]["display_name"] == "需求匹配优先 · 同等匹配下效能降序"
    assert override_request["sort_by"] == "capability" and override_request["sort_order"] == "desc"

    constrained, constrained_policy = service.apply({
        "scenario": "cost", "scenario_options": {"min_capability": 80},
    })
    assert constrained["min_capability"] == 80
    assert constrained_policy["applied_constraints"]["min_capability"] == 80
    constrained, _ = service.apply({
        "scenario": "performance", "scenario_options": {"max_price": 15},
    })
    assert constrained["max_price"] == 15
    constrained, constrained_policy = service.apply({
        "scenario": "performance", "max_price": 12,
        "scenario_options": {"max_price": 15},
    })
    assert constrained["max_price"] == 12
    assert constrained_policy["scenario_options"]["max_price"] == 12
    assert constrained_policy["applied_constraints"]["sources"]["max_price"] == \
        "business_target_overrode_scenario_alias"

    # Legacy clients keep their explicit pre-V21.2 sort and scoring semantics.
    legacy, legacy_policy = service.apply({"sort_by": "comprehensive", "sort_order": "desc"})
    assert legacy_policy["strategy_active"] is False
    assert legacy["_scenario_policy"] == {}
    assert legacy["sort_by"] == "comprehensive"

    choices = [item("cheap", 10, 80), item("powerful", 20, 100)]
    ranked_cost = rank_agreements(choices, cost_request, {}, definitions=FakeStore().parameter_map())
    ranked_performance = rank_agreements(choices, performance_request, {}, definitions=FakeStore().parameter_map())
    ranked_override = rank_agreements(choices, override_request, {}, definitions=FakeStore().parameter_map())
    assert ranked_cost[0]["agreement_id"] == "cheap"
    assert ranked_performance[0]["agreement_id"] == "powerful"
    assert ranked_override[0]["agreement_id"] == "powerful"

    generator = HistorySeededGenerator(FakeStore(), None, lambda params, base=None: {})
    assert generator.select_seeds(cost_request, 2, choices)[0]["agreement_id"] == "cheap"
    assert generator.select_seeds(performance_request, 2, choices)[0]["agreement_id"] == "powerful"

    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    server = (ROOT / "app/server.py").read_text(encoding="utf-8")
    assert 'id="scenarioChoices"' in html
    assert "value=\"'+esc(item.scenario)+'\"" in js
    assert "renderScenarioPolicies()" in js
    assert "optimization_scenarios" in server and '"applied_ranking"' in server
    assert "renderAppliedRanking(data)" in js
    assert 'input.checked=input.value===state.scenarioCode' in js
    assert "seq!==state.recommendSeq" in js
    assert "state.currentBatchId=null" in js
    assert "scenarioConstraintField" in js and 'max_price:"maxPrice"' in js
    assert 'state.sortSource="user_override"' in js
    assert 'if scenario==="cost"' not in js and "if scenario==='cost'" not in js
    config = json.loads((ROOT / "config/scenario_config.json").read_text(encoding="utf-8"))
    assert config["scenarios"]["cost"]["default_sort"]["key"] == "price"
    assert config["scenarios"]["performance"]["default_sort"]["key"] == "capability"
    print("PASS V21.2 scenario frontend/backend consistency and user sort override")


if __name__ == "__main__":
    main()
