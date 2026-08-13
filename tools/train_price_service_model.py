# -*- coding: utf-8 -*-
"""Train and export an independent price-service bundle from one history table.

This is the supported operator entry point.  It does not require a Notebook,
saved model directory, fixed model count, or hand-written ensemble weights.
"""
from __future__ import print_function

import argparse
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.historical_onboarding import (
    ID_HEADERS, NAME_HEADERS, PRICE_HEADERS, POSITION_HEADERS, SUPPLIER_HEADERS,
    TAG_HEADERS, TEXT_HEADER, YEAR_HEADERS, _header_key, _infer_parameter,
    _is_missing, _parameter_id, parse_missing_tokens,
)
from app.wide_import import read_table_bytes
from services.price_service.export_native_price_bundle import export_from_notebook


def repair_text(value):
    text = str(value if value is not None else "").strip()
    try:
        repaired = text.encode("latin1").decode("gbk")
        if any("\u4e00" <= ch <= "\u9fff" for ch in repaired):
            return repaired
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return text


def clean(value):
    return repair_text(value).strip()


def number(value):
    text = clean(value).replace(",", "")
    text = re.sub(r"^ip\s*", "", text, flags=re.I)
    return float(text)


def load_rows(path):
    rows = read_table_bytes(Path(path).name, Path(path).read_bytes())
    return [[repair_text(value) for value in row] for row in rows if any(clean(value) for value in row)]


def detect_target(headers, requested=None):
    if requested:
        if requested in headers:
            return headers.index(requested)
        normalized = _header_key(requested)
        for index, header in enumerate(headers):
            if _header_key(header) == normalized:
                return index
        raise ValueError("找不到价格列：%s" % requested)
    for index, header in enumerate(headers):
        key = _header_key(header)
        if key in PRICE_HEADERS or "价格" in header or key in ("price", "target", "y"):
            return index
    raise ValueError("未自动识别价格列；请用 --target 指定列名")


def price_to_wan(value, header, unit):
    raw = number(value)
    selected = str(unit or "auto").lower()
    if selected == "auto":
        normalized = _header_key(header)
        selected = "wan" if "万元" in header or "wan" in normalized else "qianyuan" if "千元" in header else "yuan" if "元" in header else "wan"
    return raw if selected == "wan" else raw / 10.0 if selected == "qianyuan" else raw / 10000.0


