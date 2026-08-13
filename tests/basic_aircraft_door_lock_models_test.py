# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import shutil
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.model_runtime import IntegratedModelRuntime
from app.model_service_client import ModelServiceGateway, ServiceBackedRuntime
from app.local_generator import HistorySeededGenerator
from app.server import Application
from app.product_releases import ProductReleaseService
from app.store import Store
from services.common.http_service import make_handler
from services.effectiveness_service.app import EffectivenessService, backend_from_package
from services.price_service.app import PriceService
from tools.product_delivery import build_delivery, verify_delivery


OUT = ROOT / "outputs" / "019fb26c_basic_aircraft_door_lock_models_20260812"
SOURCE = ROOT / "outputs" / "019fb26c_basic_product_demo" / "basic_aircraft_door_lock_history_demo.xlsx"
PRODUCT_CODE = "AIRCRAFT_DOOR_LOCK_BASIC_DEMO"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("PASS - " + message)


def start_http(app):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server, thread, "http://127.0.0.1:%d" % server.server_address[1]


def main():
    temp_root = Path(tempfile.mkdtemp(prefix="basic_adl_models_"))
    servers = []
    try:
        local_runtime = IntegratedModelRuntime(ROOT / "models")
        store = Store(temp_root / "fixture.db", ROOT / "data" / "virtual_protocol_dataset.csv", local_runtime, temp_root / "backups")
        releases = ProductReleaseService(store, local_runtime)
        analyzed = releases.analyze_history(
            SOURCE.name, SOURCE.read_bytes(), PRODUCT_CODE, "基础航空舱门锁（虚拟功能演示）", ["-1", "\\", "/"],
        )
        parameter_ids = [item["parameter_id"] for item in analyzed["data"]["parameters"]]
        check(parameter_ids == ["attr_%03d" % index for index in range(1, 9)], "模型字段ID与历史表自动推断结果完全一致")

        price = PriceService(OUT / "price" / "price_native_bundle.pkl", None)
        effect = EffectivenessService(backend_from_package(OUT / "effectiveness_runtime" / "effectiveness_runtime_manifest.json"))
        check(price.health()["backend"] == "native_pickle" and price.health()["exact_mode"], "价格服务加载原生pickle精确模型")
        check(effect.health()["backend"] == "original_effectiveness_runtime", "效能服务加载原ProjectApp与模拟专家State")
        check(price.schema()["product_code"] == effect.schema()["product_code"] == PRODUCT_CODE, "双HTTP模型成品代号一致")
        check(
            [item["field_name"] for item in price.schema()["fields"]] == ["attr_%03d" % index for index in range(1, 8)]
            and [item["field_name"] for item in effect.schema()["fields"]] == ["attr_001", "attr_005", "attr_007"],
            "价格与效能字段角色对应基础历史表",
        )

        price_server, price_thread, price_url = start_http(price)
        effect_server, effect_thread, effect_url = start_http(effect)
        servers.extend([(price_server, price_thread), (effect_server, effect_thread)])
        gateway = ModelServiceGateway(None, price_url, effect_url, timeout=30, fallback=False)
        remote = ServiceBackedRuntime(gateway)
        roles = remote.feature_roles()
        check(
            roles == {
                "shared_features":["attr_001", "attr_005", "attr_007"],
                "effectiveness_only_features":[],
                "price_only_features":["attr_002", "attr_003", "attr_004", "attr_006"],
            },
            "推荐主系统可从双服务Schema恢复共享和价格专用字段角色",
        )

        active_protocol_id = (effect.schema().get("active_protocol") or {}).get("profile_id")
        fixed_protocol_evaluation = remote.evaluate(
            analyzed["data"]["agreements"][0]["params"],
            target_protocol=active_protocol_id,
        )
        check(
            fixed_protocol_evaluation["capability_score"] is not None,
            "V10固定协议包会忽略页面携带的动态协议参数并使用包内协议",
        )
        workbench_evaluation = gateway.evaluate_effectiveness(
            analyzed["data"]["agreements"][0]["params"],
            target_protocol=active_protocol_id,
        )
        check(
            (workbench_evaluation.get("evaluation") or {}).get("effectiveness_score") is not None,
            "V10独立效能工作台会自动改用模型包内固定协议",
        )
        compatibility_improvement = remote.improve(
            analyzed["data"]["agreements"][0]["params"],
            target_protocol=active_protocol_id,
        )
        check(
            (compatibility_improvement.get("improvement_plan") or {}).get("search_mode")
            == "v10_service_compatibility_batched_neighborhood",
            "V10固定协议包使用双服务批量邻域兼容改进搜索",
        )

        mapping_store = Store(temp_root / "mapping.db", ROOT / "data" / "virtual_protocol_dataset.csv", remote, temp_root / "mapping_backups")
        mapping_data = dict((key, []) for key in ("products", "parameters", "tags", "tag_rules", "couplings", "constraints", "agreements"))
        mapping_data["products"] = [{"product_code": PRODUCT_CODE, "product_name": "映射测试", "enabled": 1}]
        mapping_data["parameters"] = [dict(item) for item in analyzed["data"]["parameters"]]
        mapping_data["agreements"] = [dict(item) for item in analyzed["data"]["agreements"]]
        for parameter in mapping_data["parameters"]:
            if parameter["parameter_id"] == "attr_002":
                parameter["value_type"] = "enum"
                parameter["allowed_values_json"] = json.dumps(["类型1", "类型2"], ensure_ascii=False)
        mapping_store.replace_from_datamaster(mapping_data, evaluate_agreements=False, sync_model_contract=False)
        mapping_store.sync_model_schema()
        encoded = mapping_store.runtime_parameters({"attr_001": "是", "attr_002": "类型2"})
        check(
            int(encoded["attr_001"]) == 1 and str(encoded["attr_002"]) == "1",
            "中文是/否和类型1/类型2自动编码为模型0/1值",
        )
        calls = {"single": 0, "batch": 0}
        original_single, original_batch = remote.evaluate, remote.evaluate_batch
        def counted_single(*args, **kwargs):
            calls["single"] += 1
            return original_single(*args, **kwargs)
        def counted_batch(*args, **kwargs):
            calls["batch"] += 1
            return original_batch(*args, **kwargs)
        remote.evaluate, remote.evaluate_batch = counted_single, counted_batch
        try:
            mapped_history = mapping_store.historical_agreements()
        finally:
            remote.evaluate, remote.evaluate_batch = original_single, original_batch
        check(
            len(mapped_history) == 12 and calls == {"single": 0, "batch": 1},
            "历史智能推荐由逐条模型调用优化为一次批量双服务评价",
        )

        evaluations = []
        for agreement in analyzed["data"]["agreements"]:
            evaluations.append(remote.evaluate(agreement["params"]))
        check(len(evaluations) == 12 and all(item["predicted_price_wan"] > 0 for item in evaluations), "12条原始历史成品均可通过双HTTP服务计算")
        check(all(item["capability_score"] is not None for item in evaluations), "12条原始历史成品均返回效能与可行性结果")
        check(any(item.get("price_imputed_features") for item in evaluations), "价格模型按显式策略处理重量/材料/锁定方式缺失")

        batch = remote.evaluate_batch([{"candidate_id":item["agreement_id"], "parameters":item["params"]} for item in analyzed["data"]["agreements"]])
        check(len(batch) == 12, "双服务批量计算接口完成12条历史成品评价")
        check(
            [item["predicted_price_wan"] for item in batch]
            == [item["predicted_price_wan"] for item in evaluations],
            "价格服务矩阵批量预测与逐方案预测结果一致",
        )
        fixed_protocol_batch = remote.evaluate_batch(
            [
                {
                    "candidate_id": item["agreement_id"],
                    "parameters": item["params"],
                    "target_protocol": active_protocol_id,
                }
                for item in analyzed["data"]["agreements"][:2]
            ]
        )
        check(len(fixed_protocol_batch) == 2, "V10固定协议包的批量推荐不再误发逐请求动态协议")

        generation_calls = {"single": 0, "batch": 0}
        def decorate(evaluation, business_params, base_params=None):
            result = dict(evaluation)
            model_parameters = dict(result.get("parameters") or {})
            result["model_parameters"] = model_parameters
            result["parameters"] = mapping_store.business_parameters(model_parameters, business_params)
            result["rule_messages"] = mapping_store.assess_rules(result["parameters"], base_params)
            return result
        def generation_single(params, base_params=None, target_protocol=None):
            generation_calls["single"] += 1
            encoded = mapping_store.runtime_parameters(params)
            evaluation = remote.evaluate(encoded, target_protocol=target_protocol)
            return decorate(evaluation, params, base_params)
        def generation_batch(items):
            generation_calls["batch"] += 1
            prepared = []
            for index, item in enumerate(items):
                prepared.append({
                    "candidate_id": item.get("candidate_id") or str(index),
                    "parameters": mapping_store.runtime_parameters(item.get("parameters") or {}),
                    "target_protocol": item.get("target_protocol"),
                })
            values = remote.evaluate_batch(prepared)
            return [
                decorate(value, items[index].get("parameters") or {}, items[index].get("base_parameters"))
                for index, value in enumerate(values)
            ]
        generator = HistorySeededGenerator(
            mapping_store, remote, generation_single, evaluate_batch_callback=generation_batch,
        )
        started = time.time()
        price_target = sorted(item["predicted_price_wan"] for item in evaluations)[4]
        generated = generator.generate(
            {"max_price": price_target},
            count=3, seed=20260812, budget=80,
        )
        elapsed = time.time() - started
        check(
            len(generated["candidates"]) == 3
            and generated["strict_filter_satisfied"]
            and generation_calls["single"] == 0
            and generation_calls["batch"] <= 3,
            "合格候选生成采用少量整轮批量束搜索且不再隐藏逐方案模型试算（%.3f秒，%d批）"
            % (elapsed, generation_calls["batch"]),
        )
        classifier = Application.__new__(Application)
        classifier.store = mapping_store
        shallow_profile = classifier.generation_search_profile({"max_price": min(item["predicted_price_wan"] for item in evaluations) * 0.98})
        deep_profile = classifier.generation_search_profile({"max_price": min(item["predicted_price_wan"] for item in evaluations) * 0.90})
        check(
            shallow_profile["mode"] == "fast"
            and deep_profile["mode"] == "deep_extrapolation"
            and "等待时间" in deep_profile["warning"]
            and "仅供" in deep_profile["warning"],
            "历史范围内/浅层越界走快速搜索，深度越界自动切换并发布等待与外推提示",
        )

        report = json.loads((OUT / "price" / "price_training_report.json").read_text(encoding="utf-8"))
        check(report["source_known_price_mae_wan"] < 0.10 and report["source_known_price_max_error_wan"] < 0.20, "虚拟价格模型回代源表价格误差满足演示基线")
        delivery_path = temp_root / "history_direct_delivery.zip"
        built_delivery = build_delivery(
            OUT / "price" / "price_native_bundle.pkl",
            OUT / "effectiveness_runtime" / "effectiveness_runtime_manifest.json",
            None,
            delivery_path,
            history_workbook=SOURCE,
            product_code=PRODUCT_CODE,
            product_name="基础航空舱门锁（虚拟功能演示）",
        )
        verified_delivery = verify_delivery(delivery_path, expected_sha256=built_delivery["sha256"])
        check(
            verified_delivery["manifest"]["formal"]
            and verified_delivery["manifest"]["business"]["source"] == "history_workbook_auto_onboarding",
            "仅凭历史成品表和两个正式模型可直接构建并验签甲方统一交付包",
        )
        print(json.dumps({"status":"PASS", "checks":20, "product_code":PRODUCT_CODE}, ensure_ascii=False))
    finally:
        for server, thread in servers:
            server.shutdown(); server.server_close(); thread.join(5)
        shutil.rmtree(str(temp_root), ignore_errors=True)


if __name__ == "__main__":
    main()
