# -*- coding: utf-8 -*-
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.value_semantics import business_display_value
from app.model_service_client import build_model_request
from app.store import Store

a={"value_type":"boolean","display_value_mapping_json":"{\"0\":\"无\",\"1\":\"有\"}"}
b={"value_type":"boolean","display_value_mapping_json":"{\"0\":\"未配置\",\"1\":\"已配置\"}"}
assert business_display_value(1,a) != business_display_value(1,b)
assert build_model_request("price", {"xx":1})["parameters"] == build_model_request("price", {"xx":1})["parameters"] == {"xx":1}

class Runtime:
    def manifest(self): return {"calculation_available":False}
    def feature_roles(self): return {"shared_features":[],"effectiveness_only_features":[],"price_only_features":[]}
    def all_feature_specs(self): return []
db=ROOT/"data"/"_display_model_identity.db"; paths=(db,Path(str(db)+"-wal"),Path(str(db)+"-shm"))
for p in paths:
    if p.exists(): p.unlink()
s=Store(db,ROOT/"data"/"virtual_protocol_dataset.csv",Runtime())
try:
    s.admin_upsert("parameters",{"parameter_id":"xx","label":"XX","value_type":"boolean","allowed_values_json":"[0,1]","display_value_mapping_json":a["display_value_mapping_json"]})
    before=(s.runtime_parameters({"xx":1}),s.generation_semantics_fingerprint())
    s.admin_upsert("parameters",dict(s.parameter_map()["xx"],display_value_mapping_json=b["display_value_mapping_json"]))
    after=(s.runtime_parameters({"xx":1}),s.generation_semantics_fingerprint())
    assert before==after,(before,after)
finally:
    for p in paths:
        if p.exists(): p.unlink()
print("PASS display labels do not change model request")
