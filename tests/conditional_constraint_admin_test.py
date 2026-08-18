# -*- coding: utf-8 -*-
"""Conditional-attribute template admin CRUD is group-atomic."""
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
    db_path = ROOT / "data" / "_conditional_admin_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    try:
        store.admin_upsert("parameters", {"parameter_id": "has_cooling", "label": "是否液冷", "value_type": "boolean"})
        store.admin_upsert("parameters", {"parameter_id": "cooling_flow", "label": "冷却液流量", "value_type": "number", "min_value": -1, "max_value": 30})

        result = store.upsert_conditional_template({
            "controller": "has_cooling", "active_value": 1, "target": "cooling_flow",
            "inactive_value": -1, "active_min": 0, "active_max": 30,
        })
        group = result["constraint_group"]
        group_rows = [r for r in store.constraint_rows() if r.get("constraint_group") == group]
        assert len(group_rows) == 2, group_rows
        assert sorted(r["rule_kind"] for r in group_rows) == ["conditional_lower", "conditional_upper"]

        # Edit replaces the whole group (still exactly two rules).
        store.upsert_conditional_template({
            "controller": "has_cooling", "active_value": 1, "target": "cooling_flow",
            "inactive_value": -1, "active_min": 5, "active_max": 20,
        })
        group_rows2 = [r for r in store.constraint_rows() if r.get("constraint_group") == group]
        assert len(group_rows2) == 2, group_rows2

        # Templates list exposes the group once with its two rule rows.
        templates = {t["constraint_group"]: t for t in store.conditional_templates()}
        assert group in templates and len(templates[group]["rules"]) == 2

        # Delete removes both rules, never a dangling half-rule.
        store.delete_conditional_template(group)
        assert all(r.get("constraint_group") != group for r in store.constraint_rows())
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "条件属性模板成组增删改，不残留半条约束"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
