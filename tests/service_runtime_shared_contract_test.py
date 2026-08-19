# -*- coding: utf-8 -*-
"""ServiceBackedRuntime must expose per-model specs and block shared-target model conflicts."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.model_service_client import ServiceBackedRuntime  # noqa: E402
from app.store import Store  # noqa: E402


class FakeGateway(object):
    product_code = "P1"
    fallback = None

    def schemas(self):
        return {
            "effectiveness": {
                "product_code": "P1", "product_name": "产品1", "model_version": "e1",
                "fields": [
                    {"field_name": "attr_004", "field_label": "从属", "dtype": "number",
                     "min": -1, "max": 30, "required": True, "missing_policy": "reject",
                     "source": "product_parameter"},
                ],
            },
            "price": {
                "product_code": "P1", "product_name": "产品1", "model_version": "p1",
                "fields": [
                    {"field_name": "attr_004", "field_label": "从属", "dtype": "number",
                     "min": 0, "max": 30, "required": True, "missing_policy": "reject",
                     "source": "product_parameter"},
                ],
            },
        }


def main():
    runtime = ServiceBackedRuntime(FakeGateway())
    specs = runtime.model_feature_specs()
    effect_specs = [s for s in specs if s.get("model_kind") == "effectiveness" and s.get("key") == "attr_004"]
    price_specs = [s for s in specs if s.get("model_kind") == "price" and s.get("key") == "attr_004"]
    assert len(effect_specs) == 1, specs
    assert len(price_specs) == 1, specs
    assert effect_specs[0]["min"] == -1 and price_specs[0]["min"] == 0

    db_path = ROOT / "data" / "_service_runtime_shared_contract_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", runtime)
    try:
        store.replace_from_datamaster({
            "products": [{"product_code": "P1", "product_name": "产品1", "enabled": 1}],
            "parameters": [
                {"parameter_id": "attr_001", "label": "控制器", "value_type": "boolean",
                 "search_type": "boolean", "min_value": -1, "max_value": 1, "display_order": 1},
                {"parameter_id": "attr_004", "label": "从属", "value_type": "number",
                 "search_type": "continuous", "min_value": -10, "max_value": 30, "display_order": 2},
            ],
            "parameter_groups": [], "tags": [], "tag_rules": [], "couplings": [],
            "constraints": [], "agreements": [],
        }, evaluate_agreements=False, sync_model_contract=False)

        # -1 is allowed by effectiveness but rejected by price -> must block online save.
        bad = {
            "template": "conditional_applicability_v2",
            "controller": "attr_001",
            "when": {"operator": "equals", "business_value": "无", "model_value": 0},
            "target": "attr_004",
            "then": {"mode": "not_applicable", "business_value": "无该属性", "model_value": -1},
            "otherwise": {"mode": "range", "min": 0, "max": 30},
        }
        try:
            store.upsert_conditional_template(bad)
            raise AssertionError("online save with price-incompatible model value must be rejected")
        except ValueError:
            pass

        # 0 is compatible with both -> save succeeds.
        good = dict(bad)
        good["then"] = {"mode": "not_applicable", "business_value": "无该属性", "model_value": 0}
        result = store.upsert_conditional_template(good)
        assert result["saved"] is True
        assert result["compatibility"]["model_compatibility"]["price"]["compatible"] is True
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "ServiceBackedRuntime 双契约生效，价格模型不接受的共享字段值被拒绝保存"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
