# -*- coding: utf-8 -*-
"""Conditional template metadata round-trips and controller/target edits clean old groups."""
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
    db_path = ROOT / "data" / "_template_roundtrip_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    try:
        for pid, label, group in (("has_cooling", "是否液冷", "功能属性"), ("cooling_flow", "冷却液流量", "性能属性"), ("cooling_pressure", "冷却压力", "性能属性")):
            store.admin_upsert("parameters", {"parameter_id": pid, "label": label, "value_type": "number" if pid != "has_cooling" else "boolean", "parameter_group": group})

        # parameter_group persists through the admin upsert.
        pmap = store.parameter_map()
        assert pmap["has_cooling"].get("parameter_group") == "功能属性", pmap["has_cooling"]

        # Create controller has_cooling -> target cooling_flow.
        r1 = store.upsert_conditional_template({"controller": "has_cooling", "target": "cooling_flow",
                                                "inactive_value": -1, "active_min": 0, "active_max": 30})
        g1 = r1["constraint_group"]
        # Edit to a different target with the original group supplied.
        store.upsert_conditional_template({"controller": "has_cooling", "target": "cooling_pressure",
                                           "inactive_value": -1, "active_min": 0, "active_max": 10,
                                           "original_constraint_group": g1})
        rows = store.constraint_rows()
        assert all(r.get("constraint_group") != g1 for r in rows), "old group must be removed on target edit"
        # New group exists with two rules.
        new_groups = {r["constraint_group"] for r in rows if r.get("constraint_group")}
        assert len(new_groups) == 1, new_groups
        assert sum(1 for r in rows if r.get("constraint_group")) == 2

        # Metadata columns survive a raw round-trip through the rows.
        for r in rows:
            if r.get("constraint_group"):
                assert r.get("rule_kind") in ("conditional_lower", "conditional_upper")
                assert r.get("template_metadata_json")
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "模板元数据round-trip、编辑换target清旧组、parameter_group落库"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
