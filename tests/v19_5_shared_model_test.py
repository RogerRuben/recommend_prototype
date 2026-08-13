# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.model_runtime import IntegratedModelRuntime
from app.store import Store


def check(condition, message, report):
    if not condition:
        raise AssertionError(message)
    print("PASS - " + message)
    report["checks"].append(message)


def insert_effect_definitions(store, runtime):
    conn = store.connect()
    try:
        conn.execute(
            "INSERT INTO products(product_code,product_name,product_description,enabled) VALUES(?,?,?,1)",
            (runtime.schema["product_code"], runtime.schema.get("product_name") or runtime.schema["product_code"], "V19.5契约4.0测试"),
        )
        for order, spec in enumerate(runtime.effectiveness.features, 1):
            value_type = "ip_grade" if spec.get("parser") == "ip_grade" else spec.get("type", "number")
            conn.execute(
                """INSERT INTO parameter_definitions
                (parameter_id,label,unit,value_type,min_value,max_value,preference,description,adjustment_hint,
                 allowed_values_json,search_type,required,auto_adjustable,decimal_places,display_order,enabled,model_bound)
                VALUES(?,?,?,?,?,?,?,?,?,NULL,?,?,?,?,?,1,1)""",
                (
                    spec["key"], spec.get("label", spec["key"]), spec.get("unit", ""), value_type,
                    spec.get("min"), spec.get("max"), spec.get("preference", "neutral"),
                    spec.get("description", ""), spec.get("adjustment_hint", ""),
                    spec.get("search_type", "continuous"), 1 if spec.get("required", True) else 0,
                    1 if spec.get("auto_adjustable", True) else 0,
                    int(spec.get("decimal_places", 3)), order,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def main():
    report = {"version": "V19.5", "status": "RUNNING", "checks": []}
    fixture = ROOT / "tests" / "fixtures" / "contract4_model_pair"
    runtime = IntegratedModelRuntime(fixture)
    manifest = runtime.manifest()
    check(manifest["contract_version"] == "4.0", "真实效能转换产物与价格转换产物可由集成运行时加载", report)
    roles = runtime.feature_roles()
    check(set(roles["shared_features"]) == {"rated_load", "mass", "design_life"}, "共享字段由两个模型的交集自动识别", report)
    check(set(roles["price_only_features"]) == {"purchase_quantity", "delivery_months"}, "价格专用字段可以独立存在", report)
    check(len(roles["effectiveness_only_features"]) == 6, "效能专用字段保持独立", report)

    sample = dict(runtime.effectiveness.bundle["historical_samples"][0])
    evaluation = runtime.evaluate(sample)
    check(evaluation["predicted_price_wan"] > 0 and evaluation["capability_score"] >= 0, "共享参数集完成价格与效能联合推理", report)
    check("purchase_quantity" in evaluation["parameters"] and "delivery_months" in evaluation["parameters"], "价格专用缺失字段按模型策略补全并写入当前方案", report)
    check(evaluation["price_imputed_features"], "联合评估明确记录价格字段补全依据", report)

    with tempfile.TemporaryDirectory(prefix="ipdemo_v195_roles_") as temp_name:
        temp = Path(temp_name)
        (temp / "data").mkdir(); (temp / "backups").mkdir()
        store = Store(temp / "data" / "protocol_demo.db", temp / "data" / "missing.csv", runtime, temp / "backups")
        insert_effect_definitions(store, runtime)
        store.sync_model_schema()
        bootstrap = store.bootstrap()
        by_key = {x["parameter_id"]: x for x in bootstrap["parameters"]}
        check(len(by_key) == len(runtime.all_feature_specs()), "数据库字段定义同步为价格与效能属性并集", report)
        check(by_key["rated_load"]["model_role"] == "shared" and by_key["rated_load"]["default_visible"], "共享属性只保留一份且默认显示", report)
        check(by_key["purchase_quantity"]["model_role"] == "price_only" and not by_key["purchase_quantity"]["default_visible"], "价格专用属性默认隐藏", report)
        bindings = bootstrap["model_input_bindings"]
        rated = [x for x in bindings if x["parameter_id"] == "rated_load"]
        check({x["model_kind"] for x in rated} == {"effectiveness", "price"}, "同一指标可以同时保存价格和效能两条模型绑定", report)

    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    check("showPriceAttributes" in html and "showPriceAttributes" in js, "方案编辑区提供价格相关属性展开选项", report)
    check('def.model_role==="price_only"' in js and "price-attribute-hidden" in js, "前端按模型角色控制默认显示", report)
    check("价格＋效能" in js, "共享属性在编辑区明确标识为价格＋效能", report)

    report["status"] = "PASS"
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
