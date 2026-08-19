# -*- coding: utf-8 -*-
"""Real chain: incomplete seed + enum mapping + conditional relationship -> model input complete."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator  # noqa: E402
from app.store import Store  # noqa: E402


class StubRuntime(object):
    schema = {"product_code": "P1", "product_name": "产品1"}

    def manifest(self):
        return {"calculation_available": False}

    def feature_roles(self):
        return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}

    def all_feature_specs(self):
        return []


class _MockEffectiveness(object):
    couplings = []
    coupling_edges = []
    learned_boundaries = []


class MockRuntime(object):
    schema = {"product_code": "P1", "product_name": "产品1"}
    effectiveness = _MockEffectiveness()

    def all_feature_specs(self):
        return [
            {"key": "attr_003", "label": "锁体材料", "required": True, "missing_policy": "reject"},
            {"key": "attr_004", "label": "锁舌长度", "required": True, "missing_policy": "reject"},
            {"key": "attr_006", "label": "重量", "required": True, "missing_policy": "reject"},
        ]


def main():
    db_path = ROOT / "data" / "_real_generation_incomplete_seed_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    try:
        store.replace_from_datamaster({
            "products": [{"product_code": "P1", "product_name": "产品1", "enabled": 1}],
            "parameters": [
                {"parameter_id": "attr_001", "label": "是否应急解锁", "value_type": "boolean",
                 "search_type": "boolean", "min_value": -1, "max_value": 1, "display_order": 1,
                 "required": 0, "auto_adjustable": 1, "decimal_places": 0, "enabled": 1, "model_bound": 0},
                {"parameter_id": "attr_003", "label": "锁体材料", "value_type": "enum",
                 "search_type": "unordered_enum", "min_value": 0, "max_value": 3, "display_order": 2,
                 "allowed_values_json": '["不锈钢","钛合金","高强铝合金"]',
                 "model_value_mapping_json": '{"不锈钢":1.0,"钛合金":2.0,"高强铝合金":0.0}',
                 "required": 0, "auto_adjustable": 1, "decimal_places": 3, "enabled": 1, "model_bound": 1},
                {"parameter_id": "attr_004", "label": "锁舌长度", "value_type": "number",
                 "search_type": "continuous", "min_value": 0, "max_value": 30, "display_order": 3,
                 "required": 0, "auto_adjustable": 1, "decimal_places": 2, "enabled": 1, "model_bound": 1},
                {"parameter_id": "attr_006", "label": "重量", "value_type": "number",
                 "search_type": "continuous", "min_value": 0, "max_value": 10, "display_order": 4,
                 "required": 0, "auto_adjustable": 1, "decimal_places": 1, "enabled": 1, "model_bound": 1},
            ],
            "parameter_groups": [], "tags": [], "tag_rules": [], "couplings": [],
            "constraints": [], "agreements": [],
        }, evaluate_agreements=False, sync_model_contract=False)

        store.upsert_conditional_template({
            "template": "conditional_applicability_v2",
            "controller": "attr_001",
            "when": {"operator": "equals", "business_value": "无", "model_value": 0},
            "target": "attr_004",
            "then": {"mode": "not_applicable", "business_value": "无该属性", "model_value": 0},
            "otherwise": {"mode": "range", "min": 0, "max": 30},
        })

        seeds = [
            {"agreement_id": "H-01", "params": {"attr_001": 0, "attr_003": "高强铝合金"}, "tags": []},
        ]
        received = {}

        def mock_evaluate(params, base_params=None, target_protocol=None):
            model_params = store.runtime_parameters(dict(params))
            received["model_params"] = dict(model_params)
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

        # Replace store.historical_agreements to return our incomplete seed.
        original_historical = store.historical_agreements
        store.historical_agreements = lambda target_protocol=None: seeds

        gen = HistorySeededGenerator(store, MockRuntime(), mock_evaluate, None)
        request = {
            "min_capability": 50, "frozen_parameters": [], "selected_tags": [],
            "indicator_filters": [
                {"parameter_id": "attr_003", "operator": "text_equals", "value1": "高强铝合金"},
                {"parameter_id": "attr_006", "operator": "lte", "value1": 2.2},
            ],
            "indicator_filter_mode": "all", "sort_by": "comprehensive", "count": 1,
            "target_protocol": None,
        }
        result = gen.generate(request, count=1, seed=7, budget=200, search_mode="fast")

        assert received.get("model_params"), "model was not called"
        assert received["model_params"]["attr_003"] == 0.0, received["model_params"]
        assert received["model_params"]["attr_004"] == 0, received["model_params"]
        assert received["model_params"]["attr_006"] == 2.2, received["model_params"]
        assert result.get("actual_rounds", 0) >= 1, result

        store.historical_agreements = original_historical
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "真实不完整Seed链：映射/条件关系/缺失创建后模型输入完整并进入搜索"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
