# -*- coding: utf-8 -*-
"""Disabled parameter groups: existing params stay, new assignments are blocked, UI marks disabled."""
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
    db_path = ROOT / "data" / "_parameter_groups_disabled_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    try:
        store.replace_from_datamaster({
            "products": [{"product_code": "P1", "product_name": "产品1", "enabled": 1}],
            "parameters": [
                {"parameter_id": "A1", "label": "A1", "parameter_group": "环境属性", "value_type": "number", "display_order": 1},
            ],
            "parameter_groups": [{"group_name": "环境属性", "display_order": 1, "description": "", "enabled": 1, "default_collapsed": 0}],
            "tags": [], "tag_rules": [], "couplings": [], "constraints": [], "agreements": [],
        }, evaluate_agreements=False, sync_model_contract=False)

        store.admin_toggle("parameter_groups", "环境属性", False)
        groups = {g["group_name"]: g for g in store.bootstrap()["parameter_groups"]}
        assert groups["环境属性"]["enabled"] == 0, groups["环境属性"]

        # New parameter cannot be assigned to a disabled group.
        try:
            store.admin_upsert("parameters", {"parameter_id": "A2", "label": "A2", "parameter_group": "环境属性", "value_type": "number", "display_order": 2})
            raise AssertionError("expected disabled group assignment to be rejected")
        except ValueError:
            pass

        # Existing parameter in the disabled group can still be edited without moving it.
        store.admin_upsert("parameters", {"parameter_id": "A1", "label": "A1-改名", "parameter_group": "环境属性", "value_type": "number", "display_order": 1})
        assert store.parameter_map()["A1"]["label"] == "A1-改名"

        # Re-enable allows new assignments again.
        store.admin_toggle("parameter_groups", "环境属性", True)
        store.admin_upsert("parameters", {"parameter_id": "A2", "label": "A2", "parameter_group": "环境属性", "value_type": "number", "display_order": 2})
        assert "A2" in store.parameter_map()
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    # Frontend/Admin static guards for disabled-group presentation.
    app_js = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    admin_js = (ROOT / "app" / "static" / "admin.js").read_text(encoding="utf-8")
    assert "frozen-group-disabled" in app_js
    assert "disabled=!metaG.enabled" in app_js
    assert "（已停用）" in admin_js
    assert "disabled" in admin_js

    print(json.dumps({"status": "PASS", "message": "停用指标分组语义已闭环：旧指标保留、新分配阻止、UI标记停用"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
