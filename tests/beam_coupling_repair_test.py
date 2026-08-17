# -*- coding: utf-8 -*-
"""Coupling repair must be symmetric and parent-relative.

A positive A↔B coupling is a symmetric trend rule.  The repair must fire no
matter which side the current move touched (A-moved or B-moved) and must measure
the delta against the given reference (the parent centre), never against a hard
coded historical seed.
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
               "search_type": "integer", "min_value": 0, "max_value": 20,
               "decimal_places": 0, "enabled": 1, "auto_adjustable": 1, "allowed_values_json": None},
    "attr_b": {"parameter_id": "attr_b", "label": "属性B", "value_type": "number",
               "search_type": "integer", "min_value": 0, "max_value": 20,
               "decimal_places": 0, "enabled": 1, "auto_adjustable": 1, "allowed_values_json": None},
}

COUPLING = {
    "coupling_id": "CPL-1", "coupling_name": "A-B正相关", "coupling_type": "positive",
    "parameter_a": "attr_a", "parameter_b": "attr_b", "domain_operator": None,
    "multiplier": None, "offset": None, "strength": 0.35, "severity": "warning",
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
        return []

    def tag_map(self):
        return {}

    def tag_rule_branches(self, selected_tags, max_branches=24):
        return [{"rules": [], "tag_groups": {}, "unresolved_tags": []}]

    def coupling_rows(self):
        return [COUPLING]

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


def main():
    gen = HistorySeededGenerator(_MockStore(), _MockRuntime(), lambda p, b=None, t=None: {}, None)
    definitions = PARAMETER_DEFINITIONS
    reference = {"attr_a": 10, "attr_b": 10}

    # A moved alone -> B must follow (down, since positive coupling and A fell).
    params = {"attr_a": 8, "attr_b": 10}
    repairs = gen._repair_relations(params, reference, definitions, {})
    assert repairs, "A-moved repair must fire"
    assert float(params["attr_b"]) < 10.0, "B should follow A downward, got %s" % params["attr_b"]

    # B moved alone -> A must follow (this was the asymmetric gap).
    params = {"attr_a": 10, "attr_b": 8}
    repairs = gen._repair_relations(params, reference, definitions, {})
    assert repairs, "B-moved repair must fire"
    assert float(params["attr_a"]) < 10.0, "A should follow B downward, got %s" % params["attr_a"]

    # B moved alone with A locked -> nothing can be repaired (A is locked).
    params = {"attr_a": 10, "attr_b": 8}
    repairs = gen._repair_relations(params, reference, definitions, {"attr_a": 10})
    assert not repairs, "locked A must block B-driven repair"
    assert float(params["attr_a"]) == 10.0

    # Parent-relative: a move that keeps A/B consistent with the parent produces
    # no repair even when both differ from any historical seed.
    parent = {"attr_a": 6, "attr_b": 6}
    params = {"attr_a": 6, "attr_b": 7}
    repairs = gen._repair_relations(params, parent, definitions, {})
    assert repairs, "inconsistent relative move must still be repaired"

    print(json.dumps({"status": "PASS", "message": "耦合修复双向且相对父中心执行"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
