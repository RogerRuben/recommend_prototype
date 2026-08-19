# -*- coding: utf-8 -*-
"""DataMaster 指标定义 validations must align with the current column layout."""
from __future__ import print_function

import io
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_master import DataMasterService  # noqa: E402
from app.store import Store  # noqa: E402


class StubRuntime(object):
    schema = {"product_code": "P1", "product_name": "产品1"}

    def manifest(self):
        return {"calculation_available": False}

    def feature_roles(self):
        return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}

    def all_feature_specs(self):
        return []


def _sheet_xml_by_name(data, sheet_name):
    ns = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        relmap = dict((rel.attrib["Id"], rel.attrib["Target"]) for rel in rels)
        for sheet in workbook.findall("m:sheets/m:sheet", ns):
            if sheet.attrib.get("name") == sheet_name:
                rid = sheet.attrib.get("{%s}id" % ns["r"])
                target = relmap[rid].lstrip("/")
                if not target.startswith("xl/"):
                    target = "xl/" + target
                return zf.read(target).decode("utf-8")
    raise AssertionError("sheet not found: %s" % sheet_name)


def _workbook_xml(data):
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        return zf.read("xl/workbook.xml").decode("utf-8")


def main():
    db_path = ROOT / "data" / "_datamaster_validation_alignment_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    try:
        store.replace_from_datamaster({
            "products": [{"product_code": "P1", "product_name": "产品1", "enabled": 1}],
            "parameters": [
                {"parameter_id": "A1", "label": "A1", "parameter_group": "环境属性", "value_type": "number",
                 "search_type": "auto", "min_value": 0, "max_value": 10, "display_order": 1},
            ],
            "parameter_groups": [{"group_name": "环境属性", "display_order": 1, "description": "", "enabled": 1, "default_collapsed": 0}],
            "tags": [], "tag_rules": [], "couplings": [], "constraints": [], "agreements": [],
        }, evaluate_agreements=False, sync_model_contract=False)

        service = DataMasterService(store, StubRuntime())
        data = service.export_current()
        sheet2 = _sheet_xml_by_name(data, "指标定义")
        workbook = _workbook_xml(data)

        # Defined name for the parameter-group dropdown exists.
        assert "DM_PARAMETER_GROUPS" in workbook, "DM_PARAMETER_GROUPS defined name missing"

        checks = [
            ('C2:C1000', 'DM_PARAMETER_GROUPS'),
            ('E2:E1000', 'DM_VALUE_TYPES'),
            ('F2:F1000', 'DM_SEARCH_TYPES'),
            ('I2:I1000', 'DM_PREFERENCES'),
            ('M2:M1000', 'DM_YES_NO'),
            ('N2:N1000', 'DM_YES_NO'),
            ('Q2:Q1000', 'DM_YES_NO'),
        ]
        for sqref, formula in checks:
            assert ('sqref="%s"' % sqref) in sheet2, "missing sqref %s" % sqref
            assert ('formula1>%s</formula1>' % formula) in sheet2, "missing formula %s for %s" % (formula, sqref)
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "DataMaster指标定义校验列与当前列位置对齐，分组下拉已生成"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
