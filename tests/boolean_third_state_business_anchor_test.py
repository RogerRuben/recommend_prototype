# -*- coding: utf-8 -*-
"""Boolean third state stays business-canonical until Store runtime encoding."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator, filters_to_anchors  # noqa: E402
from app.recommender import filter_match  # noqa: E402
from app.store import Store  # noqa: E402


class Runtime(object):
    def manifest(self): return {"calculation_available": False}
    def feature_roles(self): return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}
    def all_feature_specs(self): return []


definition = {"parameter_id": "state", "label": "状态", "value_type": "boolean", "search_type": "boolean",
              "allowed_values_json": '[0,1,"无该属性"]', "model_value_mapping_json": '{"0":0,"1":1,"无该属性":-1}',
              "auto_adjustable": 1}
anchors = filters_to_anchors([{"parameter_id": "state", "operator": "boolean_is", "value1": "无该属性"}], {"state": definition})
params = {"state": 1}
locked, conflicts = HistorySeededGenerator(object(), object(), None)._anchor_demands(params, anchors, {"state": definition})
assert not conflicts and locked["state"] == params["state"] == "无该属性", (locked, conflicts)
assert filter_match(params, {"parameter_id": "state", "operator": "boolean_is", "value1": "无该属性"}, definition)

db = ROOT / "data" / "_third_state_business_anchor.db"
paths = (db, Path(str(db) + "-wal"), Path(str(db) + "-shm"))
for path in paths:
    if path.exists(): path.unlink()
store = Store(db, ROOT / "data" / "virtual_protocol_dataset.csv", Runtime())
try:
    store.admin_upsert("parameters", definition)
    assert store.runtime_parameters(params)["state"] == -1
finally:
    for path in paths:
        if path.exists(): path.unlink()
print("PASS boolean third state business anchor")
