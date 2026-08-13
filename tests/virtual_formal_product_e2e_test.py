# -*- coding: utf-8 -*-
"""Formal virtual-product acceptance test.

Run this file with runtime/venvs/virtual_product38.  The test intentionally
uses the real native-price backend, the original effectiveness Workbook+State
runtime, the HTTP service gateway, staged business activation, recommendation,
explicit recomputation, saving, and delivery rollback.
"""
from __future__ import print_function

import hashlib
import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
LOCAL_OPENER = build_opener(ProxyHandler({}))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.server import Application, create_server
from services.common.http_service import make_handler
from services.effectiveness_service.app import EffectivenessService, backend_from_package
from services.price_service.app import PriceService
from tools.product_delivery import install_delivery, rollback_delivery, verify_delivery


PRODUCT_CODE = "VIRTUAL_COUPLED_ACTUATOR"
OUTPUT_ROOT = ROOT / "outputs" / "virtual_formal_baseline"
PACKAGE = OUTPUT_ROOT / "virtual_product_delivery.zip"
REPORT_PATH = ROOT / "logs" / "virtual_formal_product_e2e_report.json"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sqlite_logical_sha256(path):
    connection = sqlite3.connect(str(path))
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise AssertionError("SQLite完整性检查失败: %s" % integrity)
        dump = "\n".join(connection.iterdump()).encode("utf-8")
        return hashlib.sha256(dump).hexdigest()
    finally:
        connection.close()


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


def request_json(url, payload=None, timeout=30):
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with LOCAL_OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check(condition, name, report, detail=None):
    if not condition:
        raise AssertionError(name if detail is None else "%s: %s" % (name, detail))
    item = {"name": name, "status": "PASS"}
    if detail is not None:
        item["detail"] = detail
    report["checks"].append(item)


def changed(left, right, tolerance=1e-8):
    return abs(float(left) - float(right)) > float(tolerance)


def effect_signature(result):
    return (
        float(result["capability_score"]),
        float(result["feasibility_probability"]),
        json.dumps(result.get("coupling_assessments") or [], ensure_ascii=False, sort_keys=True),
    )


def start_service(application):
    port = free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(application))
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server, thread, port


def stop_service(server, thread):
    if server is not None:
        server.shutdown()
        server.server_close()
    if thread is not None:
        thread.join(timeout=10)


def prepare_isolated_root(target):
    target = Path(target)
    (target / "data").mkdir(parents=True)
    shutil.copy2(str(ROOT / "data" / "protocol_demo.db"), str(target / "data" / "protocol_demo.db"))
    source_csv = ROOT / "data" / "virtual_protocol_dataset.csv"
    if source_csv.is_file():
        shutil.copy2(str(source_csv), str(target / "data" / source_csv.name))

    price_target = target / "services" / "price_service" / "model"
    price_target.mkdir(parents=True)
    (price_target / "price_native_bundle.pkl").write_bytes(b"PRE-INSTALL-PRICE-SENTINEL")
    (price_target / "price_native_bundle.pkl.manifest.json").write_text(
        '{"sentinel":"price-sidecar"}\n', encoding="utf-8"
    )

    effect_target = target / "services" / "effectiveness_service" / "model" / "current"
    effect_target.mkdir(parents=True)
    (effect_target / "sentinel.txt").write_text("PRE-INSTALL-EFFECT-SENTINEL\n", encoding="utf-8")
    return {
        "db_logical_sha256": sqlite_logical_sha256(target / "data" / "protocol_demo.db"),
        "price_sha256": sha256(price_target / "price_native_bundle.pkl"),
        "effect_sentinel": (effect_target / "sentinel.txt").read_text(encoding="utf-8"),
    }


