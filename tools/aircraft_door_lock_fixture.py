# -*- coding: utf-8 -*-
"""Build an aviation cabin-door-lock data-staff demonstration package.

All generated records, prices and expert preferences are deterministic virtual
test data.  The price bundle contains real fitted sklearn/XGBoost estimators;
the effectiveness package contains the original ProjectApp runtime plus a
simulated-expert State.
"""
from __future__ import print_function

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.product_releases import PACKAGE_FORMAT
from services.price_service.export_native_price_bundle import export_from_notebook
from services.price_service.native_bundle import file_sha256, load_bundle, predict


PRODUCT_CODE = "AIRCRAFT_CABIN_DOOR_LOCK_DEMO"
PRODUCT_NAME = "航空客舱门锁（虚拟数据人员演练成品）"
SEED = 20260801
PRICE_MODEL_VERSION = "aircraft-door-lock-price-20260801"


def field(key, label, unit, value_type, minimum, maximum, preference,
          stage, precision, description, allowed=None, category_mapping=None,
          participate=True, generate=True):
    return {
        "key": key, "label": label, "unit": unit, "value_type": value_type,
        "data_type": {
            "number": "连续", "integer": "整数", "boolean": "整数",
            "ip_grade": "整数", "enum": "类别",
        }[value_type],
        "min": minimum, "max": maximum, "preference": preference,
        "stage": stage, "precision": precision, "description": description,
        "allowed_values": allowed, "category_mapping": category_mapping,
        "participate": participate, "generate": generate,
    }


EFFECT_FIELDS = [
    field("rated_load_kn", "额定载荷", "kN", "number", 20, 70, "越大越好", 1, 2,
          "舱门锁在规定工况下承受的额定工作载荷。"),
    field("retention_force_kn", "锁闭保持力", "kN", "number", 25, 90, "越大越好", 1, 2,
          "锁闭后抵抗舱门开启方向载荷的保持能力。"),
    field("safety_factor", "结构安全系数", "-", "number", 1.2, 2.0, "越大越好", 1, 3,
          "结构承载能力相对于设计载荷的安全储备。"),
    field("shock_rating_g", "抗振冲击等级", "g", "number", 5, 18, "越大越好", 1, 2,
          "锁机构在振动与冲击环境下保持功能的能力。"),
    field("stability_margin", "锁闭稳定裕度", "-", "number", 0.12, 0.68, "越大越好", 2, 3,
          "防止扰动导致意外脱锁的稳定储备。"),
    field("design_life_kcycles", "设计寿命", "千次", "integer", 30, 180, "越大越好", 1, 0,
          "规定使用条件下的目标开闭循环寿命。"),
    field("mass_kg", "锁体质量", "kg", "number", 6, 24, "越小越好", 3, 2,
          "舱门锁总成质量，受承载、材料和架构影响。"),
    field("protection_grade", "防护等级", "IP", "ip_grade", 54, 67, "越大越好", 2, 0,
          "锁体防尘防水等级。", [54, 55, 65, 66, 67]),
    field("emergency_release", "应急解锁装置", "", "boolean", 0, 1, "越大越好", 2, 0,
          "是否配备独立应急解锁装置。", [0, 1]),
    field("trigger_force_kn", "触发/解锁力", "kN", "number", 3, 15, "越小越好", 3, 2,
          "触发锁机构并完成解锁所需的操作力。"),
    field("contact_stress_ratio", "接触应力比", "-", "number", 0.50, 1.0, "越小越好", 3, 3,
          "最大接触应力与许用接触应力之比。"),
    field("cycle_reliability_pct", "循环可靠度", "%", "number", 95, 99.99, "越大越好", 3, 3,
          "虚拟寿命试验条件下的循环动作可靠度。"),
    field("seal_leak_rate_sccm", "密封泄漏率", "sccm", "number", 0.2, 8.0, "越小越好", 3, 2,
          "锁体密封组件在规定压差下的虚拟泄漏率。"),
    field("lock_architecture", "锁机构架构", "", "enum", None, None, "不参与", 2, 0,
          "主锁机构架构，仅用于分类展示和方案编辑。",
          ["旋转钩锁", "直线插销锁", "双余度组合锁"],
          {"旋转钩锁": 0.0, "直线插销锁": 1.0, "双余度组合锁": 2.0},
          participate=False, generate=False),
]


