# -*- coding: utf-8 -*-
from __future__ import print_function

import hashlib
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.generation_tasks import GenerationTaskManager
from app.local_generator import HistorySeededGenerator
from app.model_service_client import ModelServiceGateway, ServiceBackedRuntime
from services.common.http_service import make_handler
from services.effectiveness_service.app import EffectivenessService, backend_from_package
from services.price_service.app import PriceService


def check(value, message, report, detail=None):
    if not value:
        raise AssertionError(message + (": %s" % detail if detail is not None else ""))
    report["checks"].append({"message": message, "detail": detail})
    print("PASS - " + message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def start_http(app):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server, thread, "http://127.0.0.1:%d" % server.server_address[1]


def dynamic_protocol(backend):
    values = dict((backend.protocol or {}).get("reference_values") or {})
    by_key = backend.app.project.attribute_by_key()
    for key in list(values):
        spec = by_key[key]
        span = max(float(spec.generation_max) - float(spec.generation_min), 1e-9)
        if spec.preference_direction == "lower_better":
            values[key] = float(values[key]) - 0.23 * span
        else:
            values[key] = float(values[key]) + 0.23 * span
    return {
        "profile_id": "BC-DYNAMIC-001",
        "profile_name": "阶段BC动态目标协议",
        "reference_values": values,
    }


class _EmptyEngineeringStore(object):
    def coupling_rows(self):
        return []

    def constraint_rows(self):
        return []

    @staticmethod
    def _compare(left, operator, right):
        return {
            "gte": left >= right,
            "gt": left > right,
            "lte": left <= right,
            "lt": left < right,
            "eq": abs(left - right) <= 1e-9,
        }.get(operator, True)


class _FingerprintStore(object):
    @staticmethod
    def master_data_version():
        return "master-v1"


class _FingerprintRuntime(object):
    schema = {"product_code": "TEST-PRODUCT"}

    @staticmethod
    def manifest():
        return {
            "effectiveness": {"model_version": "effect-v1"},
            "price": {"model_version": "price-v1"},
        }


def main():
    report = {"version": "V11-stage-BC", "status": "RUNNING", "checks": []}
    manifest_path = ROOT / "services/effectiveness_service/model/current/effectiveness_runtime_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    backend = backend_from_package(manifest_path)
    effect_service = EffectivenessService(backend)
    servers = []
    state_file = backend.app.state_path
    state_before = sha256(state_file)
    try:
        capabilities = manifest.get("capabilities") or {}
        check(capabilities.get("dynamic_target_protocol") is True, "正式运行包声明逐请求动态协议能力", report, capabilities)
        check(capabilities.get("counterfactual_improvement") is True, "正式运行包声明反事实改进能力", report)

        schema = backend.schema()
        check(schema["target_protocol_contract"]["changes_learning_state"] is False, "协议切换契约明确不修改学习状态", report)
        check(len(schema.get("protocol_profiles") or []) >= 1, "Schema发布可选的内置协议清单", report)
        check(len(schema.get("coupling_models") or []) >= 1, "Schema发布已拟合耦合前沿", report, len(schema.get("coupling_models") or []))
        check(len(schema.get("coupling_edges") or []) >= len(schema.get("coupling_models") or []), "Schema同时发布方向先验耦合边", report, len(schema.get("coupling_edges") or []))
        check(isinstance(schema.get("learned_boundaries"), list), "Schema发布专家可行边界接口", report)

        params = dict(backend.app.project.schemes[0].params)
        fixed = backend.evaluate(params)
        selected = backend.evaluate(params, target_protocol=backend.protocol["profile_id"])
        protocol = dynamic_protocol(backend)
        changed = backend.evaluate(params, target_protocol=protocol)
        check(fixed["capability_score"] == selected["capability_score"], "显式选择内置协议与默认评估完全一致", report)
        check(changed["protocol"]["profile_id"] == protocol["profile_id"], "动态协议身份进入评估结果", report, changed["protocol"])
        check(abs(float(changed["capability_score"]) - float(fixed["capability_score"])) > 1e-6, "同一方案在不同目标协议下得到不同相对效能分", report, [fixed["capability_score"], changed["capability_score"]])
        for key in ("feasibility_probability", "feasibility_status", "physical_gate", "bt_score", "uta_score"):
            check(changed.get(key) == fixed.get(key), "协议切换不改变%s" % key, report)
        restored = backend.evaluate(params)
        check(restored["capability_score"] == fixed["capability_score"], "切回默认协议后结果可重复", report)

        incomplete = dict(protocol)
        incomplete["reference_values"] = dict(protocol["reference_values"])
        incomplete["reference_values"].pop(next(iter(incomplete["reference_values"])))
        try:
            backend.evaluate(params, target_protocol=incomplete)
            missing_rejected = False
        except ValueError as exc:
            missing_rejected = "缺少参与效能属性" in str(exc)
        check(missing_rejected, "不完整动态协议被明确拒绝", report)

        unknown = dict(protocol)
        unknown["reference_values"] = dict(protocol["reference_values"])
        unknown["reference_values"]["UNKNOWN_FIELD"] = 1
        try:
            backend.evaluate(params, target_protocol=unknown)
            unknown_rejected = False
        except ValueError as exc:
            unknown_rejected = "模型未定义属性" in str(exc)
        check(unknown_rejected, "包含未知属性的动态协议被明确拒绝", report)

        effect_view = SimpleNamespace(
            learned_boundaries=[{"attribute_key": "x", "side": "low", "boundary": 4.0, "mature": True}],
            couplings=[],
            coupling_edges=[{"source": "x", "target": "y", "direction": "positive", "coefficient_prior": None}],
        )
        generator = HistorySeededGenerator.__new__(HistorySeededGenerator)
        generator.runtime = SimpleNamespace(effectiveness=effect_view)
        generator.store = _EmptyEngineeringStore()
        definitions = {
            "x": {"min_value": 0.0, "max_value": 10.0, "decimal_places": 2, "auto_adjustable": 1},
            "y": {"min_value": 0.0, "max_value": 100.0, "decimal_places": 2, "auto_adjustable": 1},
        }
        boundary_params = {"x": 2.0, "y": 50.0}
        boundary_repairs = generator._repair_learned_boundaries(boundary_params, set(), definitions)
        check(boundary_params["x"] > 4.0 and boundary_repairs == ["learned_boundary:x:low"], "成熟专家边界在模型调用前主动修复", report, boundary_params)
        relation_params = {"x": 7.0, "y": 50.0}
        relation_repairs = generator._repair_relations(relation_params, {"x": 5.0, "y": 50.0}, definitions, set())
        check(relation_params["y"] > 50.0 and relation_repairs == ["direction_prior:x->y"], "无拟合公式时方向耦合先验仍传播下游变化", report, relation_params)

        manager = GenerationTaskManager(SimpleNamespace(runtime=_FingerprintRuntime(), store=_FingerprintStore()))
        request = {"session_id": "test", "count": 10, "target_protocol": backend.protocol["profile_id"]}
        first_fp = manager.fingerprint(request)
        request["target_protocol"] = protocol
        check(first_fp != manager.fingerprint(request), "候选生成缓存按目标协议隔离", report)

        price_service = PriceService(
            ROOT / "services/price_service/model/price_native_bundle.pkl",
            ROOT / "models/price_bundle.json",
        )
        pserver, pthread, purl = start_http(price_service)
        eserver, ethread, eurl = start_http(effect_service)
        servers.extend([(pserver, pthread), (eserver, ethread)])
        gateway = ModelServiceGateway(None, purl, eurl, timeout=60, fallback=False)
        schemas = gateway.schemas()
        runtime = ServiceBackedRuntime(gateway, schemas=schemas)
        check(len(runtime.effectiveness.couplings) == len(schema["coupling_models"]), "远程推荐运行时恢复全部耦合模型", report, len(runtime.effectiveness.couplings))
        first_model = runtime.effectiveness.couplings[0]
        remote_band = runtime.effectiveness.coupling_band(first_model, params)
        direct_contour = fixed["contours"][first_model["target"]]
        check(abs(remote_band["predicted"] - direct_contour["expected_center"]) < 1e-6, "远程耦合前沿与原效能模型数值一致", report, remote_band)

        joint_params = dict(price_service.example_request().get("parameters") or {})
        joint_params.update(params)
        merged = gateway.evaluate(joint_params, target_protocol=protocol)
        check(merged["protocol"]["profile_id"] == protocol["profile_id"], "动态协议无损穿过HTTP网关", report)
        check(abs(float(merged["capability_score"]) - float(changed["capability_score"])) < 1e-6, "HTTP动态协议评分与原模型一致", report)
        batch = gateway.evaluate_batch([
            {"candidate_id": "FIXED", "parameters": joint_params, "target_protocol": backend.protocol["profile_id"]},
            {"candidate_id": "DYNAMIC", "parameters": joint_params, "target_protocol": protocol},
        ])
        check(batch[0]["protocol"]["profile_id"] != batch[1]["protocol"]["profile_id"], "批量接口支持候选级协议身份", report)
        check(batch[0]["capability_score"] != batch[1]["capability_score"], "批量接口按各自协议独立评分", report)

        improvement = gateway.improve(joint_params, target_protocol=protocol)
        plan = improvement.get("improvement_plan") or {}
        recommended = plan.get("recommended_evaluation") or {}
        check(plan.get("recommended_parameters"), "按需接口返回可执行的反事实参数方案", report)
        check(recommended.get("protocol", {}).get("profile_id") == protocol["profile_id"], "改进方案在同一动态协议下重新评估", report)
        check(recommended.get("predicted_price_wan") is not None, "改进方案重新计算价格而非复用旧结果", report, recommended.get("predicted_price_wan"))
        check(recommended.get("physical_gate", {}).get("passed") is not None, "改进方案重新执行独立物理门控", report)

        check(sha256(state_file) == state_before, "动态评估、批量评估与改进搜索均不修改专家学习状态", report, state_before[:12])
        report["status"] = "PASS"
    finally:
        for server, thread in servers:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        (ROOT / "logs").mkdir(exist_ok=True)
        (ROOT / "logs/v11_stage_bc_integration_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
