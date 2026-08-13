# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check(condition, label, report):
    if not condition:
        raise AssertionError(label)
    report.append("PASS: " + label)


def main():
    from app.server import Application

    report = []
    with tempfile.TemporaryDirectory(prefix="ipdemo-service-down-") as raw:
        root = Path(raw)
        (root / "data").mkdir(parents=True)
        (root / "config").mkdir(parents=True)
        shutil.copy2(str(ROOT / "data" / "protocol_demo.db"), str(root / "data" / "protocol_demo.db"))
        (root / "config" / "model_services.json").write_text(json.dumps({
            "execution_mode": "services",
            "price_service_url": "http://127.0.0.1:19991",
            "effectiveness_service_url": "http://127.0.0.1:19992",
            "timeout_seconds": 0.25,
            "local_fallback": False,
        }), encoding="utf-8")

        application = Application(root)
        bootstrap = application.bootstrap()
        check(bootstrap["integration"]["calculation_available"] is False,
              "双服务不可用时主程序仍可启动并标记计算不可用", report)
        check(bootstrap["integration"]["historical_recommendation_available"] is True,
              "启动降级后明确保留历史推荐", report)
        result = application.recommend({
            "source_mode": "both", "page": 1, "page_size": 8,
            "selected_tags": [], "indicator_filters": [], "max_price": None,
            "min_capability": 99, "min_feasibility": 0.99,
        })
        check(result["recommendation_mode"] == "historical_only_degraded",
              "服务异常自动进入纯历史推荐模式", report)
        check(result["source_mode"] == "historical" and result["total"] > 0,
              "即使模型指标筛选存在也能返回已有历史成品", report)
        first = result["items"][0]
        check(first["model_evaluation_available"] is False and "historical_price_wan" in first,
              "降级结果保留历史价格且不伪造模型评价", report)
        detail = application.agreement_detail(first["agreement_id"], "fallback-test")
        check(detail["current_model_evaluation"]["model_evaluation_available"] is False,
              "历史成品详情可打开并明确未计算", report)
        snapshot = application.admin_snapshot()
        check(snapshot["model_services"]["local_model_files_read"] is False,
              "数据管理只监测HTTP服务而不读取本地模型", report)
        check("body" in snapshot["model_services"]["request_examples"]["price"],
              "数据管理提供按当前成品属性生成的价格示例JSON", report)
    print("\n".join(report))
    print("SUMMARY: %d PASS" % len(report))


if __name__ == "__main__":
    main()