PRICE_ONLY_FIELDS = [
    field("material_grade", "主体材料", "", "enum", None, None, "中性", 2, 0,
          "价格专用材料分类。", ["高强铝合金", "15-5PH不锈钢", "钛合金"],
          {"高强铝合金": 0.0, "15-5PH不锈钢": 1.0, "钛合金": 2.0}),
    field("purchase_quantity", "采购批量", "套", "integer", 1, 500, "中性", 3, 0,
          "价格专用采购数量，批量增大产生折减。"),
    field("delivery_months", "交付周期", "月", "number", 2, 18, "中性", 3, 1,
          "价格专用计划交付周期。"),
    field("certification_level", "适航验证等级", "", "enum", None, None, "中性", 2, 0,
          "价格专用适航验证阶段。", ["试验件", "适航验证", "批产级"],
          {"试验件": 0.0, "适航验证": 1.0, "批产级": 2.0}),
    field("imported_ratio_pct", "进口件比例", "%", "number", 0, 100, "中性", 3, 1,
          "价格专用进口件金额占比。"),
]


PRICE_KEYS = [
    "rated_load_kn", "retention_force_kn", "safety_factor", "shock_rating_g",
    "stability_margin", "design_life_kcycles", "mass_kg", "protection_grade",
    "emergency_release", "material_grade", "purchase_quantity", "delivery_months",
    "certification_level", "imported_ratio_pct",
]


EFFECT_COUPLINGS = [
    ("额定载荷", "锁体质量", "正向", "额定载荷提高通常增加承载结构质量。"),
    ("锁闭保持力", "锁体质量", "正向", "保持力提高通常增加锁钩和轴系质量。"),
    ("结构安全系数", "锁体质量", "正向", "更高安全储备通常增加结构质量。"),
    ("抗振冲击等级", "锁体质量", "正向", "更高抗振要求通常需要加强结构。"),
    ("额定载荷", "触发/解锁力", "正向", "载荷提高通常增加机构解锁力。"),
    ("锁闭保持力", "触发/解锁力", "正向", "保持力提高通常增加解锁力。"),
    ("设计寿命", "循环可靠度", "正向", "寿命设计强化通常提升循环可靠度。"),
    ("接触应力比", "循环可靠度", "负向", "接触应力比升高通常降低循环可靠度。"),
]


def _round(value, places):
    return round(float(value), int(places))


def generate_records(count, seed):
    rng = random.Random(seed)
    records = []
    architectures = ["旋转钩锁", "直线插销锁", "双余度组合锁"]
    materials = ["高强铝合金", "15-5PH不锈钢", "钛合金"]
    certifications = ["试验件", "适航验证", "批产级"]
    grades = [54, 55, 65, 66, 67]
    for index in range(1, count + 1):
        rated = rng.uniform(20, 70)
        retention = rng.uniform(max(25, rated * 0.82), 90)
        safety = rng.uniform(1.2, 2.0)
        shock = rng.uniform(5, 18)
        stability = rng.uniform(0.12, 0.68)
        life = rng.randint(30, 180)
        grade = grades[rng.randrange(len(grades))]
        emergency = 1 if rng.random() > 0.25 else 0
        architecture = architectures[rng.randrange(len(architectures))]
        material = materials[rng.randrange(len(materials))]
        quantity = rng.randint(1, 500)
        delivery = rng.uniform(2, 18)
        certification = certifications[rng.randrange(len(certifications))]
        imported = rng.uniform(0, 100)

        arch_mass = {"旋转钩锁": 0.5, "直线插销锁": 0.2, "双余度组合锁": 2.3}[architecture]
        material_mass = {"高强铝合金": -1.0, "15-5PH不锈钢": 1.2, "钛合金": -0.4}[material]
        mass = 3.2 + rated * 0.095 + retention * 0.045 + shock * 0.12 + (safety - 1.2) * 2.4 + arch_mass + material_mass + rng.gauss(0, 0.35)
        mass = max(6.0, min(24.0, mass))
        trigger = 1.2 + rated * 0.055 + retention * 0.045 + stability * 2.2 + (1.0 if architecture == "双余度组合锁" else 0.0) + rng.gauss(0, 0.25)
        trigger = max(3.0, min(15.0, trigger))
        stress = 0.95 - safety * 0.18 + rated * 0.0025 + retention * 0.0015 + rng.gauss(0, 0.018)
        stress = max(0.50, min(1.0, stress))
        reliability = 95.4 + life * 0.020 + safety * 0.45 - stress * 1.15 + emergency * 0.18 + rng.gauss(0, 0.12)
        reliability = max(95.0, min(99.99, reliability))
        leak = 9.0 - (grade - 54) * 0.38 - safety * 0.35 + rng.gauss(0, 0.35)
        leak = max(0.2, min(8.0, leak))

        material_premium = {"高强铝合金": 0.0, "15-5PH不锈钢": 3.2, "钛合金": 7.8}[material]
        cert_premium = {"试验件": 0.0, "适航验证": 4.5, "批产级": 8.5}[certification]
        price = (6.5 + rated * 0.12 + retention * 0.075 + safety * 1.8 + shock * 0.16
                 + stability * 1.2 + life * 0.025 + mass * 0.52 + max(0, grade - 54) * 0.08
                 + emergency * 0.9 + material_premium + cert_premium + imported * 0.035
                 + max(0, 12 - delivery) * 0.30 - min(quantity, 350) * 0.018
                 + rng.gauss(0, 0.65))
        price = max(8.0, price)

        records.append({
            "scheme_id": "ADL-%04d" % index,
            "rated_load_kn": _round(rated, 2),
            "retention_force_kn": _round(retention, 2),
            "safety_factor": _round(safety, 3),
            "shock_rating_g": _round(shock, 2),
            "stability_margin": _round(stability, 3),
            "design_life_kcycles": int(life),
            "mass_kg": _round(mass, 2),
            "protection_grade": int(grade),
            "emergency_release": int(emergency),
            "trigger_force_kn": _round(trigger, 2),
            "contact_stress_ratio": _round(stress, 3),
            "cycle_reliability_pct": _round(reliability, 3),
            "seal_leak_rate_sccm": _round(leak, 2),
            "lock_architecture": architecture,
            "material_grade": material,
            "purchase_quantity": int(quantity),
            "delivery_months": _round(delivery, 1),
            "certification_level": certification,
            "imported_ratio_pct": _round(imported, 1),
            "price_wan": _round(price, 4),
        })
    return records


