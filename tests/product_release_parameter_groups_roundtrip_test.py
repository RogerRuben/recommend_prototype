# -*- coding: utf-8 -*-
"""Product Release round-trip must preserve parameter_group and parameter_groups."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_master import DataMasterService  # noqa: E402
from app.product_releases import ProductReleaseService  # noqa: E402
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
    db_path = ROOT / "data" / "_product_release_groups_roundtrip_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    runtime = StubRuntime()
    try:
        store.replace_from_datamaster({
            "products": [{"product_code": "P1", "product_name": "产品1", "enabled": 1}],
            "parameters": [
                {"parameter_id": "A1", "label": "A1", "parameter_group": "环境属性", "value_type": "number", "display_order": 1},
                {"parameter_id": "A2", "label": "A2", "parameter_group": "环境属性", "value_type": "number", "display_order": 2},
            ],
            "parameter_groups": [{"group_name": "环境属性", "display_order": 1, "description": "环境相关", "enabled": 1, "default_collapsed": 1}],
            "tags": [], "tag_rules": [], "couplings": [], "constraints": [], "agreements": [],
        }, evaluate_agreements=False, sync_model_contract=False)

        releases = ProductReleaseService(store, runtime)
        datamaster = DataMasterService(store, runtime)

        cloned = releases.clone_current()
        assert any(g["group_name"] == "环境属性" and g["default_collapsed"] == 1 for g in cloned["data"]["parameter_groups"])
        assert all(p.get("parameter_group") == "环境属性" for p in cloned["data"]["parameters"] if p["parameter_id"] in ("A1", "A2"))

        # Export the draft as a maintenance workbook and import into a new draft.
        workbook = datamaster.export_snapshot(cloned["data"])
        draft = releases.create(product_code="P2", product_name="产品2")
        imported = releases.import_maintenance_workbook(draft["release_id"], "maintenance.xlsx", workbook)

        imported_data = imported["release"]["data"]
        assert any(g["group_name"] == "环境属性" and g["default_collapsed"] == 1 for g in imported_data["parameter_groups"])
        assert all(p.get("parameter_group") == "环境属性" for p in imported_data["parameters"] if p["parameter_id"] in ("A1", "A2"))

        # Validate and activate; bootstrap must still expose the same groups.
        validation = releases.validate(draft["release_id"])
        assert validation["valid"], validation["errors"]
        releases.activate(draft["release_id"])
        boot = store.bootstrap()
        boot_groups = [g["group_name"] for g in boot["parameter_groups"]]
        assert "环境属性" in boot_groups, boot_groups
        boot_params = {p["parameter_id"]: p for p in boot["parameters"]}
        assert boot_params["A1"]["parameter_group"] == "环境属性", boot_params["A1"]
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "Product Release维护工作簿完整保留指标分组与parameter_group"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
