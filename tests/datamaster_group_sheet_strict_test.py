# -*- coding: utf-8 -*-
"""When a group master sheet exists, unknown parameter_group values must not be auto-created."""
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
    schema = {"product_code": "P1", "product_name": "产品1"}

    def manifest(self):
        return {"calculation_available": False}

    def feature_roles(self):
        return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}

    def all_feature_specs(self):
        return []


def main():
    db_path = ROOT / "data" / "_datamaster_group_sheet_strict_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    service = DataMasterService(store, StubRuntime())
    try:
        parameter_header = SHEETS["指标定义"]
        group_header = SHEETS["指标分组"]
        sheets = [
            ("成品信息", [SHEETS["成品信息"], ["P1", "产品", "", "是"]]),
            ("指标定义", [
                parameter_header,
                ["A1", "A1", "环境 属性", "", "数值", "连续数值", "0", "10", "中性", "", "", "", "是", "是", "2", "1", "是", ""],
            ]),
            ("指标分组", [group_header, ["环境属性", "1", "", "是", "否"]]),
            ("标签字典", [SHEETS["标签字典"]]),
            ("标签规则", [SHEETS["标签规则"]]),
            ("耦合关系", [SHEETS["耦合关系"]]),
            ("约束规则", [SHEETS["约束规则"]]),
            ("历史协议", [SHEETS["历史协议"]]),
            ("模型字段绑定", [SHEETS["模型字段绑定"]]),
        ]
        data = write_workbook_bytes(sheets)
        report = service.parse("strict.xlsx", data)
        group_names = [g["group_name"] for g in report["data"]["parameter_groups"]]
        assert "环境 属性" not in group_names, group_names
        assert "环境属性" in group_names, group_names
        assert report["valid"] is False, report["errors"]
        assert any("环境 属性" in e for e in report["errors"]), report["errors"]
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "存在分组sheet时未知分组不会被自动创建，而是校验报错"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
