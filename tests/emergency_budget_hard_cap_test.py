# -*- coding: utf-8 -*-
"""Emergency fallback must not bypass the generation hard evaluation budget."""
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
    "env": {"parameter_id": "env", "label": "环境温度", "value_type": "number",
            "search_type": "integer", "min_value": -60, "max_value": 60,
            "decimal_places": 0, "enabled": 1, "auto_adjustable": 1, "allowed_values_json": None},
}

SEEDS = [
    {"agreement_id": "H-01", "params": {"attr_a": 10, "env": 40}, "tags": []},
    {"agreement_id": "H-02", "params": {"attr_a": 9, "env": 35}, "tags": []},
]

CALLS = {"n": 0}


def mock_evaluate(params, base_params=None, target_protocol=None):
    CALLS["n"] += 1
    raise ValueError("mock model always fails for hard-cap test")


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


def main():
    CALLS["n"] = 0
    gen = HistorySeededGenerator(_MockStore(), _MockRuntime(), mock_evaluate, None)
    request = {"min_capability": 50, "frozen_parameters": [], "selected_tags": [],
               "indicator_filters": [], "indicator_filter_mode": "all",
               "sort_by": "comprehensive", "count": 2, "target_protocol": None}
    result = gen.generate(request, count=2, seed=5, budget=1, search_mode="fast")

    assert CALLS["n"] <= 1, "model was called %d times with budget=1" % CALLS["n"]
    assert result["actual_budget_used"] == CALLS["n"], (result["actual_budget_used"], CALLS["n"])
    assert result["generation_budget"] == 1

    print(json.dumps({"status": "PASS", "message": "emergency fallback 不再绕过 hard budget"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
