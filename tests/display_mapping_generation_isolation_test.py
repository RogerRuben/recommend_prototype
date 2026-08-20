# -*- coding: utf-8 -*-
"""Changing display text cannot alter generator, persistence or model values."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator, filters_to_anchors  # noqa: E402
from app.store import Store  # noqa: E402
from app.value_semantics import business_display_value  # noqa: E402


class Runtime(object):
    def manifest(self): return {"calculation_available": False}
    def feature_roles(self): return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}
    def all_feature_specs(self): return []


db = ROOT / "data" / "_display_generation_isolation.db"
paths = (db, Path(str(db) + "-wal"), Path(str(db) + "-shm"))
for path in paths:
    if path.exists(): path.unlink()
store = Store(db, ROOT / "data" / "virtual_protocol_dataset.csv", Runtime())
try:
    base = {"parameter_id": "xx", "label": "XX", "value_type": "boolean", "search_type": "boolean",
            "allowed_values_json": "[0,1]", "auto_adjustable": 1,
            "display_value_mapping_json": {"0": "无", "1": "有"}}
    store.admin_upsert("parameters", base)
    before_def = store.parameter_map()["xx"]
    before_fingerprint = store.generation_semantics_fingerprint()
    before_bounds = filters_to_anchors([{"parameter_id": "xx", "operator": "boolean_is", "value1": 1}], {"xx": before_def})
    before_params = {"xx": 0}
    HistorySeededGenerator(object(), object(), None)._anchor_demands(before_params, before_bounds, {"xx": before_def})
    before_runtime = store.runtime_parameters(before_params)

    updated = dict(before_def, display_value_mapping_json={"0": 123, "1": 456})
    store.admin_upsert("parameters", updated)
    after_def = store.parameter_map()["xx"]
    assert json.loads(after_def["display_value_mapping_json"]) == {"0": "123", "1": "456"}
    after_bounds = filters_to_anchors([{"parameter_id": "xx", "operator": "boolean_is", "value1": 1}], {"xx": after_def})
    after_params = {"xx": 0}
    HistorySeededGenerator(object(), object(), None)._anchor_demands(after_params, after_bounds, {"xx": after_def})
    assert before_bounds == after_bounds
    assert before_params == after_params == {"xx": 1}
    assert before_runtime == store.runtime_parameters(after_params) == {"xx": 1}
    assert before_fingerprint == store.generation_semantics_fingerprint()
    assert business_display_value(1, before_def) == "有"
    assert business_display_value(1, after_def) == "456"
finally:
    for path in paths:
        if path.exists(): path.unlink()
print("PASS display mapping generation isolation")
