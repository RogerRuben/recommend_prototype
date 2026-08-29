# -*- coding: utf-8 -*-
"""V21.1.1 release-readiness, diagnostics and customer-copy regressions."""
from __future__ import print_function

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.configuration import _boolean, load_service_portal_config  # noqa: E402
from app.local_generator import HistorySeededGenerator  # noqa: E402
from app.server import Application  # noqa: E402
from tools.select_price_runtime import candidate_pythons, select_runtime  # noqa: E402


def price_runtime_contract():
    env = {"PRICE_SERVICE_PYTHON": r"C:\vscode\python.exe", "CONDA_PREFIX": r"C:\conda"}
    candidates = candidate_pythons(ROOT, environ=env, which=lambda: r"C:\path\python.exe")
    assert candidates[0] == env["PRICE_SERVICE_PYTHON"]
    assert "price_runtime" in candidates[1]
    assert "model_runtime38" in candidates[2]
    assert candidates[-1] == r"C:\path\python.exe"

    with tempfile.TemporaryDirectory(prefix="price_selector_") as folder:
        first = Path(folder) / "bad.exe"
        second = Path(folder) / "good.exe"
        first.touch()
        second.touch()

        class Completed(object):
            def __init__(self, code, output):
                self.returncode, self.stdout = code, output

        calls = []

        def runner(command, **_kwargs):
            calls.append(command[0])
            return Completed(1, "incompatible") if command[0] == str(first) else Completed(0, "Runtime smoke: PASS")

        selected, attempts = select_runtime(ROOT, ROOT / "native.pkl", [str(first), str(second)], runner)
        assert selected == str(second.resolve())
        assert calls == [str(first), str(second)]
        assert [item["ok"] for item in attempts] == [False, True]

    launcher = (ROOT / "START_PRICE_SERVICE_WIN7.bat").read_text(encoding="utf-8")
    all_services = (ROOT / "START_ALL_SERVICES_WIN7.bat").read_text(encoding="utf-8")
    assert "PRICE_SERVICE_PYTHON" in launcher
    assert "tools\\select_price_runtime.py" in launcher
    assert "--allow-model-fallback" not in launcher
    assert "portable" not in launcher.lower()
    assert "check_service_readiness.py" in launcher and "price-prediction-service" in launcher
    assert "=== Price Service ===" in all_services and "=== Effectiveness Service ===" in all_services
    assert "Maximum wait: 20 seconds" in all_services


def preflight_revalidation_contract():
    definitions = {
        "mode": {
            "parameter_id": "mode", "value_type": "enum",
            "allowed_values_json": '["A"]',
            "model_value_mapping_json": '{"A":0}',
        }
    }

    class Runtime(object):
        def all_feature_specs(self):
            return [{"key": "mode", "required": True, "missing_policy": "reject", "allowed_values": [0, 1]}]

    class Store(object):
        def runtime_parameters(self, params):
            # The business repair succeeds, but conversion is still invalid for
            # the model contract. Full post-repair validation must catch this.
            return {"mode": 99 if params.get("mode") == "A" else params.get("mode")}

    item = {"params": {"mode": 999}, "base": {"agreement_id": "H-01"}}
    report = HistorySeededGenerator(Store(), Runtime(), None, None)._generation_input_preflight(
        [item], definitions
    )
    assert item["params"]["mode"] == "A"
    assert report["eligible_seed_count"] == 0
    assert report["seeds"][0]["unmapped_values"] == ["mode"]


def portal_contract():
    assert _boolean("false", True) is False
    assert _boolean("true", False) is True
    with tempfile.TemporaryDirectory(prefix="portal_v2111_", dir=str(ROOT)) as folder:
        config_dir = Path(folder) / "config"
        config_dir.mkdir()
        path = config_dir / "service_portal.json"
        path.write_text(json.dumps({"services": {
            "advanced_price": {"description": "客户自定义说明", "url": "", "visible": "true", "enabled": "false"}
        }}, ensure_ascii=False), encoding="utf-8")
        loaded = load_service_portal_config(folder)
        advanced = loaded["services"]["advanced_price"]
        assert advanced["description"] == "客户自定义说明"
        assert advanced["visible"] is True and advanced["enabled"] is False
        assert loaded["services"]["recommendation"]["url"] == "/"

        app = Application.__new__(Application)
        app.root = Path(folder)
        app.portal_config = loaded
        saved = app.save_portal_config({"services": {
            "advanced_price": {"description": "保存后的说明", "visible": "false", "enabled": "false"}
        }})
        item = saved["config"]["services"]["advanced_price"]
        assert item["description"] == "保存后的说明"
        assert item["visible"] is False and item["enabled"] is False
        assert saved["config"]["services"]["recommendation"]["label"] == "方案智能推荐"


def presentation_contract():
    app_js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    portal_js = (ROOT / "app/static/portal.js").read_text(encoding="utf-8")
    pages = "\n".join(
        (ROOT / "app/static" / name).read_text(encoding="utf-8")
        for name in ("index.html", "price.html", "effectiveness.html", "portal.html", "admin.html")
    )
    assert 'exploratory=item.generation_level==="exploratory"' in app_js
    assert "当前参数组合已生成，但模型没有完成评价" in app_js
    assert "本轮暂未找到可直接推荐的方案" in app_js
    assert '<summary>查看技术详情</summary>' in app_js
    assert "来源：DataMaster" in app_js and '<summary>技术详情</summary>' in app_js
    assert "item.description||m.description" in portal_js
    assert "保守效能 P10" not in pages
    for forbidden in ("Business → Model", "model_services.json", "反事实搜索", "我方快速价格", "DataMaster 参考范围提示"):
        assert forbidden not in pages + "\n" + app_js + "\n" + portal_js, forbidden


if __name__ == "__main__":
    price_runtime_contract()
    preflight_revalidation_contract()
    portal_contract()
    presentation_contract()
    print("PASS V21.1.1 release readiness regressions")
