# -*- coding: utf-8 -*-
"""Legacy DataMaster without 指标分组 sheet must parse and derive groups."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_master import SHEETS, DataMasterService  # noqa: E402
from app.store import Store  # noqa: E402
from app.xlsx_utils import write_workbook_bytes  # noqa: E402


class StubRuntime(object):
    def manifest(self):
        return {"calculation_available": False}

    def feature_roles(self):
        return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}

    def all_feature_specs(self):
        return []


def main():
    db_path = ROOT / "data" / "_datamaster_optional_sheet_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    service = DataMasterService(store, StubRuntime())
    try:
        product_header = SHEETS["成品信息"]
        parameter_header = SHEETS["指标定义"]
        sheets = [
            ("成品信息", [product_header, ["P1", "产品", "", "是"]]),
            ("指标定义", [
                parameter_header,
                ["A1", "A1", "性能属性", "", "数值", "连续数值", "0", "10", "中性", "", "", "", "是", "是", "2", "1", "是", ""],
                ["A2", "A2", "性能属性", "", "数值", "连续数值", "0", "10", "中性", "", "", "", "是", "是", "2", "2", "是", ""],
            ]),
            ("标签字典", [SHEETS["标签字典"]]),
            ("标签规则", [SHEETS["标签规则"]]),
            ("耦合关系", [SHEETS["耦合关系"]]),
            ("约束规则", [SHEETS["约束规则"]]),
            ("历史协议", [SHEETS["历史协议"]]),
            ("模型字段绑定", [SHEETS["模型字段绑定"]]),
        ]
        # Deliberately no 指标分组 sheet: this is a legacy workbook.
        data = write_workbook_bytes(sheets)
        report = service.parse("legacy.xlsx", data)
        assert report["valid"], report["errors"]
        groups = report["data"]["parameter_groups"]
        names = [g["group_name"] for g in groups]
        assert "性能属性" in names, names
        assert "其他" in names, names
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "旧DataMaster缺指标分组sheet可解析并自动推导分组"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
