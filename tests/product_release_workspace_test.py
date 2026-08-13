# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.model_runtime import IntegratedModelRuntime
from app.product_releases import ProductReleaseService
from app.store import Store


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("PASS - " + message)


def main():
    temp_root = Path(tempfile.mkdtemp(prefix="ipdemo_release_"))
    try:
        runtime = IntegratedModelRuntime(ROOT / "models")
        store = Store(
            temp_root / "data" / "release_test.db",
            ROOT / "data" / "virtual_protocol_dataset.csv",
            runtime,
            temp_root / "backups",
        )
        service = ProductReleaseService(store, runtime)
        legacy_path = temp_root / "legacy_without_release_table.db"
        shutil.copy2(str(store.db_path), str(legacy_path))
        legacy_conn = sqlite3.connect(str(legacy_path))
        try:
            legacy_conn.execute("DROP TABLE product_releases")
            legacy_conn.commit()
        finally:
            legacy_conn.close()
        legacy_check = store.integrity_check(legacy_path)
        check(legacy_check["ok"] and "product_releases" in legacy_check["migratable_tables"], "旧版数据库可通过迁移补建发布工作区")

        release = service.create()
        check(store.is_empty(), "创建待发布草稿不会修改当前运行主数据")
        check(len(release["data"]["parameters"]) == 0, "默认空白草稿不读取当前模型字段")
        service.set_section(release["release_id"], "parameters", service._parameter_skeleton())
        release = service.get(release["release_id"])

        tag_csv = (
            "\ufeff标签编号,标签名称,标签分组,匹配权重,生成判定方式,是否启用\r\n"
            "TAG_FAST,快速响应,能力,1.5,规则判定,是\r\n"
        ).encode("utf-8")
        preview = service.parse_module(release["release_id"], "tags", "tags.csv", tag_csv)
        check(preview["valid_count"] == 1 and preview["invalid_count"] == 0, "标签模块可独立解析CSV")
        service.stage_module(release["release_id"], "tags", preview)
        check(len(service.get(release["release_id"])["data"]["tags"]) == 1, "独立模块只暂存到发布草稿")

        data = service.get(release["release_id"])["data"]
        data["tag_rules"] = [{
            "rule_id": "RULE_BAD", "tag_id": "TAG_UNKNOWN",
            "parameter_id": data["parameters"][0]["parameter_id"],
            "operator": "gte", "value1": "1", "value2": "",
            "rule_group": "default", "enabled": 1,
        }]
        service.set_section(release["release_id"], "tag_rules", data["tag_rules"])
        report = service.validate(release["release_id"])
        check(not report["valid"] and any("不存在的标签" in item for item in report["errors"]), "跨模块引用延迟到发布校验处理")

        data["tag_rules"][0]["tag_id"] = "TAG_FAST"
        service.set_section(release["release_id"], "tag_rules", data["tag_rules"])
        data["parameters"].append({
            "parameter_id": "business_note", "label": "业务备注", "unit": "",
            "value_type": "text", "min_value": None, "max_value": None,
            "preference": "neutral", "description": "非模型业务扩展字段",
            "adjustment_hint": "", "allowed_values_json": None, "search_type": "auto",
            "required": 0, "auto_adjustable": 0, "decimal_places": 0,
            "display_order": 999, "enabled": 1, "model_bound": 1,
        })
        service.set_section(release["release_id"], "parameters", data["parameters"])
        report = service.validate(release["release_id"])
        check(report["valid"] and not report["model_contract_checked"], "业务扩展字段可保留且数据检查完全不读取模型契约")

        result = service.activate(release["release_id"])
        check(
            result["activated"] and result["commit_result"]["backup"]
            and not result["model_services_called"] and not result["commit_result"]["agreements_evaluated"],
            "切换前自动备份，且业务数据写入不调用当前模型服务",
        )
        active = service.get(release["release_id"])
        store.sync_model_schema()
        check(active["status"] == "active" and not store.is_empty() and store.parameter_map()["business_note"]["model_bound"] == 0, "激活和再次同步后业务扩展字段仍被保留")

        cloned = service.clone_current()
        check(
            cloned["data"]["products"][0]["product_code"] == active["product_code"]
            and len(cloned["data"]["parameters"]) == len(store.parameter_map()),
            "当前运行数据可一键完整复制为待发布草稿",
        )
        package_bytes = service.export_package(cloned["release_id"])
        imported = service.import_package(package_bytes)
        check(imported["data"] == cloned["data"] and imported["status"] == "draft", "完整草稿可导出并在断网环境重新导入")
        package = json.loads(package_bytes.decode("utf-8"))
        package["data"]["products"][0]["product_name"] = "被篡改"
        try:
            service.import_package(json.dumps(package, ensure_ascii=False).encode("utf-8"))
            raise AssertionError("篡改发布包应被拒绝")
        except ValueError as exc:
            check("完整性校验失败" in str(exc), "离线发布包使用SHA256检查传输完整性")
        templates = [service.module_template(cloned["release_id"], section) for section in (
            "products", "parameters", "tags", "tag_rules", "couplings", "constraints", "agreements"
        )]
        check(all(item.startswith(b"\xef\xbb\xbf") for item in templates), "七个业务模块均可独立下载UTF-8 CSV模板")
        service.delete(imported["release_id"])
        service.delete(cloned["release_id"])

        mismatch = service.create("ANOTHER_PRODUCT", "新成品", seed_schema=True)
        mismatch_report = service.validate(mismatch["release_id"])
        check(
            mismatch_report["valid"] and not mismatch_report["model_contract_checked"],
            "新成品草稿不再与当前HTTP模型成品代号比较",
        )
        service.delete(mismatch["release_id"])

        print(json.dumps({"status": "PASS", "checks": 14}, ensure_ascii=False))
    finally:
        shutil.rmtree(str(temp_root), ignore_errors=True)


if __name__ == "__main__":
    main()
