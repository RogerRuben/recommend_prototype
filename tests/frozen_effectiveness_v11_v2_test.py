# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.model_service_client import ModelServiceGateway
from services.common.http_service import make_handler
from services.effectiveness_service.app import EffectivenessService, FrozenRuntimeBackend, backend_from_package
from services.effectiveness_service.install_frozen_effectiveness_model import install_frozen_package
from tools.product_delivery import _load_effect_for_build


def check(value, message, checks, detail=None):
    if not value:
        raise AssertionError(message + (": %s" % detail if detail is not None else ""))
    checks.append(message)
    print("PASS - " + message)


def main():
    checks = []
    package = next((ROOT / "outputs" / "frozen_v11_v2_smoke").glob("effectiveness_model_*.zip"))
    with tempfile.TemporaryDirectory(prefix="frozen_v11_v2_test_") as temp:
        target = Path(temp) / "current"
        installed = install_frozen_package(package, target, "AIRCRAFT_DOOR_LOCK_DEMO")
        check(installed["backend"] == "frozen_effectiveness_runtime", "冻结ZIP安装为只读效能后端", checks)
        backend = backend_from_package(target / "effectiveness_runtime_manifest.json")
        check(isinstance(backend, FrozenRuntimeBackend), "服务自动识别最终冻结包格式", checks)
        schema = backend.schema()
        check(schema["profile_version"] == 11 and schema["algorithm_version"] == "V11-PAR-UTA", "冻结包算法身份无损保留", checks)
        check(schema["privacy"]["contains_source_workbook"] is False, "冻结模型不携带原Workbook", checks)
        values = {}
        for field in schema["fields"]:
            allowed = field.get("allowed_values") or []
            lo, hi = field.get("generation_min"), field.get("generation_max")
            values[field["field_name"]] = allowed[0] if allowed else ((float(lo) + float(hi)) / 2.0 if lo is not None and hi is not None else lo or 0)
        service = EffectivenessService(backend)
        result = service._one({"request_id": "FROZEN-V2", "parameters": values})
        check(result["evaluation"]["effectiveness_score"] is not None, "冻结模型可直接评价效能", checks)
        check(result["model"]["model_version"] == installed["model_version"], "HTTP响应保留冻结模型版本", checks)
        delivery_effect = _load_effect_for_build(target)
        check(delivery_effect["formal"] and delivery_effect["backend"] == backend.name, "统一甲方交付工具接受冻结效能包", checks)
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        thread = threading.Thread(target=server.serve_forever); thread.daemon = True; thread.start()
        try:
            gateway = ModelServiceGateway(effectiveness_url="http://127.0.0.1:%d" % server.server_address[1])
            remote_schema = gateway.effectiveness_schema()
            remote = gateway.evaluate_effectiveness(values)
            check(remote_schema["product_code"] == "AIRCRAFT_DOOR_LOCK_DEMO", "工作台可独立读取效能Schema", checks)
            check(remote["evaluation"]["effectiveness_score"] is not None, "工作台只调用效能服务即可完成评价", checks)
        finally:
            server.shutdown(); thread.join(timeout=5); server.server_close()
    html = (ROOT / "app" / "static" / "effectiveness.html").read_text(encoding="utf-8")
    js = (ROOT / "app" / "static" / "effectiveness.js").read_text(encoding="utf-8")
    check("效能评价工作台" in html and "/api/effectiveness-workbench/evaluate" in js, "操作人员专用效能评价页面已接入", checks)
    print(json.dumps({"status": "PASS", "checks": checks}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
