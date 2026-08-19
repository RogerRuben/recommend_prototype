# -*- coding: utf-8 -*-
"""V1 conditional templates remain compatible while V2 can be stored/migrated."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.constraint_projection import project_constraints  # noqa: E402
from app.store import Store  # noqa: E402


class StubRuntime(object):
    schema = {"product_code": "P1", "product_name": "产品1"}

    def manifest(self):
        return {"calculation_available": False}

    def feature_roles(self):
        return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}

    def all_feature_specs(self):
        return []


def main():
    db_path = ROOT / "data" / "_conditional_v1_migration_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    try:
        store.replace_from_datamaster({
            "products": [{"product_code": "P1", "product_name": "产品1", "enabled": 1}],
            "parameters": [
                {"parameter_id": "attr_001", "label": "是否液冷", "value_type": "boolean",
                 "search_type": "boolean", "min_value": -1, "max_value": 1, "display_order": 1},
                {"parameter_id": "attr_004", "label": "冷却液流量", "value_type": "number",
                 "search_type": "continuous", "min_value": 0, "max_value": 30, "display_order": 2},
            ],
            "parameter_groups": [], "tags": [], "tag_rules": [], "couplings": [],
            "constraints": [], "agreements": [],
        }, evaluate_agreements=False, sync_model_contract=False)

        # V1 template still saves and projects.
        v1 = store.upsert_conditional_template({
            "controller": "attr_001", "active_value": 1, "target": "attr_004",
            "inactive_value": -1, "active_min": 0, "active_max": 30,
        })
        assert v1["saved"]
        rules1 = store.constraint_rows()
        projected1 = project_constraints({"attr_001": 0, "attr_004": 5}, store.parameter_map(), rules1)
        assert "attr_004" in projected1["inactive_parameters"]
        assert projected1["parameters"]["attr_004"] == -1

        # V2 template can be saved through the same API and projects from metadata.
        v2 = store.upsert_conditional_template({
            "template": "conditional_applicability_v2",
            "controller": "attr_001",
            "when": {"operator": "equals", "business_value": "无", "model_value": 0},
            "target": "attr_004",
            "then": {"mode": "not_applicable", "business_value": "无该属性", "model_value": 0},
            "otherwise": {"mode": "range", "min": 0, "max": 30},
        })
        assert v2["saved"]
        templates = {t["constraint_group"]: t for t in store.conditional_templates()}
        v2_group = v2["constraint_group"]
        assert templates[v2_group]["template_metadata"]["template"] == "conditional_applicability_v2"
        rules2 = store.constraint_rows()
        projected2 = project_constraints({"attr_001": 0, "attr_004": 5}, store.parameter_map(), rules2)
        assert "attr_004" in projected2["inactive_parameters"]
        assert projected2["parameters"]["attr_004"] == 0
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "V1保持兼容，V2可保存并直接驱动投影"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
