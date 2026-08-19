# -*- coding: utf-8 -*-
"""Managed parameter groups: bootstrap, admin CRUD, rename propagation, DataMaster derivation."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.store import Store  # noqa: E402


class StubRuntime(object):
    def manifest(self):
        return {"calculation_available": False}

    def feature_roles(self):
        return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}

    def all_feature_specs(self):
        return []


def main():
    db_path = ROOT / "data" / "_parameter_groups_admin_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    try:
        store.admin_upsert("parameters", {"parameter_id": "attr_env", "label": "环境温度", "parameter_group": "环境属性", "value_type": "number", "display_order": 1})
        store.admin_upsert("parameters", {"parameter_id": "attr_fn", "label": "功能开关", "parameter_group": "功能属性", "value_type": "boolean", "display_order": 2})
        store.admin_upsert("parameters", {"parameter_id": "attr_orphan", "label": "未分组指标", "parameter_group": "其他", "value_type": "number", "display_order": 3})

        snap = store.admin_snapshot()
        group_names = [g["group_name"] for g in snap["parameter_groups"]]
        assert "环境属性" in group_names and "功能属性" in group_names and "其他" in group_names, group_names

        boot = store.bootstrap()
        boot_groups = [g["group_name"] for g in boot["parameter_groups"]]
        assert "环境属性" in boot_groups and "其他" in boot_groups, boot_groups

        # Create a new managed group through admin CRUD.
        store.admin_upsert("parameter_groups", {"group_name": "结构属性", "display_order": 4, "description": "结构相关", "enabled": 1, "default_collapsed": 1})
        assert any(g["group_name"] == "结构属性" and g["default_collapsed"] == 1 for g in store.admin_snapshot()["parameter_groups"])

        # Rename propagates to parameter definitions.
        store.admin_upsert("parameter_groups", {"group_name": "环境与防护", "original_group_name": "环境属性", "display_order": 1, "description": "", "enabled": 1, "default_collapsed": 0})
        pmap = store.parameter_map()
        assert pmap["attr_env"]["parameter_group"] == "环境与防护", pmap["attr_env"]
        assert "环境属性" not in [g["group_name"] for g in store.admin_snapshot()["parameter_groups"]]

        # Disable and dependency guard for permanent deletion.
        store.admin_toggle("parameter_groups", "环境与防护", False)
        deps = store.admin_dependencies("parameter_groups", "环境与防护")
        assert any(x["type"] == "指标" and x["count"] >= 1 for x in deps), deps

        # DataMaster replacement without an explicit group sheet derives groups.
        store.replace_from_datamaster({
            "products": [{"product_code": "P1", "product_name": "产品", "enabled": 1}],
            "parameters": [
                {"parameter_id": "a1", "label": "A1", "parameter_group": "性能属性", "value_type": "number", "display_order": 1},
                {"parameter_id": "a2", "label": "A2", "parameter_group": "性能属性", "value_type": "number", "display_order": 2},
            ],
            "tags": [], "tag_rules": [], "couplings": [], "constraints": [], "agreements": [],
        }, evaluate_agreements=False, sync_model_contract=False)
        snap2 = store.admin_snapshot()
        names2 = [g["group_name"] for g in snap2["parameter_groups"]]
        assert "性能属性" in names2 and "其他" in names2, names2
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "指标分组主数据、重命名传播、DataMaster推导均通过"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
