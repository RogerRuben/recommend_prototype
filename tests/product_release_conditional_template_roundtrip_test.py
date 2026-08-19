# -*- coding: utf-8 -*-
"""Product Release round-trip must preserve conditional-attribute template metadata."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.constraint_projection import project_constraints  # noqa: E402
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
    db_path = ROOT / "data" / "_product_release_cond_template_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    runtime = StubRuntime()
    try:
        store.replace_from_datamaster({
            "products": [{"product_code": "P1", "product_name": "产品1", "enabled": 1}],
            "parameters": [
                {"parameter_id": "has_cooling", "label": "是否液冷", "value_type": "boolean",
                 "search_type": "boolean", "min_value": -1, "max_value": 1, "display_order": 1,
                 "required": 0, "auto_adjustable": 1, "decimal_places": 0, "enabled": 1, "model_bound": 0},
                {"parameter_id": "cooling_flow", "label": "冷却液流量", "value_type": "number",
                 "search_type": "continuous", "min_value": -1, "max_value": 30, "display_order": 2,
                 "required": 0, "auto_adjustable": 1, "decimal_places": 2, "enabled": 1, "model_bound": 0},
            ],
            "parameter_groups": [],
            "tags": [], "tag_rules": [], "couplings": [], "constraints": [], "agreements": [],
        }, evaluate_agreements=False, sync_model_contract=False)

        saved = store.upsert_conditional_template({
            "controller": "has_cooling", "active_value": 1, "target": "cooling_flow",
            "inactive_value": -1, "active_min": 0, "active_max": 30,
        })
        assert saved["saved"]

        releases = ProductReleaseService(store, runtime)
        datamaster = DataMasterService(store, runtime)

        cloned = releases.clone_current()
        cloned_constraints = cloned["data"]["constraints"]
        assert len(cloned_constraints) == 2
        assert {r["rule_kind"] for r in cloned_constraints} == {"conditional_lower", "conditional_upper"}
        assert all(r.get("constraint_group") for r in cloned_constraints)
        assert all(r.get("template_metadata_json") for r in cloned_constraints)

        # Export maintenance workbook and import into a fresh draft.
        workbook = datamaster.export_snapshot(cloned["data"])
        draft = releases.create(product_code="P2", product_name="产品2")
        imported = releases.import_maintenance_workbook(draft["release_id"], "maintenance.xlsx", workbook)
        imported_constraints = imported["release"]["data"]["constraints"]
        assert len(imported_constraints) == 2
        assert {r["rule_kind"] for r in imported_constraints} == {"conditional_lower", "conditional_upper"}
        assert all(r.get("constraint_group") for r in imported_constraints)
        assert all(r.get("template_metadata_json") for r in imported_constraints)

        # Validate, activate, and confirm the store still recognises the template.
        validation = releases.validate(draft["release_id"])
        assert validation["valid"], validation["errors"]
        releases.activate(draft["release_id"])
        templates = store.conditional_templates()
        assert len(templates) == 1, templates
        group = templates[0]["constraint_group"]
        lower = next(r for r in templates[0]["rules"] if r["rule_kind"] == "conditional_lower")
        upper = next(r for r in templates[0]["rules"] if r["rule_kind"] == "conditional_upper")
        assert lower["constraint_group"] == upper["constraint_group"] == group
        assert lower["template_metadata_json"] and upper["template_metadata_json"]

        # Phase 5 projection must still see the template after the round-trip.
        rules = store.constraint_rows()
        definitions = store.parameter_map()
        projected = project_constraints(
            {"has_cooling": 0, "cooling_flow": 5}, definitions, rules,
        )
        assert "cooling_flow" in projected["inactive_parameters"], projected
        assert projected["parameters"]["cooling_flow"] == -1, projected["parameters"]
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "Product Release维护工作簿完整保留条件属性模板元数据"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
