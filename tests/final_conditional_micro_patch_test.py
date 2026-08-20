# -*- coding: utf-8 -*-
"""Malformed explicit rules block; stale model ranges only diagnose both contracts."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_compatibility import validate_conditional_relationship  # noqa: E402
from app.store import Store  # noqa: E402


class OfflineRuntime(object):
    schema = {"product_code": "P1", "product_name": "产品1"}

    def manifest(self):
        return {"calculation_available": False}

    def feature_roles(self):
        return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}

    def all_feature_specs(self):
        return []


class _MockEffectiveness(object):
    couplings = []
    coupling_edges = []
    learned_boundaries = []


class OnlineRuntime(OfflineRuntime):
    effectiveness = _MockEffectiveness()

    def manifest(self):
        return {
            "calculation_available": True,
            "effectiveness": {"model_version": "e1", "backend": "mock"},
            "price": {"model_version": "p1", "backend": "mock"},
            "execution_mode": "in_process_json_models",
            "contract_valid": True,
            "product_code": "P1",
        }

    def model_feature_specs(self):
        return [
            {"key": "attr_004", "model_kind": "effectiveness", "min": -1, "max": 30},
            {"key": "attr_004", "model_kind": "price", "min": 0, "max": 30},
        ]


def _v2_metadata(controller, target, then_model_value, range_min, range_max):
    return {
        "template": "conditional_applicability_v2",
        "controller": controller, "target": target,
        "when": {"operator": "equals", "business_value": "无", "model_value": 0},
        "then": {"mode": "not_applicable", "business_value": "无该属性", "model_value": then_model_value},
        "otherwise": {"mode": "range", "min": range_min, "max": range_max},
    }


def main():
    # Business error (min > max) must block even when model services are offline.
    db_path = ROOT / "data" / "_final_conditional_micro_patch_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", OfflineRuntime())
    try:
        store.replace_from_datamaster({
            "products": [{"product_code": "P1", "product_name": "产品1", "enabled": 1}],
            "parameters": [
                {"parameter_id": "attr_001", "label": "控制器", "value_type": "boolean",
                 "search_type": "boolean", "min_value": -1, "max_value": 1, "display_order": 1},
                {"parameter_id": "attr_004", "label": "从属", "value_type": "number",
                 "search_type": "continuous", "min_value": 0, "max_value": 30, "display_order": 2},
            ],
            "parameter_groups": [], "tags": [], "tag_rules": [], "couplings": [],
            "constraints": [], "agreements": [],
        }, evaluate_agreements=False, sync_model_contract=False)

        bad = _v2_metadata("attr_001", "attr_004", 0, 10, 1)
        try:
            store.upsert_conditional_template(bad)
            raise AssertionError("business error should block even offline")
        except ValueError:
            pass
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    # Model conflict: shared target must be checked against both model contracts.
    compat = validate_conditional_relationship(
        _v2_metadata("attr_001", "attr_004", -1, 0, 30),
        {"attr_004": {"parameter_id": "attr_004", "min_value": -10, "max_value": 30}},
        OnlineRuntime().model_feature_specs(),
    )
    assert compat["business_errors"] == [], compat["business_errors"]
    assert compat["model_errors"] == [], compat["model_errors"]
    assert compat["warnings"], compat["warnings"]
    assert "effectiveness" in compat["model_compatibility"], compat["model_compatibility"]
    assert "price" in compat["model_compatibility"], compat["model_compatibility"]
    assert compat["model_compatibility"]["price"]["compatible"] is False, compat["model_compatibility"]

    # Online Store save with a range mismatch is allowed and returns diagnostics.
    db_path2 = ROOT / "data" / "_final_conditional_micro_patch_online_test.db"
    for candidate in (db_path2, Path(str(db_path2) + "-wal"), Path(str(db_path2) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store2 = Store(db_path2, ROOT / "data" / "virtual_protocol_dataset.csv", OnlineRuntime())
    try:
        store2.replace_from_datamaster({
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
        saved = store2.upsert_conditional_template(_v2_metadata("attr_001", "attr_004", -1, 0, 30))
        assert saved["saved"] is True
        assert saved["compatibility"]["model_compatibility"]["price"]["compatible"] is False
    finally:
        for candidate in (db_path2, Path(str(db_path2) + "-wal"), Path(str(db_path2) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "非法显式规则阻止保存，双模型范围差异仅诊断"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
