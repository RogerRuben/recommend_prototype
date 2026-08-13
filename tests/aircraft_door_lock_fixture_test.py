# -*- coding: utf-8 -*-
"""Acceptance test for the aircraft cabin-door-lock data-staff fixture."""
from __future__ import print_function

import json
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.data_master import DataMasterService
from app.model_service_client import ModelServiceGateway, ServiceBackedRuntime
from app.store import Store
from services.effectiveness_service.app import EffectivenessService, backend_from_package
from services.price_service.app import PriceService
from tools.product_delivery import verify_delivery


OUT = ROOT / "outputs" / "aircraft_door_lock_data_staff_20260801"
PRODUCT_CODE = "AIRCRAFT_CABIN_DOOR_LOCK_DEMO"
REPORT = ROOT / "logs" / "aircraft_door_lock_fixture_report.json"


def check(condition, name, report, detail=None):
    if not condition:
        raise AssertionError("%s: %s" % (name, detail) if detail is not None else name)
    item = {"name": name, "status": "PASS"}
    if detail is not None:
        item["detail"] = detail
    report["checks"].append(item)


class DirectGateway(object):
    fallback = False

    def __init__(self, price, effectiveness):
        self.price = price
        self.effectiveness = effectiveness
        self.product_code = PRODUCT_CODE

    def evaluate(self, params):
        envelope = {"request_id": "DIRECT-TEST", "product_code": PRODUCT_CODE, "parameters": dict(params)}
        price = self.price.handle_post("/api/v1/predict", envelope)
        effect = self.effectiveness.handle_post("/api/v1/evaluate", envelope)
        return ModelServiceGateway._merge(envelope, price, effect)

    def evaluate_batch(self, items):
        return [self.evaluate(item.get("parameters") or item.get("params") or {}) for item in items]


def main():
    report = {"test": "aircraft_door_lock_fixture", "started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "python": sys.version, "checks": [], "status": "RUNNING"}
    try:
        import numpy
        import openpyxl
        import sklearn
        import xgboost
        check(sys.version_info[:2] == (3, 8), "使用独立Python 3.8环境", report)
        check((numpy.__version__, openpyxl.__version__, sklearn.__version__, xgboost.__version__) == ("1.24.4", "3.1.3", "1.3.2", "1.7.6"), "固定模型依赖版本正确", report)

        manifest = json.loads((OUT / "fixture_manifest.json").read_text(encoding="utf-8"))
        delivery = Path(manifest["delivery"]["package"])
        verified = verify_delivery(delivery, expected_sha256=manifest["delivery"]["sha256"])
        check(verified["manifest"]["formal"] is True, "统一交付包使用双正式后端", report)
        check(verified["manifest"]["cross_contract"]["valid"] is True, "价格、效能与业务数据跨契约一致", report)
        check(verified["manifest"]["product_code"] == PRODUCT_CODE, "成品代号稳定一致", report)
        check(manifest["counts"] == {"price_training_rows": 640, "effectiveness_history_rows": 48, "parameters": 19, "tags": 10, "tag_rules": 10, "couplings": 7, "constraints": 3}, "数据量和治理对象数量符合设计", report, manifest["counts"])

        price = PriceService(OUT / "price" / "price_native_bundle.pkl")
        effect = EffectivenessService(backend_from_package(OUT / "effectiveness_runtime" / "effectiveness_runtime_manifest.json"))
        price_schema, effect_schema = price.schema(), effect.schema()
        check(price_schema["required_modules"] == ["sklearn", "xgboost"], "价格模型包含真实sklearn和XGBoost对象", report)
        check(price_schema["model_count"] == 4, "价格模型四成员集成已加载", report)
        check(effect.health()["backend"] == "original_effectiveness_runtime", "效能模型加载原ProjectApp与专家State", report)
        effect_by_key = dict((item["field_name"], item) for item in effect_schema["fields"])
        check(effect_by_key["emergency_release"]["dtype"] == "boolean", "效能Schema正确声明布尔字段", report)
        check(effect_by_key["protection_grade"]["dtype"] == "ip_grade", "效能Schema正确声明IP字段", report)

        business = json.loads((OUT / "business" / "product_release.iprelease.json").read_text(encoding="utf-8"))
        sample = dict(business["data"]["agreements"][0]["params"])
        gateway = DirectGateway(price, effect)
        runtime = ServiceBackedRuntime(gateway, schemas={"price": price_schema, "effectiveness": effect_schema})
        evaluation = runtime.evaluate(sample)
        check(evaluation["predicted_price_wan"] > 0, "训练价格模型可完成预测", report, evaluation["predicted_price_wan"])
        check(evaluation["capability_score"] >= 0 and 0 <= evaluation["feasibility_probability"] <= 1, "效能模型可完成评分且允许优于协议时超过100分", report)

        with tempfile.TemporaryDirectory(prefix="adl_dm_", dir=str(ROOT / "runtime")) as temp:
            temp_root = Path(temp)
            store = Store(temp_root / "data" / "protocol_demo.db", ROOT / "data" / "virtual_protocol_dataset.csv", runtime, backup_dir=temp_root / "backups")
            data_master = DataMasterService(store, runtime)
            workbook_path = OUT / "航空舱门锁_DataMaster.xlsx"
            parsed = data_master.parse(workbook_path.name, workbook_path.read_bytes())
            check(parsed["valid"], "DataMaster通过当前双模型契约校验", report, parsed.get("errors"))
            check(parsed["counts"] == {"products": 1, "parameters": 19, "tags": 10, "tag_rules": 10, "couplings": 7, "constraints": 3, "agreements": 48, "model_inputs": 28}, "DataMaster各模块数据完整", report, parsed["counts"])
            committed = data_master.commit(parsed)
            check(committed["committed"] and committed["agreements"]["total"] == 48, "DataMaster可一次性提交并计算48条协议", report)
            snapshot = store.admin_snapshot()
            check(len(snapshot["parameters"]) == 19 and len(snapshot["agreements"]) == 48, "提交后数据库主数据数量正确", report)

        training = manifest["price_training"]
        check(training["models"]["ridge"]["r2"] > 0.95 and training["models"]["svr"]["r2"] > 0.95, "价格留出集拟合指标达到演练基线", report)
        check(training["max_bundle_parity_error"] < 1e-6, "训练对象与原生bundle预测一致", report)
        check(manifest["simulated_expert"]["summary_stats"]["activePreferenceEvidence"] >= 20, "效能State包含模拟专家偏好证据", report)
        report["status"] = "PASS"
    except Exception as exc:
        report["status"] = "FAIL"
        report["error"] = "%s: %s" % (type(exc).__name__, exc)
        raise
    finally:
        report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