def effectiveness_payload(records):
    headers = ["方案编号", "来源", "已知可行性"] + [item["label"] for item in EFFECT_FIELDS]
    scheme_rows = [headers]
    for row in records:
        scheme_rows.append([row["scheme_id"], "虚拟航空舱门锁历史样本", "未标注"] + [row[item["key"]] for item in EFFECT_FIELDS])
    attribute_rows = [["属性名", "属性ID", "单位", "数据类型", "设计顺序", "显示精度", "生成下限", "生成上限", "可行下限", "可行上限", "偏好方向", "边际规律", "参与效能", "参与生成", "说明"]]
    for item in EFFECT_FIELDS:
        attribute_rows.append([
            item["label"], item["key"], item["unit"], item["data_type"], item["stage"], item["precision"],
            item["min"], item["max"], item["min"], item["max"], item["preference"],
            "边际收益递减" if item["preference"] == "越大越好" else "低值改善逐渐饱和" if item["preference"] == "越小越好" else "分类展示",
            "是" if item["participate"] else "否", "是" if item["generate"] else "否", item["description"],
        ])
    coupling_rows = [["源属性", "目标属性", "方向", "关系类型", "先验系数", "置信状态", "说明"]]
    for left, right, direction, note in EFFECT_COUPLINGS:
        coupling_rows.append([left, right, direction, "单调影响", None, "方向已知，强度由虚拟样本学习", note])
    reference = records[len(records) // 2]
    protocol_fields = [item for item in EFFECT_FIELDS if item["value_type"] != "enum"]
    protocol_rows = [["协议编号", "协议名称"] + [item["label"] for item in protocol_fields] + ["说明"]]
    protocol_rows.append(["ADL-REQ-001", "航空客舱门锁综合技术协议（虚拟）"] + [reference[item["key"]] for item in protocol_fields] + ["虚拟协议参考向量，仅供软件功能演练。"])
    return {
        "product_code": PRODUCT_CODE,
        "product_name": PRODUCT_NAME,
        "sheets": {
            "生成说明": [["项目", PRODUCT_NAME], ["用途", "数据人员功能演练；全部数据均为虚拟数据"], ["随机种子", SEED], ["样本数量", len(records)], ["专家状态", "由ProjectApp模拟专家偏好与可行性证据"]],
            "项目信息": [["成品代号", PRODUCT_CODE], ["成品名称", PRODUCT_NAME], ["数据性质", "虚拟测试数据，不代表适航、工程或报价结论"]],
            "方案数据": scheme_rows,
            "属性配置": attribute_rows,
            "耦合关系": coupling_rows,
            "新技术协议": protocol_rows,
        },
        "validations": {
            "方案数据": {
                "lock_architecture": ["旋转钩锁", "直线插销锁", "双余度组合锁"],
                "emergency_release": [0, 1],
                "protection_grade": [54, 55, 65, 66, 67],
            }
        },
    }


def _encode_price(records):
    mappings = {item["key"]: item.get("category_mapping") for item in EFFECT_FIELDS + PRICE_ONLY_FIELDS}
    rows = []
    for record in records:
        rows.append([
            float((mappings.get(key) or {}).get(record[key], record[key]))
            for key in PRICE_KEYS
        ])
    return rows


def train_price_bundle(records, output):
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVR
    from xgboost import XGBRegressor

    rows = np.asarray(_encode_price(records), dtype=float)
    targets = np.log(np.asarray([row["price_wan"] for row in records], dtype=float))
    split = int(len(records) * 0.8)
    train_frame = pd.DataFrame(rows[:split], columns=PRICE_KEYS)
    test_array = rows[split:]
    scaler = StandardScaler().fit(train_frame.values)
    train_scaled = scaler.transform(train_frame.values)
    test_scaled = scaler.transform(test_array)
    models = {
        "ridge": Ridge(alpha=0.35).fit(train_scaled, targets[:split]),
        "svr": SVR(C=18.0, epsilon=0.02, gamma="scale").fit(train_scaled, targets[:split]),
        "gbdt": GradientBoostingRegressor(n_estimators=120, max_depth=2, learning_rate=0.045, random_state=SEED).fit(train_scaled, targets[:split]),
        "xgboost": XGBRegressor(n_estimators=110, max_depth=3, learning_rate=0.045, subsample=0.9, colsample_bytree=0.9, objective="reg:squarederror", n_jobs=1, random_state=SEED).fit(train_scaled, targets[:split]),
    }
    actual = np.exp(targets[split:])
    metrics = {}
    inverse_rmse = []
    for name, model in models.items():
        values = np.exp(model.predict(test_scaled))
        rmse = float(math.sqrt(mean_squared_error(actual, values)))
        metrics[name] = {"rmse_wan": rmse, "mae_wan": float(mean_absolute_error(actual, values)), "r2": float(r2_score(actual, values))}
        inverse_rmse.append(1.0 / max(rmse, 1e-9))
    total = sum(inverse_rmse)
    weights = [value / total for value in inverse_rmse]
    names = list(models)
    all_fields = dict((item["key"], item) for item in EFFECT_FIELDS + PRICE_ONLY_FIELDS)
    metadata = {}
    for key in PRICE_KEYS:
        item = all_fields[key]
        metadata[key] = {
            "field_name": key, "field_label": item["label"], "dtype": item["value_type"],
            "unit": item["unit"], "required": True, "missing_policy": "reject",
            "allowed_values": item.get("allowed_values"), "category_mapping": item.get("category_mapping"),
            "parser": "ip_grade" if item["value_type"] == "ip_grade" else None,
        }
    namespace = {
        "X_train": train_frame, "X_test": test_array, "y_train": targets[:split], "y_test": actual,
        "scaler": scaler, "ridge_model": models["ridge"], "svr_model": models["svr"],
        "gbdt_model": models["gbdt"], "xgb_model": models["xgboost"],
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    export_from_notebook(
        namespace, output=output, product_code=PRODUCT_CODE, product_name=PRODUCT_NAME,
        model_version=PRICE_MODEL_VERSION, target_divisor_to_wan=1.0, field_metadata=metadata,
        ensemble_model_names=names, ensemble_weights=weights, strict=True, model_source="namespace",
    )
    bundle = load_bundle(output)
    parity = []
    for row in records[split:split + 10]:
        sample = dict((key, row[key]) for key in PRICE_KEYS)
        served = predict(bundle, sample)["predicted_price_wan"]
        encoded = np.asarray([_encode_price([row])[0]], dtype=float)
        prepared = scaler.transform(encoded)
        expected = sum(weight * math.exp(float(models[name].predict(prepared)[0])) for name, weight in zip(names, weights))
        parity.append(abs(float(served) - expected))
    report = {
        "product_code": PRODUCT_CODE, "model_version": PRICE_MODEL_VERSION,
        "training_rows": split, "test_rows": len(records) - split,
        "models": metrics, "ensemble_weights": dict(zip(names, weights)),
        "max_bundle_parity_error": max(parity), "bundle_sha256": file_sha256(output),
        "required_modules": bundle.get("required_modules"),
    }
    (output.parent / "price_training_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output, report


def parameter_definition(item, order):
    allowed = item.get("allowed_values")
    value_type = item["value_type"]
    return {
        "parameter_id": item["key"], "label": item["label"], "unit": item["unit"],
        "value_type": value_type,
        "search_type": "boolean" if value_type == "boolean" else "unordered_enum" if value_type == "enum" else "ordered_discrete" if allowed and value_type != "ip_grade" else "integer" if value_type in ("integer", "ip_grade") else "continuous",
        "min_value": item["min"], "max_value": item["max"],
        "preference": "higher" if item["preference"] == "越大越好" else "lower" if item["preference"] == "越小越好" else "neutral",
        "description": item["description"], "adjustment_hint": "虚拟数据演练字段，请在工程范围内调整。",
        "allowed_values_json": json.dumps(allowed, ensure_ascii=False) if allowed else None,
        "required": 1, "auto_adjustable": 0 if value_type == "enum" else 1,
        "decimal_places": item["precision"], "display_order": order, "enabled": 1, "model_bound": 1,
    }


def tags_and_rules():
    definitions = [
        ("TAG_HIGH_LOAD", "高载荷", "性能", 1.3), ("TAG_HIGH_RETENTION", "高保持力", "性能", 1.3),
        ("TAG_LIGHTWEIGHT", "轻量化", "性能", 1.2), ("TAG_LONG_LIFE", "长寿命", "可靠性", 1.3),
        ("TAG_HIGH_SHOCK", "高抗振", "环境", 1.2), ("TAG_EMERGENCY", "应急解锁", "安全", 1.4),
        ("TAG_HIGH_PROTECTION", "高防护", "环境", 1.2), ("TAG_LOW_TRIGGER", "低解锁力", "人机", 1.1),
        ("TAG_BATCH", "批量采购", "商务", 0.9), ("TAG_AIRWORTHINESS", "批产适航", "验证", 1.4),
    ]
    tags = [{"tag_id": code, "tag_name": name, "tag_group": group, "weight": weight, "derivation_mode": "rule", "description": "虚拟航空舱门锁数据人员演练标签", "enabled": 1} for code, name, group, weight in definitions]
    specs = [
        ("ADL-TR-001", "TAG_HIGH_LOAD", "rated_load_kn", "gte", "55"),
        ("ADL-TR-002", "TAG_HIGH_RETENTION", "retention_force_kn", "gte", "75"),
        ("ADL-TR-003", "TAG_LIGHTWEIGHT", "mass_kg", "lte", "11"),
        ("ADL-TR-004", "TAG_LONG_LIFE", "design_life_kcycles", "gte", "140"),
        ("ADL-TR-005", "TAG_HIGH_SHOCK", "shock_rating_g", "gte", "14"),
        ("ADL-TR-006", "TAG_EMERGENCY", "emergency_release", "eq", "1"),
        ("ADL-TR-007", "TAG_HIGH_PROTECTION", "protection_grade", "gte", "65"),
        ("ADL-TR-008", "TAG_LOW_TRIGGER", "trigger_force_kn", "lte", "7"),
        ("ADL-TR-009", "TAG_BATCH", "purchase_quantity", "gte", "250"),
        ("ADL-TR-010", "TAG_AIRWORTHINESS", "certification_level", "eq", "批产级"),
    ]
    rules = [{"rule_id": rid, "tag_id": tag, "parameter_id": key, "operator": op, "value1": value, "value2": None, "rule_group": "default", "enabled": 1} for rid, tag, key, op, value in specs]
    return tags, rules


def derive_tags(row):
    result = []
    if row["rated_load_kn"] >= 55: result.append("TAG_HIGH_LOAD")
    if row["retention_force_kn"] >= 75: result.append("TAG_HIGH_RETENTION")
    if row["mass_kg"] <= 11: result.append("TAG_LIGHTWEIGHT")
    if row["design_life_kcycles"] >= 140: result.append("TAG_LONG_LIFE")
    if row["shock_rating_g"] >= 14: result.append("TAG_HIGH_SHOCK")
    if row["emergency_release"] == 1: result.append("TAG_EMERGENCY")
    if row["protection_grade"] >= 65: result.append("TAG_HIGH_PROTECTION")
    if row["trigger_force_kn"] <= 7: result.append("TAG_LOW_TRIGGER")
    if row["purchase_quantity"] >= 250: result.append("TAG_BATCH")
    if row["certification_level"] == "批产级": result.append("TAG_AIRWORTHINESS")
    return result


def build_business_release(records, output):
    fields = EFFECT_FIELDS + PRICE_ONLY_FIELDS
    tags, rules = tags_and_rules()
    coupling_specs = [
        ("rated_load_kn", "mass_kg", "positive", "额定载荷—质量正向耦合"),
        ("retention_force_kn", "mass_kg", "positive", "保持力—质量正向耦合"),
        ("safety_factor", "mass_kg", "positive", "安全系数—质量正向耦合"),
        ("shock_rating_g", "mass_kg", "positive", "抗振等级—质量正向耦合"),
        ("rated_load_kn", "trigger_force_kn", "positive", "载荷—解锁力正向耦合"),
        ("retention_force_kn", "trigger_force_kn", "positive", "保持力—解锁力正向耦合"),
        ("contact_stress_ratio", "cycle_reliability_pct", "negative", "应力比—可靠度负向耦合"),
    ]
    couplings = [{
        "coupling_id": "ADL-CPL-%03d" % index, "coupling_name": name, "coupling_type": kind,
        "parameter_a": left, "parameter_b": right, "domain_operator": None, "multiplier": None,
        "offset": None, "strength": 0.55, "severity": "warning",
        "description": "与效能Workbook单调关系一致。", "rationale": "虚拟工程关系",
        "display_order": index, "enabled": 1,
    } for index, (left, right, kind, name) in enumerate(coupling_specs, 1)]
    constraints = [
        {"rule_id": "ADL-CON-001", "rule_name": "保持力不低于载荷比例", "left_parameter": "retention_force_kn", "operator": "gte", "right_parameter": "rated_load_kn", "multiplier": 0.82, "offset": 0.0, "severity": "error", "message": "锁闭保持力不得低于额定载荷的82%。", "rationale": "虚拟跨字段约束", "display_order": 1, "enabled": 1},
        {"rule_id": "ADL-CON-002", "rule_name": "最低结构安全系数", "left_parameter": "safety_factor", "operator": "gte", "right_parameter": None, "multiplier": 1.0, "offset": 1.2, "severity": "error", "message": "结构安全系数不得低于1.2。", "rationale": "虚拟常量约束", "display_order": 2, "enabled": 1},
        {"rule_id": "ADL-CON-003", "rule_name": "应急解锁建议", "left_parameter": "emergency_release", "operator": "gte", "right_parameter": None, "multiplier": 1.0, "offset": 1.0, "severity": "info", "message": "建议配置应急解锁装置。", "rationale": "用于演练布尔约束", "display_order": 3, "enabled": 1},
    ]
    agreements = []
    for index, row in enumerate(records, 1):
        agreements.append({
            "agreement_id": "ADL-HIST-%03d" % index, "product_code": PRODUCT_CODE,
            "agreement_name": "虚拟航空舱门锁历史协议-%03d" % index,
            "positioning": "、".join(derive_tags(row)) or "通用方案", "agreement_source": "historical",
            "source_year": 2019 + index % 7, "supplier_type": "虚拟供应方%s" % ("A" if index % 2 else "B"),
            "historical_price_wan": row["price_wan"], "capability_score": None,
            "feasibility_probability": None,
            "params": dict((item["key"], row[item["key"]]) for item in fields),
            "tags": derive_tags(row), "enabled": 1,
        })
    data = {
        "products": [{"product_code": PRODUCT_CODE, "product_name": PRODUCT_NAME, "product_description": "航空客舱门锁虚拟数据人员演练成品；不得作为工程、适航或报价依据。", "enabled": 1}],
        "parameters": [parameter_definition(item, index) for index, item in enumerate(fields, 1)],
        "tags": tags, "tag_rules": rules, "couplings": couplings, "constraints": constraints,
        "agreements": agreements,
    }
    core = {"format": PACKAGE_FORMAT, "product_code": PRODUCT_CODE, "product_name": PRODUCT_NAME, "data": data}
    canonical = json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    package = dict(core)
    package.update({"exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "source_release_id": "ADL-DATA-STAFF-20260801", "source_status": "validated_virtual_fixture", "virtual_fixture": True, "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest()})
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output, package


def write_csv(path, records):
    keys = ["scheme_id"] + [item["key"] for item in EFFECT_FIELDS + PRICE_ONLY_FIELDS] + ["price_wan"]
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in records:
            writer.writerow(dict((key, row.get(key)) for key in keys))


def prepare(output_dir):
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    effect_records = generate_records(48, SEED)
    price_records = generate_records(640, SEED + 1000)
    (output / "effectiveness_workbook_payload.json").write_text(json.dumps(effectiveness_payload(effect_records), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "generation_inputs.json").write_text(json.dumps({"product_code": PRODUCT_CODE, "seed": SEED, "effect_records": effect_records, "price_records": price_records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(output / "航空舱门锁_价格训练数据.csv", price_records)
    (output / "price_training_workbook_payload.json").write_text(json.dumps({"product_code": PRODUCT_CODE, "product_name": PRODUCT_NAME, "fields": ["scheme_id"] + [item["key"] for item in EFFECT_FIELDS + PRICE_ONLY_FIELDS] + ["price_wan"], "labels": ["方案编号"] + [item["label"] + (("(%s)" % item["unit"]) if item["unit"] else "") for item in EFFECT_FIELDS + PRICE_ONLY_FIELDS] + ["价格(万元)"], "records": price_records, "disclaimer": "全部为确定性虚拟训练数据，不代表真实航空产品报价。"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def _display_parameter(item):
    return [item["parameter_id"], item["label"], item["unit"], {"number": "数值", "integer": "数值", "boolean": "布尔", "ip_grade": "IP等级", "enum": "枚举"}[item["value_type"]], {"continuous": "连续数值", "integer": "整数数值", "ordered_discrete": "有序离散", "unordered_enum": "无序枚举", "boolean": "布尔开关"}[item["search_type"]], item["min_value"], item["max_value"], {"higher": "越大越好", "lower": "越小越好", "neutral": "中性"}[item["preference"]], item["description"], item["adjustment_hint"], "、".join(str(value) for value in json.loads(item["allowed_values_json"])) if item.get("allowed_values_json") else None, "是", "是" if item["auto_adjustable"] else "否", item["decimal_places"], item["display_order"], "是"]


def datamaster_payload(package, price_bundle, effect_manifest):
    data = package["data"]
    price = load_bundle(price_bundle)
    effect = json.loads(Path(effect_manifest).read_text(encoding="utf-8"))
    p_schema = dict((item["field_name"], item) for item in price["feature_schema"])
    # Original runtime exposes its schema after package validation.  The
    # effectiveness fields are the Workbook attributes in stable order.
    effect_items = dict((item["key"], item) for item in EFFECT_FIELDS)
    bindings = []
    for key, item in effect_items.items():
        bindings.append(["效能", key, item["label"], "产品参数", {"number": "数值", "integer": "整数", "boolean": "布尔", "ip_grade": "IP等级", "enum": "枚举"}[item["value_type"]], item["unit"], "是", "缺失时拒绝计算", None, None, effect["model_version"], "是"])
    for key in PRICE_KEYS:
        item = p_schema[key]
        bindings.append(["价格", key, item["field_label"], "产品参数", {"number": "数值", "integer": "整数", "boolean": "布尔", "ip_grade": "IP等级", "enum": "枚举"}.get(item["dtype"], item["dtype"]), item.get("unit") or "", "是", "缺失时拒绝计算", None, item.get("training_mean"), price["model_version"], "是"])
    tag_name = dict((item["tag_id"], item["tag_name"]) for item in data["tags"])
    parameter_by_id = dict((item["parameter_id"], item) for item in data["parameters"])
    headers = ["协议编号", "协议名称", "方案定位", "协议来源", "来源年份", "供应方类型", "历史价格(万元)", "标签"] + [item["label"] + (("(%s)" % item["unit"]) if item["unit"] else "") for item in data["parameters"]]
    agreements = [headers]
    for row in data["agreements"]:
        values = [row["agreement_id"], row["agreement_name"], row["positioning"], "历史协议", row["source_year"], row["supplier_type"], row["historical_price_wan"], "、".join(tag_name[tag] for tag in row["tags"])]
        for item in data["parameters"]:
            value = row["params"].get(item["parameter_id"])
            if item["value_type"] == "boolean": value = "有" if int(value) else "无"
            elif item["value_type"] == "ip_grade": value = "IP%d" % int(value)
            values.append(value)
        agreements.append(values)
    sheets = {
        "填写说明": [["主题", "说明"], ["数据性质", "本工作簿全部内容为虚拟数据，仅供数据人员演练。"], ["推荐顺序", "先上传统一成品交付包，再在待发布成品中校验并激活；DataMaster用于继续维护。"], ["字段角色", "指标定义是价格与效能字段并集；模型字段绑定展示各模型实际使用范围。"], ["布尔/IP", "布尔值填写有/无；IP等级填写IP54、IP65等。"], ["安全边界", "不得将本工作簿用于真实适航、结构设计或商务报价。"]],
        "字典_下拉项": [["字典名称", "可选值"], ["是否", "是、否"], ["取值类型", "数值、布尔、IP等级、枚举"], ["模型类型", "价格、效能"], ["提示级别", "提示、警告、严重"]],
        "成品信息": [["成品代号", "成品名称", "成品说明", "是否启用"], [PRODUCT_CODE, PRODUCT_NAME, data["products"][0]["product_description"], "是"]],
        "指标定义": [["指标编号", "指标名称", "单位", "取值类型", "搜索类型", "工程下限", "工程上限", "效能方向", "指标说明", "调整提示", "允许值", "是否必填", "允许自动调整", "显示小数位", "显示顺序", "是否启用"]] + [_display_parameter(item) for item in data["parameters"]],
        "标签字典": [["标签编号", "标签名称", "标签分组", "匹配权重", "生成判定方式", "标签说明", "是否启用"]] + [[item["tag_id"], item["tag_name"], item["tag_group"], item["weight"], "规则判定", item["description"], "是"] for item in data["tags"]],
        "标签规则": [["规则编号", "标签编号", "指标编号", "比较关系", "条件值1", "条件值2", "规则组", "是否启用"]] + [[item["rule_id"], item["tag_id"], item["parameter_id"], {"gte": "≥", "lte": "≤", "eq": "等于"}[item["operator"]], item["value1"], item["value2"], item["rule_group"], "是"] for item in data["tag_rules"]],
        "耦合关系": [["关系编号", "关系名称", "关系类型", "指标A", "指标B", "可行域比较", "系数", "偏置", "作用强度", "提示级别", "关系说明", "设置依据", "显示顺序", "是否启用"]] + [[item["coupling_id"], item["coupling_name"], {"positive": "正向", "negative": "负向"}[item["coupling_type"]], item["parameter_a"], item["parameter_b"], None, None, None, item["strength"], "警告", item["description"], item["rationale"], item["display_order"], "是"] for item in data["couplings"]],
        "约束规则": [["规则编号", "规则名称", "左侧指标", "比较关系", "右侧指标", "系数", "偏置", "提示级别", "违反提示", "设置依据", "显示顺序", "是否启用"]] + [[item["rule_id"], item["rule_name"], item["left_parameter"], {"gte": "≥"}[item["operator"]], item["right_parameter"], item["multiplier"], item["offset"], {"error": "严重", "info": "提示"}[item["severity"]], item["message"], item["rationale"], item["display_order"], "是"] for item in data["constraints"]],
        "历史协议": agreements,
        "模型字段绑定": [["模型类型", "字段编号", "字段名称", "字段来源", "数据类型", "单位", "是否必填", "缺失策略", "数据库配置值", "训练均值", "模型版本", "是否启用"]] + bindings,
    }
    return {"product_code": PRODUCT_CODE, "product_name": PRODUCT_NAME, "sheets": sheets, "parameter_ids": [item["parameter_id"] for item in data["parameters"]], "tag_ids": [item["tag_id"] for item in data["tags"]], "enum_columns": {item["parameter_id"]: json.loads(item["allowed_values_json"]) for item in data["parameters"] if item.get("allowed_values_json")}, "parameter_labels": dict((item["parameter_id"], item["label"] + (("(%s)" % item["unit"]) if item["unit"] else "")) for item in data["parameters"])}


def finalize(output_dir, effectiveness_workbook):
    from services.effectiveness_service.package_effectiveness_runtime import package_runtime
    from tools.product_delivery import build_delivery

    output = Path(output_dir).resolve()
    inputs = json.loads((output / "generation_inputs.json").read_text(encoding="utf-8"))
    price_path, price_report = train_price_bundle(inputs["price_records"], output / "price" / "price_native_bundle.pkl")
    business_path, business_package = build_business_release(inputs["effect_records"], output / "business" / "product_release.iprelease.json")
    source_root = ROOT / "services" / "effectiveness_service" / "original_runtime_demo"
    if str(source_root) not in sys.path: sys.path.insert(0, str(source_root))
    from interactive_project_app import ProjectApp
    state_dir = output / "simulated_expert_state"
    if state_dir.exists(): shutil.rmtree(str(state_dir))
    app = ProjectApp(Path(effectiveness_workbook).resolve(), state_dir=state_dir, seed=SEED)
    expert_summary = app.prepare_demo_state(preference_count=20)
    state_path = app.state_path
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["virtual_fixture"] = {"product_code": PRODUCT_CODE, "seed": SEED, "disclaimer": "系统模拟专家，仅用于数据人员功能演练，不得视为真实专家结论"}
    state["data_mode"] = "aircraft_door_lock_virtual_expert_simulation"
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    effect_manifest = package_runtime(source_root, effectiveness_workbook, output / "effectiveness_runtime", state_path)
    delivery = build_delivery(price_path, effect_manifest, business_path, output / "航空舱门锁_统一成品交付包.zip", delivery_version="aircraft-door-lock-data-staff-20260801", allow_demo_models=False)
    dm_payload = datamaster_payload(business_package, price_path, effect_manifest)
    (output / "datamaster_payload.json").write_text(json.dumps(dm_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "format_version": "aircraft-door-lock-data-staff-demo-1.0", "product_code": PRODUCT_CODE,
        "product_name": PRODUCT_NAME, "virtual_fixture": True, "seed": SEED,
        "counts": {"price_training_rows": len(inputs["price_records"]), "effectiveness_history_rows": len(inputs["effect_records"]), "parameters": len(business_package["data"]["parameters"]), "tags": len(business_package["data"]["tags"]), "tag_rules": len(business_package["data"]["tag_rules"]), "couplings": len(business_package["data"]["couplings"]), "constraints": len(business_package["data"]["constraints"])},
        "price_training": price_report, "effectiveness_manifest": str(effect_manifest),
        "simulated_expert": {"state": str(state_path), "summary_stats": expert_summary.get("stats"), "disclaimer": state["virtual_fixture"]["disclaimer"]},
        "delivery": delivery,
    }
    (output / "fixture_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return output / "datamaster_payload.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成航空舱门锁虚拟数据人员演练成品")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("prepare"); p.add_argument("--output-dir", required=True)
    f = sub.add_parser("finalize"); f.add_argument("--output-dir", required=True); f.add_argument("--effectiveness-workbook", required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare": print(prepare(args.output_dir))
    elif args.command == "finalize": print(finalize(args.output_dir, args.effectiveness_workbook))
    else: parser.print_help(); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
