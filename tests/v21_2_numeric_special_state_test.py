# -*- coding: utf-8 -*-
"""V21.2.x numeric special business-state regression contract."""
from __future__ import print_function

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator, filters_to_anchors  # noqa: E402
from app.range_diagnostics import build_range_diagnostics  # noqa: E402
from app.recommender import filter_match  # noqa: E402
from app.store import Store  # noqa: E402
from app.value_semantics import (  # noqa: E402
    business_display_value, is_special_value, normal_numeric_values,
    special_value_keys, special_value_label,
)


DEFINITION = {
    "parameter_id": "attr_special", "label": "锁定力", "unit": "N",
    "value_type": "number", "search_type": "continuous",
    "min_value": 10, "max_value": 50, "default_value": 25,
    "allowed_values_json": json.dumps([-1, 10, 20, 30]),
    "display_value_mapping_json": json.dumps({"-1": "无该属性"}, ensure_ascii=False),
    "special_value_keys_json": json.dumps(["-1"]),
    "auto_adjustable": 1, "decimal_places": 2,
}


class Runtime(object):
    def manifest(self):
        return {"calculation_available": False}

    def feature_roles(self):
        return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}

    def all_feature_specs(self):
        return []


def main():
    # A-D: display and canonical business state remain separate.
    assert special_value_keys(DEFINITION) == ["-1"]
    assert is_special_value(DEFINITION, -1)
    assert special_value_label(DEFINITION, -1) == "无该属性"
    assert business_display_value(-1, DEFINITION) == "无该属性"
    assert not is_special_value(DEFINITION, 25)
    assert normal_numeric_values(DEFINITION, [-1, 10, 20]) == [10, 20]

    # E-H: special equality is explicit; normal numeric/range comparisons never
    # treat -1 as a small continuous value. Legacy eq remains compatible.
    special_rule = {"parameter_id": "attr_special", "operator": "special_is", "value1": -1}
    assert filter_match({"attr_special": -1}, special_rule, DEFINITION)
    assert not filter_match({"attr_special": 20}, special_rule, DEFINITION)
    assert not filter_match({"attr_special": -1}, {"parameter_id": "attr_special", "operator": "lte", "value1": 20}, DEFINITION)
    assert filter_match({"attr_special": 15}, {"parameter_id": "attr_special", "operator": "lte", "value1": 20}, DEFINITION)
    assert not filter_match({"attr_special": -1}, {"parameter_id": "attr_special", "operator": "range_inside", "value1": 10, "value2": 20}, DEFINITION)
    assert filter_match({"attr_special": -1}, {"parameter_id": "attr_special", "operator": "eq", "value1": -1}, DEFINITION)

    # I-J: special state is an additional structural domain, not part of numeric
    # interpolation or snapping; an explicit special request is an immutable anchor.
    generator = HistorySeededGenerator(object(), object(), None)
    assert generator._normalized_allowed_values(DEFINITION) == [10, 20, 30]
    assert generator._attribute_neighbors(-1, DEFINITION)[:3] == [25, 10, 20]
    assert any(is_special_value(DEFINITION, value) for value in generator._attribute_neighbors(25, DEFINITION))
    params = {"attr_special": 25}
    anchors = filters_to_anchors([special_rule], {"attr_special": DEFINITION})
    locked, conflicts = generator._anchor_demands(params, anchors, {"attr_special": DEFINITION})
    assert not conflicts and locked["attr_special"] == -1 and params["attr_special"] == -1
    generator._round_values(params, {"attr_special": DEFINITION}, locked)
    assert params["attr_special"] == -1

    # K: special state is reported without ordinary business/schema/training range comparisons.
    diagnostics = build_range_diagnostics(
        {"attr_special": -1}, {"attr_special": DEFINITION},
        [{"key": "attr_special", "model_kind": "price", "min": 10, "max": 50,
          "training_min": 12, "training_max": 45}], {"attr_special": -1},
    )[0]
    assert diagnostics["special_state"] is True
    assert diagnostics["special_state_label"] == "无该属性"
    assert diagnostics["business_reference"] is None
    assert diagnostics["model_contracts"] == {} and diagnostics["training_ranges"] == {}
    assert diagnostics["outside_any_reference"] is False

    # L-M/Admin/migration: DB stores the new metadata independently, fingerprint
    # includes it, and runtime_parameters still owns Business -> Model encoding.
    db = ROOT / "data" / "_numeric_special_state_test.db"
    paths = (db, Path(str(db) + "-wal"), Path(str(db) + "-shm"))
    for path in paths:
        if path.exists():
            path.unlink()
    store = Store(db, ROOT / "data" / "virtual_protocol_dataset.csv", Runtime())
    try:
        assert "special_value_keys_json" in {row[1] for row in sqlite3.connect(str(db)).execute("PRAGMA table_info(parameter_definitions)")}
        store.admin_upsert("parameters", dict(DEFINITION))
        saved = store.parameter_map()["attr_special"]
        assert json.loads(saved["special_value_keys_json"]) == ["-1"]
        assert store.runtime_parameters({"attr_special": -1})["attr_special"] == -1
        restarted = Store(db, ROOT / "data" / "virtual_protocol_dataset.csv", Runtime())
        restarted_definitions = dict(
            (item["parameter_id"], item) for item in restarted.bootstrap()["parameters"]
        )
        restarted_saved = restarted_definitions["attr_special"]
        assert json.loads(restarted_saved["special_value_keys_json"]) == ["-1"]
        assert json.loads(restarted_saved["display_value_mapping_json"])["-1"] == "无该属性"
        before = store.generation_semantics_fingerprint()
        store.admin_upsert("parameters", dict(saved, special_value_keys_json="[]"))
        assert store.generation_semantics_fingerprint() != before
        try:
            store.admin_upsert("parameters", dict(saved, special_value_keys_json='{"-1":"bad"}'))
            raise AssertionError("special keys must be a JSON array")
        except ValueError:
            pass
    finally:
        for path in paths:
            if path.exists():
                path.unlink()

    # B-D/N: static wiring protects hybrid controls and canonical numeric submit
    # across the detail editor and both workbenches.
    app_js = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    price_js = (ROOT / "app" / "static" / "price.js").read_text(encoding="utf-8")
    effect_js = (ROOT / "app" / "static" / "effectiveness.js").read_text(encoding="utf-8")
    assert 'special_is","状态为' in app_js
    assert "numericHybridControl" in app_js and "data-special-value" in app_js
    assert "canonicalInputValue(parameter(el.dataset.key),el.dataset.specialValue)" in app_js
    for source in (price_js, effect_js):
        assert "numericControl" in source and "numeric-state-select" in source
        assert "Number(el.dataset.specialValue)" in source
    server_source = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
    assert '"Cache-Control","no-store, no-cache, must-revalidate"' in server_source

    print("PASS V21.2.x numeric special business-state semantics")


if __name__ == "__main__":
    main()
