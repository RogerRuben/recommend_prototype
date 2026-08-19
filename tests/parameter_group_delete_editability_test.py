# -*- coding: utf-8 -*-
"""Deleting parameter groups must not break later data editing; referenced groups are protected."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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
    db_path = ROOT / "data" / "_parameter_group_delete_editability_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    try:
        store.replace_from_datamaster({
            "products": [{"product_code": "P1", "product_name": "产品1", "enabled": 1}],
            "parameters": [
                {"parameter_id": "A1", "label": "A1", "parameter_group": "G", "value_type": "number", "display_order": 1},
                {"parameter_id": "A2", "label": "A2", "parameter_group": "G", "value_type": "number", "display_order": 2},
            ],
            "parameter_groups": [
                {"group_name": "G", "display_order": 1, "description": "", "enabled": 1, "default_collapsed": 0},
                {"group_name": "EMPTY", "display_order": 2, "description": "", "enabled": 1, "default_collapsed": 0},
            ],
            "tags": [], "tag_rules": [], "couplings": [], "constraints": [], "agreements": [],
        }, evaluate_agreements=False, sync_model_contract=False)

        # Referenced group cannot be permanently deleted.
        try:
            store.admin_purge("parameter_groups", "G")
            raise AssertionError("expected referenced group purge to be rejected")
        except ValueError as exc:
            assert "2" in str(exc), str(exc)

        # Empty group can be archived and then deleted.
        store.admin_toggle("parameter_groups", "EMPTY", False)
        store.admin_purge("parameter_groups", "EMPTY")
        assert all(g["group_name"] != "EMPTY" for g in store.admin_snapshot()["parameter_groups"])

        # After deletion, editing parameters and agreements still works.
        store.admin_upsert("parameters", {"parameter_id": "A1", "label": "A1-改", "parameter_group": "G", "value_type": "number", "display_order": 1})
        assert store.parameter_map()["A1"]["label"] == "A1-改"
        store.admin_upsert("agreements", {
            "agreement_id": "AGR-1", "product_code": "P1", "agreement_name": "协议1",
            "agreement_source": "historical", "enabled": 1, "params": {"A1": 5}, "tags": [],
        })
        assert any(a["agreement_id"] == "AGR-1" for a in store.admin_snapshot()["agreements"])
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "删除空分组后编辑仍可用，引用分组被禁止删除"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
