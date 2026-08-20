# -*- coding: utf-8 -*-
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.store import Store

class Runtime:
    def manifest(self): return {"calculation_available": False}
    def feature_roles(self): return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}
    def all_feature_specs(self): return []

db = ROOT / "data" / "_display_backend_identity.db"
for p in (db, Path(str(db)+"-wal"), Path(str(db)+"-shm")):
    if p.exists(): p.unlink()
s = Store(db, ROOT / "data" / "virtual_protocol_dataset.csv", Runtime())
try:
    s.admin_upsert("parameters", {"parameter_id":"xx","label":"XX","value_type":"boolean","allowed_values_json":"[0,1]","display_value_mapping_json":"{\"0\":\"无\",\"1\":\"有\"}"})
    assert s.runtime_parameters({"xx": 1})["xx"] == 1
    assert s.business_parameters({"xx": 1}, {"xx": 1})["xx"] == 1
finally:
    for p in (db, Path(str(db)+"-wal"), Path(str(db)+"-shm")):
        if p.exists(): p.unlink()
print("PASS display mapping does not change backend values")