def build_dataset(rows, target_name=None, missing_tokens=None, include_text=False):
    if len(rows) < 4:
        raise ValueError("价格训练表至少需要表头和3条具有价格的数据")
    headers = [clean(value) for value in rows[0]]
    width = len(headers)
    body = [list(row) + [""] * max(0, width - len(row)) for row in rows[1:]]
    tokens = parse_missing_tokens(missing_tokens or ["-1", "\\", "/"])
    target_index = detect_target(headers, target_name)
    reserved = ID_HEADERS | NAME_HEADERS | TAG_HEADERS | YEAR_HEADERS | SUPPLIER_HEADERS | POSITION_HEADERS
    used, feature_specs, attribute_order = set(), [], 0
    for index, header in enumerate(headers):
        if index == target_index or not header:
            continue
        key = _header_key(header)
        if key in reserved:
            continue
        attribute_order += 1
        field_name = _parameter_id(header, attribute_order, used)
        values = [row[index] if index < len(row) else "" for row in body]
        inferred = _infer_parameter(header, field_name, values, tokens, attribute_order)
        if inferred["value_type"] == "text" and not include_text:
            continue
        feature_specs.append((index, inferred))
    if not feature_specs:
        raise ValueError("没有识别到可训练的价格属性；文本说明列默认不会参与模型")

    records, targets = [], []
    for row in body:
        target_raw = row[target_index] if target_index < len(row) else ""
        if _is_missing(target_raw, tokens):
            continue
        targets.append(target_raw)
        records.append(row)
    if len(records) < 3:
        raise ValueError("具有有效价格的历史成品少于3条，无法训练价格模型")

    columns, metadata = {}, {}
    for index, spec in feature_specs:
        key, dtype = spec["parameter_id"], spec["value_type"]
        observed = [clean(row[index]) for row in records if not _is_missing(row[index], tokens)]
        if not observed:
            raise ValueError("属性%s没有任何有效训练值" % spec["label"])
        mapping = None
        if dtype in ("enum", "text"):
            allowed = []
            for value in observed:
                if value not in allowed:
                    allowed.append(value)
            mapping = dict((value, float(i)) for i, value in enumerate(allowed))
            converted = [None if _is_missing(row[index], tokens) else mapping[clean(row[index])] for row in records]
            fill = max(allowed, key=observed.count)
            fill_numeric = mapping[fill]
        elif dtype == "boolean":
            truth = set(("1", "true", "yes", "y", "有", "是", "启用", "具备", "支持"))
            converted = [None if _is_missing(row[index], tokens) else (1.0 if clean(row[index]).lower() in truth else 0.0) for row in records]
            fill_numeric = sum(x for x in converted if x is not None) / max(1, sum(x is not None for x in converted))
        else:
            converted = [None if _is_missing(row[index], tokens) else number(row[index]) for row in records]
            numeric = sorted(x for x in converted if x is not None)
            fill_numeric = numeric[len(numeric) // 2]
        columns[key] = [fill_numeric if value is None else value for value in converted]
        required = not any(value is None for value in converted)
        metadata[key] = {
            "field_name": key, "field_label": spec["label"], "unit": spec.get("unit") or "",
            "dtype": dtype, "required": required,
            "missing_policy": "reject" if required else "training_mean",
            "default_value": None if required else fill_numeric,
            "training_mode": fill_numeric,
            "allowed_values": list(mapping) if mapping else ([0, 1] if dtype == "boolean" else None),
            "category_mapping": mapping, "parser": "ip_grade" if dtype == "ip_grade" else None,
            "source": "product_parameter",
        }
    return columns, targets, metadata, headers[target_index]


def train(input_path, output, product_code, product_name="", target=None, target_unit="auto",
          missing_tokens=None, model_version=None, include_text=False, seed=20260812):
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.metrics import mean_absolute_error
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVR

    columns, raw_targets, metadata, target_header = build_dataset(
        load_rows(input_path), target, missing_tokens, include_text
    )
    frame = pd.DataFrame(columns, dtype=float)
    y = np.asarray([price_to_wan(value, target_header, target_unit) for value in raw_targets], dtype=float)
    indices = np.arange(len(frame)); rng = np.random.RandomState(int(seed)); rng.shuffle(indices)
    test_count = max(1, min(len(frame) // 5, len(frame) - 2))
    test_idx, train_idx = indices[:test_count], indices[test_count:]
    X_train, X_test = frame.iloc[train_idx].copy(), frame.iloc[test_idx].copy()
    y_train, y_test = y[train_idx], y[test_idx]
    scaler = StandardScaler().fit(X_train.values)
    train_scaled, test_scaled = scaler.transform(X_train), scaler.transform(X_test)
    factories = [
        ("ridge", lambda: Ridge(alpha=0.8)),
        ("random_forest", lambda: RandomForestRegressor(n_estimators=180, max_depth=10, min_samples_leaf=1, random_state=seed, n_jobs=1)),
        ("extra_trees", lambda: ExtraTreesRegressor(n_estimators=180, max_depth=12, min_samples_leaf=1, random_state=seed, n_jobs=1)),
        ("gbdt", lambda: GradientBoostingRegressor(n_estimators=160, max_depth=2, learning_rate=0.04, random_state=seed)),
        ("svr", lambda: SVR(C=12.0, epsilon=0.04, gamma="scale")),
    ]
    models, failures, metrics = {}, {}, {}
    for name, factory in factories:
        try:
            model = factory().fit(train_scaled, y_train)
            predicted = model.predict(test_scaled)
            mae = float(mean_absolute_error(y_test, predicted))
            models[name] = model
            metrics[name] = {"mae_wan": mae}
        except Exception as exc:
            failures[name] = str(exc)
    if not models:
        raise RuntimeError("没有任何价格模型训练成功：%s" % failures)
    inverse = [1.0 / max(metrics[name]["mae_wan"], 1e-6) for name in models]
    total = sum(inverse); weights = [value / total for value in inverse]
    namespace = {"X_train": X_train, "X_test": X_test, "y_train": y_train, "y_test": y_test,
                 "scaler": scaler, "weights": weights}
    variables = {}
    for index, (name, model) in enumerate(models.items()):
        variable = "trained_model_%d" % index
        namespace[variable] = model; variables[name] = variable
    version = model_version or "price-service-%s" % datetime.now().strftime("%Y%m%d-%H%M%S")
    bundle = export_from_notebook(
        namespace, output=output, product_code=product_code,
        product_name=product_name or product_code, model_version=version,
        target_divisor_to_wan=1.0, field_metadata=metadata,
        model_variables=variables, ensemble_model_names=list(models), ensemble_weights=weights,
        strict=False, model_source="namespace", model_output_transform="direct",
    )
    report = {
        "input": str(Path(input_path).resolve()), "output": str(Path(output).resolve()),
        "product_code": product_code, "model_version": version,
        "training_rows": int(len(train_idx)), "test_rows": int(len(test_idx)),
        "feature_count": len(columns), "features": list(columns), "target_column": target_header,
        "target_unit": target_unit, "trained_models": list(models), "failed_optional_models": failures,
        "weights": dict(zip(models, weights)), "metrics": metrics,
        "service_install": "复制price_native_bundle.pkl及manifest到services/price_service/model后重启价格服务",
    }
    report_path = Path(str(output) + ".training.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return bundle, report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="从一张历史成品表直接训练并导出独立价格服务模型（模型数量不限）",
        epilog="示例：python tools/train_price_service_model.py 历史成品.xlsx PRODUCT_A --target 价格(万元)",
    )
    parser.add_argument("input", nargs="?", help="CSV或XLSX历史成品表")
    parser.add_argument("product_code", nargs="?", help="价格服务成品代号")
    parser.add_argument("--output", default=str(ROOT / "services" / "price_service" / "model" / "price_native_bundle.pkl"))
    parser.add_argument("--product-name", default="")
    parser.add_argument("--target", help="价格列名；省略时自动识别")
    parser.add_argument("--target-unit", choices=("auto", "wan", "yuan", "qianyuan"), default="auto")
    parser.add_argument("--missing", default="-1,\\,/")
    parser.add_argument("--model-version")
    parser.add_argument("--include-text", action="store_true", help="也将普通文本列作为枚举训练")
    args = parser.parse_args(argv)
    if not args.input or not args.product_code:
        parser.print_help()
        print("\n无需model-dir、workbook、模型文件映射或固定模型数量。")
        return 0
    _bundle, report = train(
        args.input, args.output, args.product_code, args.product_name, args.target,
        args.target_unit, parse_missing_tokens(args.missing), args.model_version, args.include_text,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
