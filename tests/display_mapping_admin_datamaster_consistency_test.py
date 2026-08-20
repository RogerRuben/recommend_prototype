# -*- coding: utf-8 -*-
"""Admin persistence and DataMaster round-trip share one canonical mapping."""
import json
import io
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_master import DataMasterService  # noqa: E402
from app.store import Store  # noqa: E402


class Runtime(object):
    schema = {"product_code": "P", "product_name": "P"}
    def manifest(self): return {"calculation_available": False}
    def feature_roles(self): return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}
    def all_feature_specs(self): return []


db = ROOT / "data" / "_display_admin_dm_consistency.db"
paths = (db, Path(str(db) + "-wal"), Path(str(db) + "-shm"))
for path in paths:
    if path.exists(): path.unlink()
store = Store(db, ROOT / "data" / "virtual_protocol_dataset.csv", Runtime())
try:
    store.admin_upsert("parameters", {"parameter_id": "xx", "label": "XX", "value_type": "boolean",
                                      "allowed_values_json": "[0,1]",
                                      "display_value_mapping_json": {"0": 123, "1": "有"}})
    saved = json.loads(store.parameter_map()["xx"]["display_value_mapping_json"])
    assert saved == {"0": "123", "1": "有"}
    service = DataMasterService(store, Runtime())
    workbook = service.export_current()
    with zipfile.ZipFile(io.BytesIO(workbook)) as archive:
        worksheet_xml = "\n".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist() if name.startswith("xl/worksheets/sheet")
        )
    assert "前端显示映射(JSON)" in worksheet_xml
    assert "只修改界面显示" in worksheet_xml
    report = service.parse("current.xlsx", workbook)
    assert report["valid"], report["errors"]
    exported = json.loads(report["data"]["parameters"][0]["display_value_mapping_json"])
    assert exported == saved
finally:
    for path in paths:
        if path.exists(): path.unlink()
print("PASS display mapping admin/DataMaster consistency")