def main():
    report = {
        "test": "virtual_formal_product_e2e",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python": sys.version,
        "python_executable": sys.executable,
        "checks": [],
        "status": "RUNNING",
    }
    price_server = price_thread = effect_server = effect_thread = None
    main_server = main_thread = None
    old_environment = dict(os.environ)
    isolated_path = None
    try:
        import numpy
        import scipy
        import openpyxl

        check(sys.version_info[:2] == (3, 8), "使用Win7目标Python 3.8虚拟环境", report)
        check(
            (numpy.__version__, scipy.__version__, openpyxl.__version__) == ("1.24.4", "1.10.1", "3.1.3"),
            "离线固定依赖版本正确",
            report,
            "%s / %s / %s" % (numpy.__version__, scipy.__version__, openpyxl.__version__),
        )

        verified = verify_delivery(PACKAGE)
        manifest = verified["manifest"]
        check(manifest["formal"] is True, "统一交付包为正式后端", report)
        check(manifest["cross_contract"]["valid"] is True, "交付包跨模块契约通过", report)
        check(manifest["product_code"] == PRODUCT_CODE, "交付包成品代号稳定", report)
        check(
            (
                manifest["cross_contract"]["price_field_count"],
                manifest["cross_contract"]["effectiveness_field_count"],
                manifest["cross_contract"]["shared_field_count"],
                manifest["cross_contract"]["model_parameter_count"],
            ) == (10, 11, 6, 15),
            "价格专用、效能专用和共有字段集合完整",
            report,
        )

        test_temp_parent = ROOT / "runtime" / "t"
        test_temp_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="v_",
            dir=str(test_temp_parent),
        ) as temp:
            isolated_path = Path(temp)
            before = prepare_isolated_root(isolated_path)
            installed = install_delivery(
                PACKAGE,
                project_root=isolated_path,
                expected_sha256=verified["sha256"],
                enforce_stopped=False,
            )
            release_id = installed["business_release_id"]
            check(bool(release_id), "安装只导入待发布草稿", report, release_id)

            price_path = isolated_path / manifest["price"]["target"]
            effect_manifest = isolated_path / manifest["effectiveness"]["target"] / "effectiveness_runtime_manifest.json"
            check(price_path.is_file() and effect_manifest.is_file(), "双模型正式载荷安装完成", report)

            price_application = PriceService(price_path, fallback_json=None)
            effect_application = EffectivenessService(backend_from_package(effect_manifest))
            price_server, price_thread, price_port = start_service(price_application)
            effect_server, effect_thread, effect_port = start_service(effect_application)
            price_url = "http://127.0.0.1:%d" % price_port
            effect_url = "http://127.0.0.1:%d" % effect_port

            price_health = request_json(price_url + "/health")
            effect_health = request_json(effect_url + "/health")
            price_example_result = request_json(
                price_url + "/api/v1/predict",
                price_application.example_request(),
            )
            effect_example_result = request_json(
                effect_url + "/api/v1/evaluate",
                effect_application.example_request(),
            )
            check(
                price_health["backend"] == "native_pickle"
                and price_health["exact_mode"]
                and price_example_result["success"],
                "价格服务使用原生pickle精确模式且文档示例可执行",
                report,
            )
            check(
                effect_health["backend"] == "original_effectiveness_runtime"
                and effect_example_result["success"],
                "效能服务运行原始Workbook与专家State且文档示例可执行",
                report,
            )
            check(
                price_health["product_code"] == effect_health["product_code"] == PRODUCT_CODE,
                "独立模型服务成品代号一致",
                report,
            )

            business = json.loads(
                (OUTPUT_ROOT / "business" / "product_release.iprelease.json").read_text(encoding="utf-8")
            )
            base_params = dict(business["data"]["agreements"][0]["params"])
            enum_result = request_json(
                price_url + "/api/v1/predict",
                {"product_code": PRODUCT_CODE, "parameters": base_params},
            )
            check(enum_result["success"] and enum_result["prediction"]["predicted_price_wan"] > 0, "价格枚举字段可执行预测", report)
            invalid_enum = dict(base_params)
            invalid_enum["material_grade"] = "不存在的材料"
            try:
                request_json(
                    price_url + "/api/v1/predict",
                    {"product_code": PRODUCT_CODE, "parameters": invalid_enum},
                )
                rejected = False
            except HTTPError:
                rejected = True
            check(rejected, "价格服务拒绝未知枚举而不静默编码", report)

            os.environ["IPDEMO_MODEL_EXECUTION_MODE"] = "services"
            os.environ["IPDEMO_PRICE_SERVICE_URL"] = price_url
            os.environ["IPDEMO_EFFECT_SERVICE_URL"] = effect_url
            os.environ["IPDEMO_MODEL_SERVICE_FALLBACK"] = "0"
            os.environ["IPDEMO_MODEL_SERVICE_TIMEOUT"] = "30"
            application = Application(isolated_path)
            check(
                not application.model_data_sync_error,
                "模型与当前主数据已一致时无需重复激活即可计算",
                report,
            )
            activation = application.activate_product_release(release_id)
            check(activation["activated"] and not application.model_data_sync_error, "草稿校验后显式激活并恢复推荐", report)

            bootstrap = application.bootstrap()
            roles = bootstrap["parameter_roles"]
            role_counts = {}
            for metadata in roles.values():
                value = metadata["model_role"]
                role_counts[value] = role_counts.get(value, 0) + 1
            check(
                role_counts == {"shared": 6, "effectiveness_only": 5, "price_only": 4},
                "主系统按模型Schema识别三类属性角色",
                report,
                role_counts,
            )
            check(len(application.store.historical_agreements()) == 40, "40条虚拟历史协议已激活", report)
            runtime_manifest = application.runtime.manifest()
            check(
                runtime_manifest["execution_mode"] == "independent_http_services"
                and not runtime_manifest["local_fallback_enabled"],
                "推荐主系统不再使用本地旧bundle",
                report,
            )

            base = application.evaluate({"parameters": base_params})
            price_only = dict(base_params)
            price_only["material_grade"] = (
                "钛合金" if base_params["material_grade"] != "钛合金" else "标准合金"
            )
            price_changed = application.evaluate({"parameters": price_only})
            check(
                changed(base["predicted_price_wan"], price_changed["predicted_price_wan"]),
                "价格专用属性只驱动价格模型",
                report,
            )
            check(
                effect_signature(base) == effect_signature(price_changed),
                "价格专用属性不污染效能结果",
                report,
            )

            effect_only = dict(base_params)
            effect_only["response_time_ms"] = (
                50.0 if float(base_params["response_time_ms"]) > 180.0 else 380.0
            )
            effect_changed = application.evaluate({"parameters": effect_only})
            check(
                not changed(base["predicted_price_wan"], effect_changed["predicted_price_wan"]),
                "效能专用属性不污染价格结果",
                report,
            )
            check(
                effect_signature(base) != effect_signature(effect_changed),
                "效能专用属性驱动效能或可行性结果",
                report,
            )

            shared = dict(base_params)
            shared["rated_thrust_n"] = (
                5000.0 if float(base_params["rated_thrust_n"]) > 12500.0 else 20000.0
            )
            shared_changed = application.evaluate({"parameters": shared})
            check(
                changed(base["predicted_price_wan"], shared_changed["predicted_price_wan"])
                and effect_signature(base) != effect_signature(shared_changed),
                "共有属性同时进入价格与效能模型",
                report,
            )

            contextual = application.evaluate(
                {
                    "parameters": shared,
                    "base_parameters": base_params,
                    "base_tags": [],
                    "recommendation_context": {
                        "selected_tags": [],
                        "indicator_filter_mode": "all",
                        "indicator_filters": [],
                        "locked_parameters": ["rated_thrust_n"],
                    },
                }
            )
            check("tag_evidence" in contextual and "tags" in contextual, "标签规则实时派生并保留证据", report)
            check(
                len(contextual.get("coupling_assessments") or []) >= 1
                and "recommendation_assessment" in contextual,
                "耦合与推荐风险在修改后重新计算",
                report,
            )

            historical = application.recommend(
                {
                    "session_id": "virtual-e2e",
                    "source_mode": "historical",
                    "selected_tags": [],
                    "indicator_filter_mode": "all",
                    "indicator_filters": [],
                    "page_size": 5,
                }
            )
            check(
                historical["total"] == 39 and len(historical["items"]) == 5,
                "历史协议经V11物理门控后推荐排序链路通过",
                report,
                {"total": historical["total"], "returned": len(historical["items"])},
            )

            generated = application.generate_live(
                {
                    "session_id": "virtual-e2e",
                    "selected_tags": [],
                    "indicator_filter_mode": "all",
                    "indicator_filters": [],
                    "min_feasibility": 0.0,
                    "count": 1,
                    "seed": 20260730,
                }
            )
            check(generated["count"] == 1 and generated["batch_id"], "双服务批量评价驱动智能生成", report)
            generated_view = application.recommend(
                {
                    "session_id": "virtual-e2e",
                    "source_mode": "generated",
                    "generation_batch_id": generated["batch_id"],
                    "page_size": 5,
                }
            )
            check(generated_view["total"] == 1, "生成方案进入统一推荐浏览链路", report)

            calculated = application.evaluate({"parameters": base_params})
            edited_after_calculation = dict(base_params)
            edited_after_calculation["warranty_years"] = (
                1 if int(base_params["warranty_years"]) != 1 else 8
            )
            try:
                application.save(
                    {
                        "scheme_name": "不应保存的过期计算",
                        "parameters": edited_after_calculation,
                        "evaluation_token": calculated["evaluation_token"],
                        "risk_confirmed": True,
                    }
                )
                stale_rejected = False
            except ValueError:
                stale_rejected = True
            check(stale_rejected, "属性修改后不会自动沿用旧计算结果", report)
            recalculated = application.evaluate({"parameters": edited_after_calculation})
            saved = application.save(
                {
                    "scheme_name": "虚拟正式链路显式计算方案",
                    "parameters": edited_after_calculation,
                    "evaluation_token": recalculated["evaluation_token"],
                    "risk_confirmed": True,
                }
            )
            check(saved["saved"], "点击计算后产生的新令牌可用于保存", report)

            main_port = free_port()
            main_server = create_server(isolated_path, "127.0.0.1", main_port)
            main_thread = threading.Thread(target=main_server.serve_forever)
            main_thread.daemon = True
            main_thread.start()
            main_url = "http://127.0.0.1:%d" % main_port
            health = request_json(main_url + "/api/health")
            try:
                web_recommend = request_json(
                    main_url + "/api/recommend",
                    {
                        "session_id": "virtual-http-e2e",
                        "source_mode": "historical",
                        "selected_tags": [],
                        "indicator_filters": [],
                        "page_size": 3,
                    },
                )
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError("主系统HTTP推荐失败(%s): %s" % (exc.code, body))
            check(
                health["status"] == "ok" and web_recommend["total"] == 39,
                "主系统HTTP推荐接口通过V11物理门控",
                report,
            )
            stop_service(main_server, main_thread)
            main_server = main_thread = None

            stop_service(price_server, price_thread)
            stop_service(effect_server, effect_thread)
            price_server = price_thread = effect_server = effect_thread = None
            rollback_delivery(installed["backup_id"], project_root=isolated_path, enforce_stopped=False)
            restored_price = isolated_path / "services" / "price_service" / "model" / "price_native_bundle.pkl"
            restored_effect = (
                isolated_path
                / "services"
                / "effectiveness_service"
                / "model"
                / "current"
                / "sentinel.txt"
            )
            restored_db = isolated_path / "data" / "protocol_demo.db"
            check(
                sha256(restored_price) == before["price_sha256"]
                and restored_effect.read_text(encoding="utf-8") == before["effect_sentinel"]
                and sqlite_logical_sha256(restored_db) == before["db_logical_sha256"],
                "统一回滚精确恢复价格、效能与业务数据库",
                report,
            )

        report["status"] = "PASS"
    except Exception as exc:
        report["status"] = "FAIL"
        report["error"] = "%s: %s" % (type(exc).__name__, exc)
        raise
    finally:
        stop_service(main_server, main_thread)
        stop_service(price_server, price_thread)
        stop_service(effect_server, effect_thread)
        os.environ.clear()
        os.environ.update(old_environment)
        report["isolated_root"] = str(isolated_path) if isolated_path else None
        report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
