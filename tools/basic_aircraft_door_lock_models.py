# -*- coding: utf-8 -*-
"""Build virtual HTTP model artifacts for basic_aircraft_door_lock_history_demo.xlsx.

The field IDs deliberately match HistoricalProductOnboarding's deterministic
``attr_001`` ... ``attr_008`` inference for the source workbook.  This is a
functional fixture only; it must never be treated as an engineering or quote
model.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import math
import random
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.xlsx_utils import read_workbook_bytes
from services.price_service.export_native_price_bundle import export_from_notebook
from services.price_service.native_bundle import file_sha256, load_bundle, predict


PRODUCT_CODE = "AIRCRAFT_DOOR_LOCK_BASIC_DEMO"
PRODUCT_NAME = "基础航空舱门锁（虚拟功能演示）"
SEED = 20260812
PRICE_VERSION = "basic-aircraft-door-lock-price-20260812"
EFFECT_VERSION = "basic-aircraft-door-lock-effect-20260812"
MISSING = set(("", "-1", "\\", "/"))

FIELDS = [
    {"key":"attr_001", "label":"是否应急解锁", "dtype":"boolean", "unit":"", "required":True, "policy":"reject"},
    {"key":"attr_002", "label":"类型编码", "dtype":"enum", "unit":"", "required":True, "policy":"reject", "allowed":["0", "1"], "mapping":{"0":0.0, "1":1.0}},
    {"key":"attr_003", "label":"锁体材料", "dtype":"enum", "unit":"", "required":False, "policy":"default", "default":"高强铝合金", "allowed":["高强铝合金", "不锈钢", "钛合金"], "mapping":{"高强铝合金":0.0, "不锈钢":1.0, "钛合金":2.0}},
    {"key":"attr_004", "label":"锁定方式", "dtype":"enum", "unit":"", "required":False, "policy":"default", "default":"机械插销", "allowed":["机械插销", "旋转锁舌", "楔形锁块"], "mapping":{"机械插销":0.0, "旋转锁舌":1.0, "楔形锁块":2.0}},
    {"key":"attr_005", "label":"额定载荷", "dtype":"number", "unit":"N", "required":True, "policy":"reject"},
    {"key":"attr_006", "label":"重量", "dtype":"number", "unit":"kg", "required":False, "policy":"training_mean"},
    {"key":"attr_007", "label":"防护等级", "dtype":"ip_grade", "unit":"IP", "required":True, "policy":"reject", "parser":"ip_grade"},
]
PRICE_KEYS = [item["key"] for item in FIELDS]
EFFECT_KEYS = ["attr_001", "attr_005", "attr_007"]

HEADER_TO_KEY = {
    "是否应急解锁":"attr_001", "类型编码":"attr_002", "锁体材料":"attr_003",
    "锁定方式":"attr_004", "额定载荷(N)":"attr_005", "重量(kg)":"attr_006",
    "防护等级":"attr_007", "备注说明":"attr_008",
}


def _clean(value):
    return "" if value is None else str(value).strip()


def _missing(value):
    return _clean(value) in MISSING


def _number(value):
    text = _clean(value).upper()
    if text.startswith("IP"):
        text = text[2:]
    return float(text)


def read_source(path):
    sheets = read_workbook_bytes(Path(path).read_bytes())
    rows = sheets.get("历史成品") or next(iter(sheets.values()))
    headers = [_clean(value) for value in rows[0]]
    records = []
    for source in rows[1:]:
        raw = dict((headers[index], source[index] if index < len(source) else None) for index in range(len(headers)))
        item = {
            "scheme_id": _clean(raw.get("成品编号")),
            "scheme_name": _clean(raw.get("成品名称")),
            "price_wan": None if _missing(raw.get("价格(万元)")) else _number(raw.get("价格(万元)")),
        }
        for header, key in HEADER_TO_KEY.items():
            value = raw.get(header)
            if _missing(value):
                item[key] = None
            elif key == "attr_001":
                item[key] = 1 if _number(value) else 0
            elif key == "attr_002":
                item[key] = str(int(_number(value)))
            elif key in ("attr_005", "attr_006", "attr_007"):
                item[key] = _number(value)
            else:
                item[key] = _clean(value)
        records.append(item)
    return records


def _defaults(records):
    weights = [row["attr_006"] for row in records if row.get("attr_006") is not None]
    return {"attr_003":"高强铝合金", "attr_004":"机械插销", "attr_006":sum(weights) / len(weights)}


def _filled(row, defaults):
    result = dict(row)
    for key, value in defaults.items():
        if result.get(key) is None:
            result[key] = value
    return result


def _encode(row):
    by_key = dict((item["key"], item) for item in FIELDS)
    result = []
    for key in PRICE_KEYS:
        value = row[key]
        spec = by_key[key]
        if spec["dtype"] == "enum":
            value = spec["mapping"][str(value)]
        result.append(float(value))
    return result


def augmented_price_records(records, defaults):
    rng = random.Random(SEED)
    known = [_filled(row, defaults) for row in records if row.get("price_wan") is not None]
    output = []
    for base in known:
        for _index in range(48):
            row = dict(base)
            load_delta = rng.uniform(-360.0, 360.0)
            mass_delta = rng.uniform(-0.18, 0.18)
            grade_delta = rng.choice((-1, 0, 0, 0, 1))
            row["attr_005"] = round(min(15000.0, max(8000.0, base["attr_005"] + load_delta)), 2)
            row["attr_006"] = round(min(6.4, max(3.9, base["attr_006"] + mass_delta)), 3)
            row["attr_007"] = int(min(60, max(53, base["attr_007"] + grade_delta)))
            price = (base["price_wan"] + (row["attr_005"] - base["attr_005"]) * 0.00078
                     + (row["attr_006"] - base["attr_006"]) * 0.18
                     + (row["attr_007"] - base["attr_007"]) * 0.22
                     + rng.gauss(0.0, 0.10))
            row["price_wan"] = round(max(8.0, price), 5)
            output.append(row)
    rng.shuffle(output)
    return output


def train_price(records, output_dir):
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.preprocessing import StandardScaler

    defaults = _defaults(records)
    augmented = augmented_price_records(records, defaults)
    rows = np.asarray([_encode(row) for row in augmented], dtype=float)
    targets = np.log(np.asarray([row["price_wan"] for row in augmented], dtype=float))
    split = int(len(augmented) * 0.82)
    train_frame = pd.DataFrame(rows[:split], columns=PRICE_KEYS)
    test_array = rows[split:]
    scaler = StandardScaler().fit(train_frame.values)
    train_scaled = scaler.transform(train_frame.values)
    test_scaled = scaler.transform(test_array)
    models = {
        "ridge": Ridge(alpha=0.22).fit(train_scaled, targets[:split]),
        "gbdt": GradientBoostingRegressor(n_estimators=150, max_depth=2, learning_rate=0.04, random_state=SEED).fit(train_scaled, targets[:split]),
        "random_forest": RandomForestRegressor(n_estimators=180, max_depth=9, min_samples_leaf=2, random_state=SEED, n_jobs=1).fit(train_scaled, targets[:split]),
    }
    actual = np.exp(targets[split:])
    metrics = {}
    inverse_rmse = []
    for name, model in models.items():
        values = np.exp(model.predict(test_scaled))
        rmse = float(math.sqrt(mean_squared_error(actual, values)))
        metrics[name] = {"rmse_wan":rmse, "mae_wan":float(mean_absolute_error(actual, values)), "r2":float(r2_score(actual, values))}
        inverse_rmse.append(1.0 / max(rmse, 1e-9))
    total = sum(inverse_rmse)
    weights = [value / total for value in inverse_rmse]
    metadata = {}
    for item in FIELDS:
        metadata[item["key"]] = {
            "field_name":item["key"], "field_label":item["label"], "dtype":item["dtype"],
            "unit":item["unit"], "required":item["required"], "missing_policy":item["policy"],
            "default_value":item.get("default"), "allowed_values":item.get("allowed"),
            "category_mapping":item.get("mapping"), "parser":item.get("parser"),
            "source":"product_parameter",
        }
    namespace = {
        "X_train":train_frame, "X_test":test_array, "y_train":targets[:split], "y_test":actual,
        "scaler":scaler, "ridge_model":models["ridge"], "gbdt_model":models["gbdt"],
        "rf_model":models["random_forest"],
    }
    price_dir = Path(output_dir) / "price"
    price_dir.mkdir(parents=True, exist_ok=True)
    output = price_dir / "price_native_bundle.pkl"
    export_from_notebook(
        namespace, output=output, product_code=PRODUCT_CODE, product_name=PRODUCT_NAME,
        model_version=PRICE_VERSION, target_divisor_to_wan=1.0, field_metadata=metadata,
        ensemble_model_names=["ridge", "gbdt", "random_forest"], ensemble_weights=weights,
        strict=True, model_source="namespace",
    )
    bundle = load_bundle(output)
    source_predictions = []
    for row in records:
        sample = dict((key, row.get(key)) for key in PRICE_KEYS if row.get(key) is not None)
        result = predict(bundle, sample)
        source_predictions.append({
            "scheme_id":row["scheme_id"], "historical_price_wan":row.get("price_wan"),
            "predicted_price_wan":result["predicted_price_wan"], "filled_inputs":result.get("filled_inputs") or {},
        })
    known_errors = [abs(item["predicted_price_wan"] - item["historical_price_wan"]) for item in source_predictions if item["historical_price_wan"] is not None]
    report = {
        "virtual_fixture":True, "product_code":PRODUCT_CODE, "model_version":PRICE_VERSION,
        "source_rows":len(records), "augmented_training_rows":split, "augmented_test_rows":len(augmented)-split,
        "models":metrics, "ensemble_weights":dict(zip(models, weights)),
        "source_known_price_mae_wan":sum(known_errors) / len(known_errors),
        "source_known_price_max_error_wan":max(known_errors), "source_predictions":source_predictions,
        "bundle_sha256":file_sha256(output), "required_modules":bundle.get("required_modules"),
        "disclaimer":"确定性虚拟功能模型，不代表真实航空产品价格。",
    }
    (price_dir / "price_training_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output, report


def effectiveness_records(records):
    rng = random.Random(SEED + 1)
    result = []
    for index in range(48):
        base = records[index % len(records)]
        item = {
            "scheme_id":"BADL-E%03d" % (index + 1),
            "attr_001":int(base["attr_001"] if index < len(records) else rng.random() >= 0.45),
            "attr_005":round(min(15000.0, max(8000.0, base["attr_005"] + (0 if index < len(records) else rng.uniform(-420, 420)))), 2),
            "attr_007":int(min(60, max(53, base["attr_007"] + (0 if index < len(records) else rng.choice((-1, 0, 1)))))),
        }
        result.append(item)
    return result


def effect_payload(records):
    rows = effectiveness_records(records)
    scheme_rows = [["方案编号", "来源", "已知可行性", "是否应急解锁", "额定载荷", "防护等级"]]
    for row in rows:
        scheme_rows.append([row["scheme_id"], "基础历史表增强虚拟样本", "未标注", row["attr_001"], row["attr_005"], row["attr_007"]])
    attribute_rows = [
        ["属性名", "属性ID", "单位", "数据类型", "设计顺序", "显示精度", "生成下限", "生成上限", "可行下限", "可行上限", "偏好方向", "边际规律", "参与效能", "参与生成", "说明"],
        ["是否应急解锁", "attr_001", "", "整数", 1, 0, 0, 1, 0, 1, "越大越好", "具备应急解锁作为虚拟正向偏好", "是", "是", "与源表自动推断attr_001一致"],
        ["额定载荷", "attr_005", "N", "连续", 1, 0, 8000, 15000, 8000, 15000, "越大越好", "边际收益递减", "是", "是", "与源表自动推断attr_005一致"],
        ["防护等级", "attr_007", "IP", "整数", 2, 0, 53, 60, 53, 60, "越大越好", "边际收益递减", "是", "是", "与源表自动推断attr_007一致"],
    ]
    return {
        "product_code":PRODUCT_CODE, "product_name":PRODUCT_NAME,
        "sheets":{
            "生成说明":[["项目", PRODUCT_NAME], ["用途", "对应basic_aircraft_door_lock_history_demo.xlsx的虚拟功能校验"], ["随机种子", SEED], ["样本数量", len(rows)], ["免责声明", "不得用于真实工程、适航或商务决策"]],
            "项目信息":[["成品代号", PRODUCT_CODE], ["成品名称", PRODUCT_NAME], ["模型版本", EFFECT_VERSION], ["数据性质", "虚拟增强测试数据"]],
            "方案数据":scheme_rows,
            "属性配置":attribute_rows,
            "耦合关系":[["源属性", "目标属性", "方向", "关系类型", "先验系数", "置信状态", "说明"]],
            "新技术协议":[["协议编号", "协议名称", "是否应急解锁", "额定载荷", "防护等级", "说明"], ["BADL-REQ-001", "基础航空舱门锁虚拟目标协议", 1, 11500, 56, "仅用于软件功能校验"]],
        },
        "validations":{"方案数据":{"attr_001":[0,1], "attr_007":[53,54,55,56,57,58,59,60]}},
    }


def prepare(source, output_dir):
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    records = read_source(source)
    price_path, price_report = train_price(records, output)
    payload = effect_payload(records)
    (output / "effectiveness_workbook_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    source_sha = hashlib.sha256(Path(source).read_bytes()).hexdigest()
    prepare_manifest = {
        "format_version":"basic-aircraft-door-lock-model-fixture-1.0", "virtual_fixture":True,
        "product_code":PRODUCT_CODE, "product_name":PRODUCT_NAME, "source_workbook":str(Path(source).resolve()),
        "source_sha256":source_sha, "source_rows":len(records), "field_ids":["attr_%03d" % i for i in range(1,9)],
        "price_model":str(price_path), "price_report":price_report,
        "effectiveness_fields":EFFECT_KEYS,
    }
    (output / "prepare_manifest.json").write_text(json.dumps(prepare_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output / "effectiveness_workbook_payload.json"


def finalize(output_dir, workbook):
    from services.effectiveness_service.package_effectiveness_runtime import package_runtime
    output = Path(output_dir).resolve()
    source_root = ROOT / "services" / "effectiveness_service" / "original_runtime_demo"
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    from interactive_project_app import ProjectApp

    state_dir = output / "simulated_expert_state"
    if state_dir.exists():
        shutil.rmtree(str(state_dir))
    app = ProjectApp(Path(workbook).resolve(), state_dir=state_dir, seed=SEED)
    expert_summary = app.prepare_demo_state(preference_count=20)
    state_path = app.state_path
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["virtual_fixture"] = {"product_code":PRODUCT_CODE, "source":"basic_aircraft_door_lock_history_demo.xlsx", "disclaimer":"虚拟专家状态，仅供功能校验"}
    state["data_mode"] = "basic_aircraft_door_lock_virtual_expert_simulation"
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    effect_manifest = package_runtime(source_root, workbook, output / "effectiveness_runtime", state_path)
    manifest = json.loads((output / "prepare_manifest.json").read_text(encoding="utf-8"))
    manifest.update({
        "effectiveness_workbook":str(Path(workbook).resolve()), "effectiveness_manifest":str(effect_manifest),
        "simulated_expert_state":str(state_path), "simulated_expert_stats":expert_summary.get("stats"),
    })
    (output / "fixture_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return effect_manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成基础航空舱门锁虚拟价格/效能模型")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("prepare"); p.add_argument("--source", required=True); p.add_argument("--output-dir", required=True)
    f = sub.add_parser("finalize"); f.add_argument("--output-dir", required=True); f.add_argument("--effectiveness-workbook", required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        print(prepare(args.source, args.output_dir))
    elif args.command == "finalize":
        print(finalize(args.output_dir, args.effectiveness_workbook))
    else:
        parser.print_help(); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
