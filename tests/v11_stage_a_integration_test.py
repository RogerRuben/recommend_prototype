# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import shutil
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.model_service_client import ModelServiceGateway
from app.recommender import rank_agreements
from services.common.http_service import make_handler
from services.effectiveness_service.app import EffectivenessService, OriginalRuntimeBackend, _physical_gate, backend_from_package
from services.price_service.app import PriceService


def check(value, message, report, detail=None):
    if not value:
        raise AssertionError(message + (": %s" % detail if detail is not None else ""))
    report["checks"].append({"message": message, "detail": detail})
    print("PASS - " + message)


def start_http(app):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server, thread, "http://127.0.0.1:%d" % server.server_address[1]


def main():
    report = {"version": "V11-stage-A", "status": "RUNNING", "checks": []}
    manifest_path = ROOT / "services/effectiveness_service/model/current/effectiveness_runtime_manifest.json"
    backend = backend_from_package(manifest_path)
    effect_service = EffectivenessService(backend)
    servers = []
    try:
        check(backend.profile_version == 11 and backend.algorithm_version == "V11-PAR-UTA", "正式效能运行包使用V11 PAR-UTA", report, backend.model_version)
        check(backend.product_code == "VIRTUAL_COUPLED_ACTUATOR", "V11迁移保留稳定成品代号", report, backend.product_code)
        check(len(backend.state.get("interactions") or []) == 16, "V11迁移保留全部交互记录", report, len(backend.state.get("interactions") or []))
        check(len(backend.state.get("preference_evidence") or []) == 17, "V11迁移保留全部偏好证据", report, len(backend.state.get("preference_evidence") or []))
        check(len(backend.state.get("feasibility_evidence") or []) == 8, "V11迁移保留全部可行性证据", report, len(backend.state.get("feasibility_evidence") or []))

        params = dict(backend.app.project.schemes[0].params)
        served = effect_service._one({"request_id": "V11-STAGE-A", "parameters": params})
        evaluation = served["evaluation"]
        check(evaluation["conservative_capability_score"] is not None, "效能服务输出P10保守效能分", report, evaluation["conservative_capability_score"])
        check(len(evaluation["protocol_score_interval"]) == 2, "效能服务输出协议稳健区间", report, evaluation["protocol_score_interval"])
        check(evaluation["robust_model_count"] >= 2, "效能服务输出稳健重训练模型数量", report, evaluation["robust_model_count"])
        check(evaluation["support_at_100"] is not None, "效能服务输出达到100分支持率", report, evaluation["support_at_100"])
        check(served["physical_gate"]["passed"], "正式样例通过独立物理门控", report, served["physical_gate"]["decision"])
        expected_contributors = len((served.get("requirement_assessment") or {}).get("attributes") or [])
        check(len(served["capability_contributors"]) == expected_contributors, "属性贡献账本覆盖全部协议评价属性", report, len(served["capability_contributors"]))
        check(served["protocol"]["reference_score"] == 100.0 and served["protocol"]["reference_digest"], "固定协议身份和摘要可审计", report, served["protocol"]["profile_id"])
        check(served["model"]["state_sha256"] == backend.state_sha256, "服务响应回显专家state摘要", report, backend.state_sha256[:12])

        price_service = PriceService(
            ROOT / "services/price_service/model/price_native_bundle.pkl",
            ROOT / "models/price_bundle.json",
        )
        pserver, pthread, purl = start_http(price_service)
        eserver, ethread, eurl = start_http(effect_service)
        servers.extend([(pserver, pthread), (eserver, ethread)])
        gateway = ModelServiceGateway(None, purl, eurl, timeout=20, fallback=False)
        gateway.schemas()
        joint_params = dict(price_service.example_request().get("parameters") or {})
        joint_params.update(params)
        merged = gateway.evaluate(joint_params)
        check(merged["conservative_capability_score"] == evaluation["conservative_capability_score"], "P10保守分无损穿过HTTP服务网关", report, merged["conservative_capability_score"])
        check(merged["protocol_score_interval"] == evaluation["protocol_score_interval"], "稳健区间无损穿过HTTP服务网关", report, merged["protocol_score_interval"])
        check(merged["physical_gate"]["decision"] == served["physical_gate"]["decision"], "物理门控无损穿过HTTP服务网关", report, merged["physical_gate"]["decision"])
        check(len(merged["capability_contributors"]) == len(served["capability_contributors"]), "贡献账本无损穿过HTTP服务网关", report, len(merged["capability_contributors"]))
        check(merged["model_audit"]["effectiveness"]["state_sha256"] == backend.state_sha256, "推荐结果保留模型审计链", report, merged["model_versions"]["effectiveness"])

        items = [
            {"agreement_id": "CENTER-HIGH", "predicted_price_wan": 10, "capability_score": 130, "conservative_capability_score": 90,
             "feasibility_probability": 0.90, "physical_gate": {"passed": True}, "tags": []},
            {"agreement_id": "ROBUST-HIGH", "predicted_price_wan": 10, "capability_score": 106, "conservative_capability_score": 101,
             "feasibility_probability": 0.90, "physical_gate": {"passed": True}, "tags": []},
            {"agreement_id": "PHYSICS-REJECTED", "predicted_price_wan": 1, "capability_score": 180, "conservative_capability_score": 170,
             "feasibility_probability": 0.50, "physical_gate": {"passed": False, "decision": "reject_low_feasibility_probability"}, "tags": []},
        ]
        ranked = rank_agreements(items, {"selected_tags": [], "sort_by": "capability"}, {})
        check([item["agreement_id"] for item in ranked] == ["ROBUST-HIGH", "CENTER-HIGH"], "普通推荐先物理门控并按P10保守分排序", report, [item["agreement_id"] for item in ranked])
        check(ranked[0]["capability_score"] > 100 and ranked[0]["conservative_capability_score"] > 100, "超过100分的中心分和保守分均不截断", report, [ranked[0]["capability_score"], ranked[0]["conservative_capability_score"]])

        mature = _physical_gate(0.95, "likely_infeasible_learned", [], [{"mature": True, "message": "专家边界"}], [])
        severe = _physical_gate(0.95, "uncertain_feasibility", [], [], [{"status": "above_band", "severity": 0.9}])
        check(not mature["passed"] and mature["decision"] == "reject_mature_expert_boundary", "成熟专家边界独立否决高概率方案", report)
        check(not severe["passed"] and severe["decision"] == "reject_severe_coupling", "严重耦合不匹配独立否决高概率方案", report)

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="v11_state_digest_", dir=str(ROOT / "runtime")) as temp:
            temp_root = Path(temp)
            source = manifest_path.parent / manifest["source_root"]
            workbook = manifest_path.parent / manifest["workbook"]
            state_source = manifest_path.parent / manifest["state"]
            changed_state = temp_root / state_source.name
            state = json.loads(state_source.read_text(encoding="utf-8"))
            state["stage_a_digest_probe"] = "changed-state-with-same-learning-fingerprint"
            changed_state.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            changed = OriginalRuntimeBackend(source, workbook, changed_state, temp_root / "runtime_state")
            check(changed.app.project.learning_fingerprint == backend.app.project.learning_fingerprint, "状态变化不伪造学习结构指纹", report)
            check(changed.model_version != backend.model_version and changed.state_sha256 != backend.state_sha256, "专家state变化会改变模型版本号和摘要", report, [backend.model_version, changed.model_version])

        report["status"] = "PASS"
    finally:
        for server, thread in servers:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        (ROOT / "logs").mkdir(exist_ok=True)
        (ROOT / "logs/v11_stage_a_integration_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
