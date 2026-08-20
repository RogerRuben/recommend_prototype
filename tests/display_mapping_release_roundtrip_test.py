# -*- coding: utf-8 -*-
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.store import Store
from app.product_releases import ProductReleaseService

class Runtime:
    schema={"product_code":"P","product_name":"P"}
    def manifest(self): return {"calculation_available":False}
    def feature_roles(self): return {"shared_features":[],"effectiveness_only_features":[],"price_only_features":[]}
    def all_feature_specs(self): return []

db=ROOT/"data"/"_display_release_roundtrip.db"; paths=(db,Path(str(db)+"-wal"),Path(str(db)+"-shm"))
for p in paths:
    if p.exists(): p.unlink()
s=Store(db,ROOT/"data"/"virtual_protocol_dataset.csv",Runtime())
try:
    s.replace_from_datamaster({"products":[{"product_code":"P","product_name":"P"}],"parameters":[{"parameter_id":"xx","label":"XX","value_type":"boolean","allowed_values_json":"[0,1]","display_value_mapping_json":json.dumps({"0":123,"1":456},ensure_ascii=False)}],"parameter_groups":[{"group_name":"其他"}],"tags":[],"tag_rules":[],"couplings":[],"constraints":[],"agreements":[]},evaluate_agreements=False,sync_model_contract=False)
    svc=ProductReleaseService(s,Runtime()); draft=svc.clone_current(); raw=svc.export_package(draft["release_id"]); imported=svc.import_package(raw)
    mapping=json.loads(imported["data"]["parameters"][0]["display_value_mapping_json"])
    assert mapping=={"0":"123","1":"456"},mapping
    validation=svc.validate(imported["release_id"])
    assert validation["valid"],validation
    svc.activate(imported["release_id"])
    assert json.loads(s.parameter_map()["xx"]["display_value_mapping_json"])["1"]=="456"
finally:
    for p in paths:
        if p.exists(): p.unlink()
print("PASS Product Release preserves display mapping")
