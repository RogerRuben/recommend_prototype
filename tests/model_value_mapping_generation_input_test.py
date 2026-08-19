# -*- coding: utf-8 -*-
"""Business enum values must be mapped to model encodings before model input."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_master import validate_business_data  # noqa: E402
from app.store import Store  # noqa: E402


class StubRuntime(object):
    schema = {"product_code": "P1", "product_name": "产品1"}

    def manifest(self):
        return {"calculation_available": False}

    def feature_roles(self):
        return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}

    def all_feature_specs(self):
        return []


class RecordingModel(object):
    def __init__(self):
        self.received = None

    def evaluate(self, model_params):
        self.received = dict(model_params)
        return {
            "predicted_price_wan": 10.0, "price_interval_wan": [10.0, 10.0],
            "capability_score": 50.0, "conservative_capability_score": 50.0,
            "protocol_score_interval": [50.0, 50.0], "support_at_80": None,
            "support_at_100": None, "score_uncertainty_width": 0.0,
            "feasibility_probability": 0.9, "physical_gate": {"passed": True},
            "cost_effectiveness": 5.0, "parameters": dict(model_params),
            "anomaly_assessment": {"status": "in_domain", "is_anomaly": False, "items": []},
            "rule_messages": [], "coupling_assessments": [], "hard_risk_reasons": [],
            "learned_boundary_violations": [], "risk_contributors": [],
            "requirement_assessment": {}, "model_versions": {}, "model_audit": {},
        }


def main():
    db_path = ROOT / "data" / "_model_value_mapping_generation_input_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    try:
        store.replace_from_datamaster({
            "products": [{"product_code": "P1", "product_name": "产品1", "enabled": 1}],
            "parameters": [{
                "parameter_id": "attr_003", "label": "锁体材料", "value_type": "enum",
                "search_type": "unordered_enum", "min_value": 0, "max_value": 3,
                "allowed_values_json": '["不锈钢","钛合金","高强铝合金"]',
                "model_value_mapping_json": '{"不锈钢":1.0,"钛合金":2.0,"高强铝合金":0.0}',
                "display_order": 1, "required": 0, "auto_adjustable": 1,
                "decimal_places": 3, "enabled": 1, "model_bound": 1,
            }],
            "parameter_groups": [], "tags": [], "tag_rules": [], "couplings": [],
            "constraints": [], "agreements": [],
        }, evaluate_agreements=False, sync_model_contract=False)

        business_params = {"attr_003": "高强铝合金"}
        model_params = store.runtime_parameters(business_params)
        assert model_params["attr_003"] == 0.0, model_params

        # Fake model service records the encoded value, never the Chinese string.
        model = RecordingModel()
        model.evaluate(model_params)
        assert model.received["attr_003"] == 0.0, model.received
        assert model.received["attr_003"] != "高强铝合金", model.received
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    # DataMaster validation warns in business language when mapping is incomplete.
    incomplete = {
        "products": [{"product_code": "P1", "product_name": "产品1", "enabled": 1}],
        "parameters": [{
            "parameter_id": "A1", "label": "锁体材料", "value_type": "enum",
            "allowed_values_json": '["不锈钢","钛合金","高强铝合金"]',
            "model_value_mapping_json": '{"不锈钢":1,"钛合金":2}',
        }],
        "parameter_groups": [], "tags": [], "tag_rules": [], "couplings": [],
        "constraints": [], "agreements": [],
    }
    _errors, warnings = validate_business_data(incomplete)
    assert any("高强铝合金" in w for w in warnings), warnings

    print(json.dumps({"status": "PASS", "message": "业务枚举到模型编码完整转换，缺失映射给出业务化提示"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
