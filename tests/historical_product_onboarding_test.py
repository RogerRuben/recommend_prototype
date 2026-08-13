# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_master import DataMasterService
from app.model_runtime import IntegratedModelRuntime
from app.product_releases import ProductReleaseService
from app.store import Store
from app.xlsx_utils import read_workbook_bytes, write_workbook_bytes


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("PASS - " + message)


def sample_csv():
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow([
        "成品编号", "成品名称", "价格(万元)", "是否自诊断", "类型编码",
        "额定载荷(N)", "材料", "说明文字",
    ])
    writer.writerows([
        ["LOCK-001", "舱门锁样本1", "10.5", "1", "0", "1000", "铝合金", "首批"],
        ["LOCK-002", "舱门锁样本2", "12", "0", "1", "1200", "钛合金", "改进型"],
        ["LOCK-003", "舱门锁样本3", "/", "1", "0", "-1", "\\", "试验型"],
        ["LOCK-004", "舱门锁样本4", "14", "0", "1", "1400", "铝合金", ""],
    ])
    return ("\ufeff" + out.getvalue()).encode("utf-8")


def main():
    temp_root = Path(tempfile.mkdtemp(prefix="ipdemo_history_"))
    try:
        business_product_code = "AIRCRAFT_DOOR_LOCK_DEMO"
        runtime = IntegratedModelRuntime(ROOT / "models")
        store = Store(
            temp_root / "data" / "history_test.db",
            ROOT / "data" / "virtual_protocol_dataset.csv",
            runtime,
            temp_root / "backups",
        )
        service = ProductReleaseService(store, runtime)
        report = service.analyze_history(
            "航空舱门锁历史成品.csv", sample_csv(), business_product_code,
            "航空舱门锁", ["-1", "\\", "/"],
        )
        check(report["row_count"] == 4 and report["attribute_count"] == 5, "普通历史宽表自动识别成品行和属性列")
        inferred = dict((item["source_header"], item) for item in report["inferred_parameters"])
        check(inferred["是否自诊断"]["value_type"] == "boolean", "具有是否语义的0/1字段自动识别为有无")
        check(
            inferred["类型编码"]["value_type"] == "enum"
            and inferred["类型编码"]["confidence"] == "needs_confirmation",
            "含义不明确的0/1字段保留为枚举并要求人工确认",
        )
        check(
            not inferred["额定载荷(N)"]["required"] and not inferred["材料"]["required"]
            and not inferred["说明文字"]["required"],
            "任一历史成品缺失属性时自动标记为非必填",
        )
        params = report["data"]["parameters"]
        param_by_header = dict((item["inference"]["source_header"], item) for item in params)
        third = report["data"]["agreements"][2]
        check(
            param_by_header["额定载荷(N)"]["parameter_id"] not in third["params"]
            and param_by_header["材料"]["parameter_id"] not in third["params"],
            "自定义缺失符在协议参数中保留为空而不是写入伪值",
        )

        created = service.create_from_history(
            "航空舱门锁历史成品.csv", sample_csv(), business_product_code,
            "航空舱门锁", "-1,\\,/",
        )
        release = created["release"]
        check(release["status"] == "draft" and store.is_empty(), "自动推断结果仅进入待发布草稿，不修改运行数据库")

        workbook = DataMasterService(store, runtime).export_snapshot(release["data"])
        sheets = read_workbook_bytes(workbook)
        check("自动推断报告" in sheets and len(sheets["自动推断报告"]) == 6, "维护工作簿包含逐字段自动推断报告")
        check(len(sheets["历史协议"]) == 5 and len(sheets["指标定义"]) == 6, "维护工作簿预填历史成品和推断属性")

        imported = service.import_maintenance_workbook(
            release["release_id"], "航空舱门锁_维护工作簿.xlsx", workbook,
        )
        check(
            len(imported["release"]["data"]["agreements"]) == 4
            and len(imported["release"]["data"]["parameters"]) == 5,
            "部分信息可空的维护工作簿能够回导同一草稿继续填写",
        )
        broken_sheets = read_workbook_bytes(workbook)
        broken_sheets["成品信息"][1][1] = "不应残留的半导入名称"
        broken_sheets["指标定义"][1][0] = ""
        broken = write_workbook_bytes(list(broken_sheets.items()))
        try:
            service.import_maintenance_workbook(release["release_id"], "错误工作簿.xlsx", broken)
            raise AssertionError("错误工作簿应被拒绝")
        except ValueError:
            restored = service.get(release["release_id"])
            check(restored["product_name"] == "航空舱门锁", "工作簿中途失败时草稿内容整体回滚")
        validation = service.validate(release["release_id"])
        check(
            validation["valid"] and not validation["model_contract_checked"],
            "业务成品与当前HTTP模型成品不同仍可通过本地业务结构检查",
        )
        activation = service.activate(release["release_id"])
        snapshot = store.admin_snapshot()
        check(
            activation["activated"] and not activation["model_services_called"]
            and snapshot["products"][0]["product_code"] == business_product_code
            and all(item["capability_score"] is None for item in snapshot["agreements"]),
            "切换业务成品不调用双模型，历史数据保留为待计算状态",
        )
        if len(sys.argv) > 1:
            output = Path(sys.argv[1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(workbook)
            print("WORKBOOK - " + str(output))
        print(json.dumps({"status": "PASS", "checks": 12}, ensure_ascii=False))
    finally:
        shutil.rmtree(str(temp_root), ignore_errors=True)


if __name__ == "__main__":
    main()
