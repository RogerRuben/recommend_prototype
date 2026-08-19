# -*- coding: utf-8 -*-
"""Full V2 chain: save -> projection -> assess -> repair never treats placeholders as affine."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.constraint_projection import project_constraints  # noqa: E402
from app.local_generator import HistorySeededGenerator  # noqa: E402
from app.store import Store  # noqa: E402


class _MockEffectiveness(object):
    couplings = []
    coupling_edges = []
    learned_boundaries = []


class StubRuntime(object):
    schema = {"product_code": "P1", "product_name": "产品1"}
    effectiveness = _MockEffectiveness()

    def manifest(self):
        return {"calculation_available": False}

    def feature_roles(self):
        return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}

    def all_feature_specs(self):
        return []


def main():
    db_path = ROOT / "data" / "_conditional_v2_full_chain_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    try:
        store.replace_from_datamaster({
            "products": [{"product_code": "P1", "product_name": "产品1", "enabled": 1}],
            "parameters": [
                {"parameter_id": "attr_001", "label": "控制器", "value_type": "boolean",
                 "search_type": "boolean", "min_value": -1, "max_value": 1, "display_order": 1},
                {"parameter_id": "attr_num", "label": "数值从属", "value_type": "number",
                 "search_type": "continuous", "min_value": 0, "max_value": 30, "display_order": 2},
                {"parameter_id": "attr_mat", "label": "材料", "value_type": "enum",
                 "search_type": "unordered_enum", "min_value": None, "max_value": None,
                 "allowed_values_json": '["不锈钢","钛合金"]',
                 "model_value_mapping_json": '{"不锈钢":"SS","钛合金":"TI"}',
                 "display_order": 3},
                {"parameter_id": "attr_bool", "label": "布尔从属", "value_type": "boolean",
                 "search_type": "boolean", "min_value": -1, "max_value": 1, "display_order": 4},
            ],
            "parameter_groups": [], "tags": [], "tag_rules": [], "couplings": [],
            "constraints": [], "agreements": [],
        }, evaluate_agreements=False, sync_model_contract=False)

        # UI/API would send exactly this V2 payload.
        store.upsert_conditional_template({
            "template": "conditional_applicability_v2", "controller": "attr_001",
            "when": {"operator": "equals", "business_value": "无", "model_value": 0},
            "target": "attr_num",
            "then": {"mode": "not_applicable", "business_value": "无该属性", "model_value": 0},
            "otherwise": {"mode": "range", "min": 0, "max": 30},
            "severity": "error",
        })
        store.upsert_conditional_template({
            "template": "conditional_applicability_v2", "controller": "attr_001",
            "when": {"operator": "equals", "business_value": "无", "model_value": 0},
            "target": "attr_mat",
            "then": {"mode": "not_applicable", "business_value": "无该属性", "model_value": "SS"},
            "otherwise": {"mode": "enum", "allowed": ["SS", "TI"]},
            "severity": "error",
        })
        store.upsert_conditional_template({
            "template": "conditional_applicability_v2", "controller": "attr_001",
            "when": {"operator": "equals", "business_value": "无", "model_value": 0},
            "target": "attr_bool",
            "then": {"mode": "not_applicable", "business_value": "无该属性", "model_value": 0},
            "otherwise": {"mode": "fixed", "model_value": 1},
            "severity": "error",
        })

        rules = store.constraint_rows()
        definitions = store.parameter_map()

        # Inactive controller: all targets collapse to configured model values.
        inactive = project_constraints(
            {"attr_001": 0, "attr_num": 5, "attr_mat": "TI", "attr_bool": 1},
            definitions, rules,
        )
        assert inactive["parameters"]["attr_num"] == 0, inactive["parameters"]
        assert inactive["parameters"]["attr_mat"] == "SS", inactive["parameters"]
        assert inactive["parameters"]["attr_bool"] == 0, inactive["parameters"]
        assert "attr_num" in inactive["inactive_parameters"]

        # Active controller: range/enum/fixed branches apply without affine errors.
        active = project_constraints(
            {"attr_001": 1, "attr_num": 5, "attr_mat": "TI", "attr_bool": 0},
            definitions, rules,
        )
        assert active["parameters"]["attr_num"] == 5, active["parameters"]
        assert active["parameters"]["attr_mat"] == "TI", active["parameters"]
        assert active["parameters"]["attr_bool"] == 1, active["parameters"]

        # assess_rules must ignore V2 placeholder rows entirely.
        assert store.assess_rules(active["parameters"]) == [], store.assess_rules(active["parameters"])

        # _repair_relations must also ignore V2 placeholder rows even at severity=error.
        gen = HistorySeededGenerator(store, StubRuntime(), None, None)
        before = dict(active["parameters"])
        repairs = gen._repair_relations(before, dict(before), definitions, set())
        assert repairs == [], repairs
        assert before == active["parameters"], (before, active["parameters"])
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "V2 全链：保存/投影/评估/修复均不再执行占位 affine"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
