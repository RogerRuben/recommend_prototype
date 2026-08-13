# -*- coding: utf-8 -*-
"""Generate a deterministic formal-like virtual product baseline.

The fixture covers shared, price-only, and effectiveness-only parameters,
continuous/integer/boolean/IP/enum types, coupling rules, tags, historical
agreements, a native price pickle, and a simulated-expert effectiveness State.

All generated artifacts are explicitly marked as virtual test data.
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
from services.price_service.native_bundle import file_sha256, save_bundle
from services.price_service.synthetic_models import (
    SyntheticLinearRegressor,
    SyntheticStandardScaler,
)


PRODUCT_CODE = "VIRTUAL_COUPLED_ACTUATOR"
PRODUCT_NAME = "多类型耦合执行机构（虚拟验收成品）"
SEED = 20260730


EFFECT_FIELDS = [
    {
        "key": "rated_thrust_n", "label": "额定推力", "unit": "N",
        "data_type": "连续", "value_type": "number", "stage": 1, "precision": 1,
        "min": 5000, "max": 20000, "preference": "越大越好", "trend": "边际收益递减",
        "description": "共有连续属性，影响价格、结构质量和效能。",
    },
    {
        "key": "stroke_mm", "label": "有效行程", "unit": "mm",
        "data_type": "连续", "value_type": "number", "stage": 1, "precision": 1,
        "min": 50, "max": 250, "preference": "区间型", "trend": "目标区间",
        "description": "共有连续属性，长行程会增加结构尺寸和价格。",
    },
    {
        "key": "speed_mm_s", "label": "运行速度", "unit": "mm/s",
        "data_type": "连续", "value_type": "number", "stage": 1, "precision": 1,
        "min": 10, "max": 100, "preference": "越大越好", "trend": "边际收益递减",
        "description": "共有连续属性，与响应时间存在负向耦合。",
    },
    {
        "key": "protection_grade", "label": "防护等级", "unit": "IP",
        "data_type": "整数", "value_type": "ip_grade", "stage": 1, "precision": 0,
        "min": 54, "max": 67, "preference": "越大越好", "trend": "分级提升",
        "allowed_values": [54, 55, 65, 66, 67],
        "description": "共有IP等级属性；效能模型按整数等级处理。",
    },
    {
        "key": "overload_protection", "label": "过载保护", "unit": "",
        "data_type": "整数", "value_type": "boolean", "stage": 1, "precision": 0,
        "min": 0, "max": 1, "preference": "越大越好", "trend": "具备优于不具备",
        "allowed_values": [0, 1],
        "description": "共有布尔属性；效能Workbook用0/1整数保存。",
    },
    {
        "key": "mass_kg", "label": "整机质量", "unit": "kg",
        "data_type": "连续", "value_type": "number", "stage": 3, "precision": 2,
        "min": 8, "max": 38, "preference": "越小越好", "trend": "低值改善逐渐饱和",
        "description": "共有连续属性，是多个上游设计参数的耦合目标。",
    },
    {
        "key": "accuracy_mm", "label": "定位精度", "unit": "mm",
        "data_type": "连续", "value_type": "number", "stage": 2, "precision": 3,
        "min": 0.05, "max": 1.0, "preference": "越小越好", "trend": "低值改善逐渐饱和",
        "description": "效能专用连续属性。",
    },
    {
        "key": "response_time_ms", "label": "响应时间", "unit": "ms",
        "data_type": "连续", "value_type": "number", "stage": 3, "precision": 1,
        "min": 50, "max": 380, "preference": "越小越好", "trend": "低值改善逐渐饱和",
        "description": "效能专用连续属性，是速度和精度的耦合目标。",
    },
    {
        "key": "duty_cycle_pct", "label": "工作循环", "unit": "%",
        "data_type": "连续", "value_type": "number", "stage": 2, "precision": 1,
        "min": 20, "max": 95, "preference": "越大越好", "trend": "边际收益递减",
        "description": "效能专用连续属性。",
    },
    {
        "key": "redundancy_level", "label": "冗余等级", "unit": "级",
        "data_type": "整数", "value_type": "integer", "stage": 2, "precision": 0,
        "min": 1, "max": 3, "preference": "越大越好", "trend": "分级提升",
        "allowed_values": [1, 2, 3],
        "description": "效能专用整数属性。",
    },
    {
        "key": "control_mode", "label": "控制方式", "unit": "",
        "data_type": "类别", "value_type": "enum", "stage": 2, "precision": 0,
        "min": None, "max": None, "preference": "不参与", "trend": "分类展示",
        "allowed_values": ["电动", "液压", "电液混合"],
        "description": "效能专用无序枚举，验证类别字段传输和编辑。",
    },
]


PRICE_ONLY_FIELDS = [
    {
        "key": "material_grade", "label": "主体材料等级", "unit": "",
        "value_type": "enum", "min": None, "max": None,
        "allowed_values": ["标准合金", "高强合金", "钛合金"],
        "category_mapping": {"标准合金": 0.0, "高强合金": 1.0, "钛合金": 2.0},
        "description": "价格专用无序枚举，通过category_mapping进入原生模型。",
    },
    {
        "key": "imported_ratio_pct", "label": "进口件比例", "unit": "%",
        "value_type": "number", "min": 0, "max": 100,
        "description": "价格专用连续属性。",
    },
    {
        "key": "warranty_years", "label": "质保年限", "unit": "年",
        "value_type": "integer", "min": 1, "max": 8,
        "allowed_values": list(range(1, 9)),
        "description": "价格专用整数属性。",
    },
    {
        "key": "batch_size", "label": "采购批量", "unit": "台",
        "value_type": "integer", "min": 1, "max": 500,
        "description": "价格专用整数属性，批量增加产生价格折减。",
    },
]


PRICE_KEYS = [
    "rated_thrust_n", "stroke_mm", "speed_mm_s", "protection_grade",
    "overload_protection", "mass_kg", "material_grade",
    "imported_ratio_pct", "warranty_years", "batch_size",
]


EFFECT_COUPLINGS = [
    ("额定推力", "整机质量", "正向", "额定推力提高通常增加承载结构质量。"),
    ("有效行程", "整机质量", "正向", "长行程通常增加导向和壳体质量。"),
    ("工作循环", "整机质量", "正向", "高工作循环通常需要更强的散热和承载结构。"),
    ("冗余等级", "整机质量", "正向", "冗余部件会增加整机质量。"),
    ("运行速度", "响应时间", "负向", "速度提高通常缩短完成动作的响应时间。"),
    ("定位精度", "响应时间", "正向", "精度数值放宽时闭环整定通常可缩短响应时间。"),
]


def _round(value, places):
    return round(float(value), int(places))


def generate_records(count, seed=SEED):
    rng = random.Random(seed)
    records = []
    materials = ["标准合金", "高强合金", "钛合金"]
    controls = ["电动", "液压", "电液混合"]
    grades = [54, 55, 65, 66, 67]
    for index in range(1, count + 1):
        rated = rng.uniform(5000, 20000)
        stroke = rng.uniform(50, 250)
        speed = rng.uniform(10, 100)
        grade = grades[rng.randrange(len(grades))]
        overload = 1 if rng.random() > 0.28 else 0
        accuracy = rng.uniform(0.05, 1.0)
        duty = rng.uniform(20, 95)
        redundancy = rng.randint(1, 3)
        control = controls[rng.randrange(len(controls))]
        material = materials[rng.randrange(len(materials))]
        imported = rng.uniform(0, 100)
        warranty = rng.randint(1, 8)
        batch = rng.randint(1, 500)
        mass = (
            5.8 + rated / 1800.0 + stroke * 0.035 + duty * 0.035
            + redundancy * 1.4 + (2.0 if material == "钛合金" else 0.8 if material == "高强合金" else 0)
            + rng.gauss(0, 0.7)
        )
        mass = max(8.0, min(38.0, mass))
        response = (
            330.0 - speed * 2.0 + accuracy * 75.0 + redundancy * 8.0
            + (12.0 if control == "液压" else -8.0 if control == "电液混合" else 0.0)
            + rng.gauss(0, 8.0)
        )
        response = max(50.0, min(380.0, response))
        material_premium = {"标准合金": 0.0, "高强合金": 2.8, "钛合金": 7.5}[material]
        price = (
            3.8 + rated * 0.00055 + stroke * 0.016 + speed * 0.022
            + max(0, grade - 54) * 0.12 + overload * 1.6 + mass * 0.20
            + material_premium + imported * 0.035 + warranty * 0.62
            - min(batch, 350) * 0.012 + rng.gauss(0, 0.55)
        )
        price = max(3.0, price)
        record = {
            "scheme_id": "VCA-%03d" % index,
            "rated_thrust_n": _round(rated, 1),
            "stroke_mm": _round(stroke, 1),
            "speed_mm_s": _round(speed, 1),
            "protection_grade": int(grade),
            "overload_protection": int(overload),
            "mass_kg": _round(mass, 2),
            "accuracy_mm": _round(accuracy, 3),
            "response_time_ms": _round(response, 1),
            "duty_cycle_pct": _round(duty, 1),
            "redundancy_level": int(redundancy),
            "control_mode": control,
            "material_grade": material,
            "imported_ratio_pct": _round(imported, 1),
            "warranty_years": int(warranty),
            "batch_size": int(batch),
            "price_wan": _round(price, 4),
        }
        records.append(record)
    return records


def workbook_payload(records):
    effect_headers = ["方案编号", "来源", "已知可行性"] + [
        field["label"] for field in EFFECT_FIELDS
    ]
    data_rows = [effect_headers]
    for record in records:
        data_rows.append([
            record["scheme_id"], "确定性虚拟历史样本", "未标注"
        ] + [record[field["key"]] for field in EFFECT_FIELDS])
    attribute_headers = [
        "属性名", "属性ID", "单位", "数据类型", "设计顺序", "显示精度",
        "生成下限", "生成上限", "可行下限", "可行上限", "偏好方向",
        "边际规律", "参与效能", "参与生成", "说明",
    ]
    attribute_rows = [attribute_headers]
    for field in EFFECT_FIELDS:
        attribute_rows.append([
            field["label"], field["key"], field["unit"], field["data_type"],
            field["stage"], field["precision"], field["min"], field["max"],
            field["min"], field["max"], field["preference"], field["trend"],
            "是" if field["value_type"] != "enum" else "否",
            "是" if field["value_type"] != "enum" else "否",
            field["description"],
        ])
    coupling_rows = [[
        "源属性", "目标属性", "方向", "关系类型", "先验系数", "置信状态", "说明"
    ]]
    for source, target, direction, description in EFFECT_COUPLINGS:
        coupling_rows.append([
            source, target, direction, "单调影响", None,
            "方向已知，强度由虚拟样本学习", description,
        ])
    reference = records[len(records) // 3]
    protocol_fields = [
        field for field in EFFECT_FIELDS if field["value_type"] != "enum"
    ]
    protocol_headers = ["协议编号", "协议名称"] + [field["label"] for field in protocol_fields] + ["说明"]
    protocol_rows = [protocol_headers, [
        "VCA-REQ-001", "虚拟执行机构综合技术协议"
    ] + [reference[field["key"]] for field in protocol_fields] + [
        "仅用于自动化验收；协议值不参与模拟专家BT/UTA训练。"
    ]]
    return {
        "product_code": PRODUCT_CODE,
        "product_name": PRODUCT_NAME,
        "sheets": {
            "生成说明": [
                ["项目", PRODUCT_NAME],
                ["用途", "虚拟正式模型全链路验收，不代表真实工程结论"],
                ["随机种子", SEED],
                ["样本数量", len(records)],
                ["字段覆盖", "共有、价格专用、效能专用；连续、整数、布尔、IP、枚举"],
                ["专家状态", "由ProjectApp.prepare_demo_state生成，明确标记模拟专家"],
            ],
            "项目信息": [
                ["成品代号", PRODUCT_CODE],
                ["成品名称", PRODUCT_NAME],
                ["数据性质", "确定性虚拟测试数据"],
            ],
            "方案数据": data_rows,
            "属性配置": attribute_rows,
            "耦合关系": coupling_rows,
            "新技术协议": protocol_rows,
        },
        "categorical_columns": {
            "方案数据": {
                str(4 + next(index for index, item in enumerate(EFFECT_FIELDS) if item["key"] == "control_mode")):
                    ["电动", "液压", "电液混合"]
            }
        },
    }


def _matrix_solve(matrix, vector):
    size = len(vector)
    augmented = [list(map(float, matrix[row])) + [float(vector[row])] for row in range(size)]
    for pivot in range(size):
        best = max(range(pivot, size), key=lambda row: abs(augmented[row][pivot]))
        if abs(augmented[best][pivot]) < 1e-12:
            raise ValueError("虚拟价格训练矩阵不可逆")
        augmented[pivot], augmented[best] = augmented[best], augmented[pivot]
        divisor = augmented[pivot][pivot]
        augmented[pivot] = [value / divisor for value in augmented[pivot]]
        for row in range(size):
            if row == pivot:
                continue
            factor = augmented[row][pivot]
            if abs(factor) < 1e-16:
                continue
            augmented[row] = [
                augmented[row][column] - factor * augmented[pivot][column]
                for column in range(size + 1)
            ]
    return [augmented[row][-1] for row in range(size)]


def _fit_ridge(rows, targets, ridge):
    columns = len(rows[0]) + 1
    xtx = [[0.0] * columns for _ in range(columns)]
    xty = [0.0] * columns
    for row, target in zip(rows, targets):
        design = [1.0] + list(map(float, row))
        for left in range(columns):
            xty[left] += design[left] * float(target)
            for right in range(columns):
                xtx[left][right] += design[left] * design[right]
    for index in range(1, columns):
        xtx[index][index] += float(ridge)
    fitted = _matrix_solve(xtx, xty)
    return SyntheticLinearRegressor(fitted[0], fitted[1:], "ridge_%s" % ridge)


def _encoded_price_row(record):
    material = {"标准合金": 0.0, "高强合金": 1.0, "钛合金": 2.0}
    result = []
    for key in PRICE_KEYS:
        value = record[key]
        result.append(material[value] if key == "material_grade" else float(value))
    return result


def build_price_bundle(records, output):
    raw_rows = [_encoded_price_row(record) for record in records]
    count = float(len(raw_rows))
    means = [sum(row[index] for row in raw_rows) / count for index in range(len(PRICE_KEYS))]
    scales = []
    for index, mean in enumerate(means):
        variance = sum((row[index] - mean) ** 2 for row in raw_rows) / count
        scales.append(max(math.sqrt(variance), 1e-9))
    scaler = SyntheticStandardScaler(means, scales)
    prepared = scaler.transform(raw_rows)
    targets = [math.log(record["price_wan"]) for record in records]
    model_a = _fit_ridge(prepared, targets, 0.05)
    model_b = _fit_ridge(prepared, targets, 1.0)
    weights = [0.7, 0.3]
    residuals = []
    for row, target in zip(prepared, targets):
        predicted = (
            model_a.predict([row])[0] * weights[0]
            + model_b.predict([row])[0] * weights[1]
        )
        residuals.append(target - predicted)
    sorted_abs = sorted(abs(value) for value in residuals)
    half_width = sorted_abs[min(len(sorted_abs) - 1, int(len(sorted_abs) * 0.95))]
    all_fields = dict((item["key"], item) for item in EFFECT_FIELDS + PRICE_ONLY_FIELDS)
    feature_schema = []
    for index, key in enumerate(PRICE_KEYS):
        field = all_fields[key]
        values = [row[index] for row in raw_rows]
        dtype = field["value_type"]
        schema = {
            "field_name": key,
            "source_column": key,
            "field_label": field["label"],
            "dtype": dtype,
            "unit": field.get("unit") or "",
            "required": True,
            "missing_policy": "reject",
            "training_min": min(values),
            "training_max": max(values),
            "training_mean": means[index],
            "source": "product_parameter",
            "allowed_values": field.get("allowed_values"),
            "category_mapping": field.get("category_mapping"),
            "parser": "ip_grade" if dtype == "ip_grade" else None,
        }
        feature_schema.append(schema)
    bundle = {
        "product_code": PRODUCT_CODE,
        "product_name": PRODUCT_NAME,
        "model_version": "virtual-native-price-20260730",
        "feature_order": list(PRICE_KEYS),
        "source_feature_order": list(PRICE_KEYS),
        "feature_schema": feature_schema,
        "preprocessor": scaler,
        "models": {"ridge_low": model_a, "ridge_high": model_b},
        "ensemble": {
            "aggregation": "weighted_mean_log_prediction",
            "members": [
                {"name": "ridge_low", "weight": weights[0]},
                {"name": "ridge_high", "weight": weights[1]},
            ],
        },
        "model_output_transform": "log",
        "target_transform": {"type": "log", "target": "price_wan"},
        "target_divisor_to_wan": 1.0,
        "residual_calibration": {
            "space": "log", "lower": -half_width, "upper": half_width,
            "coverage": 0.95, "sample_count": len(records),
            "source": "deterministic_virtual_holdout_proxy",
        },
        "required_modules": ["services.price_service.synthetic_models"],
        "training_environment": {
            "fixture": True, "seed": SEED,
            "note": "虚拟测试模型，不代表真实价格规律",
        },
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    save_bundle(output, bundle)
    manifest = {
        "format_version": "price-native-bundle-manifest-1.0",
        "product_code": PRODUCT_CODE,
        "product_name": PRODUCT_NAME,
        "model_version": bundle["model_version"],
        "virtual_fixture": True,
        "training_seed": SEED,
        "training_rows": len(records),
        "feature_roles": {
            "shared": [key for key in PRICE_KEYS if key in set(item["key"] for item in EFFECT_FIELDS)],
            "price_only": [key for key in PRICE_KEYS if key in set(item["key"] for item in PRICE_ONLY_FIELDS)],
        },
        "sha256": file_sha256(output),
    }
    Path(str(output) + ".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return output, manifest


def _parameter_definition(field, order):
    value_type = field["value_type"]
    allowed = field.get("allowed_values")
    return {
        "parameter_id": field["key"],
        "label": field["label"],
        "unit": field.get("unit") or "",
        "value_type": value_type,
        "search_type": (
            "boolean" if value_type == "boolean"
            else "unordered_enum" if value_type == "enum"
            else "ordered_discrete" if allowed
            else "integer" if value_type in ("integer", "ip_grade")
            else "continuous"
        ),
        "min_value": field.get("min"),
        "max_value": field.get("max"),
        "preference": (
            "higher" if field.get("preference") == "越大越好"
            else "lower" if field.get("preference") == "越小越好"
            else "neutral"
        ),
        "description": field["description"],
        "adjustment_hint": "虚拟验收字段，请在声明范围内调整。",
        "allowed_values_json": json.dumps(allowed, ensure_ascii=False) if allowed else None,
        "required": 1,
        "auto_adjustable": 0 if value_type == "enum" else 1,
        "decimal_places": int(field.get("precision", 2 if value_type == "number" else 0)),
        "display_order": order,
        "enabled": 1,
        "model_bound": 1,
    }


def _tags_and_rules():
    tags = [
        ("TAG_HIGH_THRUST", "高推力", "性能", 1.3),
        ("TAG_HIGH_SPEED", "快速运行", "性能", 1.2),
        ("TAG_HIGH_PRECISION", "高精度", "性能", 1.4),
        ("TAG_HARSH_ENV", "恶劣环境", "环境", 1.3),
        ("TAG_HIGH_RELIABILITY", "高可靠", "能力", 1.5),
        ("TAG_LIGHTWEIGHT", "轻量化", "性能", 1.1),
        ("TAG_LONG_WARRANTY", "长质保", "商务", 0.9),
        ("TAG_IMPORTED", "高进口比例", "商务", 0.8),
        ("TAG_BATCH_ECONOMY", "批量经济型", "商务", 1.0),
        ("TAG_HYBRID_CONTROL", "电液混合控制", "架构", 1.1),
    ]
    tag_rows = [{
        "tag_id": code, "tag_name": name, "tag_group": group, "weight": weight,
        "derivation_mode": "rule", "description": "确定性虚拟标签规则", "enabled": 1,
    } for code, name, group, weight in tags]
    rules = [
        ("TR-001", "TAG_HIGH_THRUST", "rated_thrust_n", "gte", "15000", None, "default"),
        ("TR-002", "TAG_HIGH_SPEED", "speed_mm_s", "gte", "75", None, "default"),
        ("TR-003", "TAG_HIGH_PRECISION", "accuracy_mm", "lte", "0.20", None, "default"),
        ("TR-004", "TAG_HARSH_ENV", "protection_grade", "gte", "65", None, "default"),
        ("TR-005", "TAG_HIGH_RELIABILITY", "overload_protection", "eq", "1", None, "default"),
        ("TR-006", "TAG_HIGH_RELIABILITY", "redundancy_level", "gte", "2", None, "default"),
        ("TR-007", "TAG_LIGHTWEIGHT", "mass_kg", "lte", "18", None, "default"),
        ("TR-008", "TAG_LONG_WARRANTY", "warranty_years", "gte", "5", None, "default"),
        ("TR-009", "TAG_IMPORTED", "imported_ratio_pct", "gte", "60", None, "default"),
        ("TR-010", "TAG_BATCH_ECONOMY", "batch_size", "gte", "250", None, "default"),
        ("TR-011", "TAG_HYBRID_CONTROL", "control_mode", "eq", "电液混合", None, "default"),
    ]
    rule_rows = [{
        "rule_id": rid, "tag_id": tag, "parameter_id": key, "operator": op,
        "value1": value1, "value2": value2, "rule_group": group, "enabled": 1,
    } for rid, tag, key, op, value1, value2, group in rules]
    return tag_rows, rule_rows


def derive_tags(record):
    result = []
    if record["rated_thrust_n"] >= 15000:
        result.append("TAG_HIGH_THRUST")
    if record["speed_mm_s"] >= 75:
        result.append("TAG_HIGH_SPEED")
    if record["accuracy_mm"] <= 0.20:
        result.append("TAG_HIGH_PRECISION")
    if record["protection_grade"] >= 65:
        result.append("TAG_HARSH_ENV")
    if record["overload_protection"] == 1 and record["redundancy_level"] >= 2:
        result.append("TAG_HIGH_RELIABILITY")
    if record["mass_kg"] <= 18:
        result.append("TAG_LIGHTWEIGHT")
    if record["warranty_years"] >= 5:
        result.append("TAG_LONG_WARRANTY")
    if record["imported_ratio_pct"] >= 60:
        result.append("TAG_IMPORTED")
    if record["batch_size"] >= 250:
        result.append("TAG_BATCH_ECONOMY")
    if record["control_mode"] == "电液混合":
        result.append("TAG_HYBRID_CONTROL")
    return result


def build_business_release(records, output):
    tags, rules = _tags_and_rules()
    fields = EFFECT_FIELDS + PRICE_ONLY_FIELDS
    couplings = []
    coupling_specs = [
        ("rated_thrust_n", "mass_kg", "positive", "额定推力—质量正向耦合"),
        ("stroke_mm", "mass_kg", "positive", "行程—质量正向耦合"),
        ("duty_cycle_pct", "mass_kg", "positive", "工作循环—质量正向耦合"),
        ("redundancy_level", "mass_kg", "positive", "冗余—质量正向耦合"),
        ("speed_mm_s", "response_time_ms", "negative", "速度—响应时间负向耦合"),
        ("accuracy_mm", "response_time_ms", "positive", "精度数值—响应时间正向耦合"),
    ]
    for index, (left, right, kind, name) in enumerate(coupling_specs, 1):
        couplings.append({
            "coupling_id": "VCPL-%03d" % index,
            "coupling_name": name,
            "coupling_type": kind,
            "parameter_a": left,
            "parameter_b": right,
            "domain_operator": None,
            "multiplier": None,
            "offset": None,
            "strength": 0.45,
            "severity": "warning",
            "description": "与效能Workbook中的单调耦合边一致。",
            "rationale": "确定性虚拟工程关系",
            "display_order": index,
            "enabled": 1,
        })
    constraints = [
        {
            "rule_id": "VCON-001", "rule_name": "高推力最小质量约束",
            "left_parameter": "mass_kg", "operator": "gte",
            "right_parameter": "rated_thrust_n", "multiplier": 0.00065,
            "offset": 4.0, "severity": "warning",
            "message": "整机质量低于虚拟承载关系参考下限。",
            "rationale": "用于验证跨字段线性约束", "display_order": 1, "enabled": 1,
        },
        {
            "rule_id": "VCON-002", "rule_name": "高可靠方案要求过载保护",
            "left_parameter": "overload_protection", "operator": "gte",
            "right_parameter": None, "multiplier": 1.0,
            "offset": 1.0, "severity": "info",
            "message": "建议启用过载保护。",
            "rationale": "用于验证布尔常量约束", "display_order": 2, "enabled": 1,
        },
    ]
    agreements = []
    for index, record in enumerate(records[:80], 1):
        params = dict((field["key"], record[field["key"]]) for field in fields)
        agreements.append({
            "agreement_id": "VHIST-%03d" % index,
            "product_code": PRODUCT_CODE,
            "agreement_name": "虚拟历史技术协议-%03d" % index,
            "positioning": "、".join(derive_tags(record)) or "通用虚拟方案",
            "agreement_source": "deterministic_virtual_fixture",
            "source_year": 2018 + (index % 9),
            "supplier_type": "虚拟供应商%s类" % ("A" if index % 2 else "B"),
            "historical_price_wan": record["price_wan"],
            "capability_score": None,
            "feasibility_probability": None,
            "params": params,
            "tags": derive_tags(record),
            "enabled": 1,
        })
    data = {
        "products": [{
            "product_code": PRODUCT_CODE,
            "product_name": PRODUCT_NAME,
            "product_description": "确定性虚拟正式模型验收成品，不代表真实工程结论。",
            "enabled": 1,
        }],
        "parameters": [
            _parameter_definition(field, index)
            for index, field in enumerate(fields, 1)
        ],
        "tags": tags,
        "tag_rules": rules,
        "couplings": couplings,
        "constraints": constraints,
        "agreements": agreements,
    }
    core = {
        "format": PACKAGE_FORMAT,
        "product_code": PRODUCT_CODE,
        "product_name": PRODUCT_NAME,
        "data": data,
    }
    canonical = json.dumps(
        core, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    package = dict(core)
    package.update({
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_release_id": "VIRTUAL-FIXTURE-20260730",
        "source_status": "validated_synthetic_fixture",
        "virtual_fixture": True,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    })
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return output, package


def _write_csv(path, rows, keys):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict((key, row.get(key)) for key in keys))


def prepare(output_dir):
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Forty historical schemes are enough to learn multiple coupling fronts
    # and preference pairs while keeping the formal-runtime test repeatable on
    # a Windows 7-class CPU.
    effect_records = generate_records(40, SEED)
    price_records = generate_records(520, SEED + 1000)
    payload = workbook_payload(effect_records)
    payload_path = output / "workbook_payload.json"
    payload_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_csv(
        output / "virtual_price_training.csv",
        price_records,
        PRICE_KEYS + ["price_wan"],
    )
    (output / "generation_inputs.json").write_text(
        json.dumps({
            "format_version": "virtual-product-fixture-inputs-1.0",
            "product_code": PRODUCT_CODE,
            "seed": SEED,
            "effect_records": effect_records,
            "price_records": price_records,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload_path


def finalize(output_dir, workbook):
    from services.effectiveness_service.package_effectiveness_runtime import package_runtime
    from tools.product_delivery import build_delivery

    output = Path(output_dir).resolve()
    workbook = Path(workbook).resolve()
    inputs = json.loads((output / "generation_inputs.json").read_text(encoding="utf-8"))
    price_records = inputs["price_records"]
    effect_records = inputs["effect_records"]

    price_path, price_manifest = build_price_bundle(
        price_records, output / "price" / "price_native_bundle.pkl"
    )
    business_path, business_package = build_business_release(
        effect_records, output / "business" / "product_release.iprelease.json"
    )

    source_root = ROOT / "services" / "effectiveness_service" / "original_runtime_demo"
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    from interactive_project_app import ProjectApp

    state_dir = output / "simulated_expert_state"
    if state_dir.exists():
        shutil.rmtree(str(state_dir))
    app = ProjectApp(workbook, state_dir=state_dir, seed=SEED)
    summary = app.prepare_demo_state(preference_count=16)
    state_path = app.state_path
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["virtual_fixture"] = {
        "product_code": PRODUCT_CODE,
        "seed": SEED,
        "disclaimer": "系统模拟专家，仅用于自动化验收，不得视为真实专家结论",
    }
    state["data_mode"] = "fixed_virtual_expert_simulation"
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    effect_manifest = package_runtime(
        source_root,
        workbook,
        output / "effectiveness_runtime",
        state_path,
    )
    delivery = build_delivery(
        price_path,
        effect_manifest,
        business_path,
        output / "virtual_product_delivery.zip",
        delivery_version="virtual-formal-baseline-20260730",
        allow_demo_models=False,
    )
    fixture_manifest = {
        "format_version": "virtual-formal-product-baseline-1.0",
        "product_code": PRODUCT_CODE,
        "product_name": PRODUCT_NAME,
        "virtual_fixture": True,
        "seed": SEED,
        "field_roles": {
            "shared": sorted(set(PRICE_KEYS).intersection(
                item["key"] for item in EFFECT_FIELDS
            )),
            "price_only": sorted(set(PRICE_KEYS) - set(
                item["key"] for item in EFFECT_FIELDS
            )),
            "effectiveness_only": sorted(
                set(item["key"] for item in EFFECT_FIELDS) - set(PRICE_KEYS)
            ),
        },
        "data_types": sorted(set(
            item["value_type"] for item in EFFECT_FIELDS + PRICE_ONLY_FIELDS
        )),
        "counts": {
            "price_training_rows": len(price_records),
            "effectiveness_history_rows": len(effect_records),
            "business_agreements": len(business_package["data"]["agreements"]),
            "tags": len(business_package["data"]["tags"]),
            "tag_rules": len(business_package["data"]["tag_rules"]),
            "business_couplings": len(business_package["data"]["couplings"]),
            "effectiveness_couplings": len(EFFECT_COUPLINGS),
        },
        "price": price_manifest,
        "effectiveness_manifest": str(effect_manifest),
        "simulated_expert": {
            "state": str(state_path),
            "summary_stats": summary.get("stats"),
            "demo_profile": state.get("demo_profile"),
            "disclaimer": state["virtual_fixture"]["disclaimer"],
        },
        "delivery": {
            "package": delivery["package"],
            "sha256": delivery["sha256"],
            "sha256_file": delivery["sha256_file"],
            "formal": delivery["manifest"]["formal"],
        },
    }
    path = output / "fixture_manifest.json"
    path.write_text(
        json.dumps(fixture_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成虚拟正式成品全链路验收基准")
    sub = parser.add_subparsers(dest="command")
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--output-dir", required=True)
    finalize_parser = sub.add_parser("finalize")
    finalize_parser.add_argument("--output-dir", required=True)
    finalize_parser.add_argument("--workbook", required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        print(prepare(args.output_dir))
    elif args.command == "finalize":
        print(finalize(args.output_dir, args.workbook))
    else:
        parser.print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
