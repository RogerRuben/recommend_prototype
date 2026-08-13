# -*- coding: utf-8 -*-
"""Leakage-safe price model exporter for recommendation contract 4.0.

The original Notebook's final pkl files are not sufficient for deployment because
they do not preserve a complete, reproducible preprocessing and ensemble chain.
This module retrains a compact pure-JSON ridge ensemble from the raw dataframe.
"""
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Union

import numpy as np
import pandas as pd

EXCLUDE_DEFAULT = {"价格", "价格类别", "Cluster", "is_outlier", "index", "Unnamed: 0"}


def _ridge(x, y, alpha):
    design = np.column_stack([np.ones(len(x)), x])
    penalty = np.eye(design.shape[1]) * float(alpha)
    penalty[0, 0] = 0.0
    coef = np.linalg.pinv(design.T @ design + penalty) @ design.T @ y
    return float(coef[0]), [float(v) for v in coef[1:]]


def _mape(y_true, y_pred):
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred)) / np.maximum(np.abs(y_true), 1e-12)))


def _r2(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = float(np.sum((y_true - y_true.mean()) ** 2))
    return 0.0 if denom <= 1e-12 else float(1.0 - np.sum((y_true - y_pred) ** 2) / denom)


def _load_field_map(field_map):
    if field_map is None:
        return {}
    if isinstance(field_map, (str, Path)):
        return json.loads(Path(field_map).read_text(encoding="utf-8"))
    return dict(field_map)


def _field_info(source_column, field_map):
    raw = field_map.get(source_column, source_column)
    if isinstance(raw, str):
        return {"parameter_id": raw, "label": source_column}
    info = dict(raw)
    info.setdefault("parameter_id", source_column)
    info.setdefault("label", source_column)
    return info


def export_price_bundle(
    df: pd.DataFrame,
    output: Union[str, Path],
    product_code: str,
    target: str = "价格",
    feature_columns: Optional[Sequence[str]] = None,
    model_version: str = "price-v19.5",
    random_seed: int = 20260728,
    field_map=None,
    target_divisor: float = 1.0,
    product_name: Optional[str] = None,
) -> Dict[str, Any]:
    if target not in df.columns:
        raise ValueError("目标列不存在: %s" % target)
    if feature_columns is None:
        feature_columns = [
            c for c in df.columns
            if c not in (EXCLUDE_DEFAULT | {target}) and pd.api.types.is_numeric_dtype(df[c])
        ]
    feature_columns = list(feature_columns)
    if not feature_columns:
        raise ValueError("没有可用数值特征；正式项目请显式填写FEATURE_COLUMNS")
    leakage = [c for c in feature_columns if c == target or "价格" in str(c)]
    if leakage:
        raise ValueError("检测到疑似价格泄漏字段: " + ",".join(map(str, leakage)))

    mapping = _load_field_map(field_map)
    infos = [_field_info(c, mapping) for c in feature_columns]
    parameter_ids = [str(x["parameter_id"]) for x in infos]
    if len(parameter_ids) != len(set(parameter_ids)):
        raise ValueError("字段映射后parameter_id重复")

    clean = df[feature_columns + [target]].replace([np.inf, -np.inf], np.nan).dropna().copy()
    clean = clean[clean[target].astype(float) > 0]
    if len(clean) < 12:
        raise ValueError("有效样本少于12条，不能可靠导出")

    if float(target_divisor) <= 0:
        raise ValueError("target_divisor必须大于0")
    x = clean[feature_columns].astype(float).to_numpy()
    y_raw = clean[target].astype(float).to_numpy() / float(target_divisor)
    y = np.log(y_raw)
    rng = np.random.RandomState(int(random_seed))
    idx = np.arange(len(x))
    rng.shuffle(idx)
    cut = max(3, int(0.8 * len(idx)))
    if cut >= len(idx):
        cut = len(idx) - 1
    train, test = idx[:cut], idx[cut:]

    xmin_train = x[train].min(0)
    xmax_train = x[train].max(0)
    span_train = np.where(xmax_train - xmin_train < 1e-12, 1.0, xmax_train - xmin_train)
    xtr = (x[train] - xmin_train) / span_train
    xte = (x[test] - xmin_train) / span_train

    alphas = [0.01, 0.1, 1.0]
    members_holdout = []
    validation_errors = []
    for alpha in alphas:
        intercept, coefficients = _ridge(xtr, y[train], alpha)
        pred = np.exp(intercept + xte @ np.asarray(coefficients))
        mape = max(_mape(y_raw[test], pred), 1e-6)
        validation_errors.append(mape)
        members_holdout.append({
            "name": "ridge_%g" % alpha,
            "alpha": alpha,
            "intercept": intercept,
            "coefficients": coefficients,
            "holdout_mape": mape,
        })
    inv = np.asarray([1.0 / value for value in validation_errors], dtype=float)
    inv /= inv.sum()
    holdout_log = sum(
        float(weight) * (member["intercept"] + xte @ np.asarray(member["coefficients"]))
        for member, weight in zip(members_holdout, inv)
    )
    holdout_pred = np.exp(holdout_log)
    holdout_mape = _mape(y_raw[test], holdout_pred)
    holdout_r2 = _r2(y_raw[test], holdout_pred)

    # Refit final members on all clean data and persist one shared scaler.
    xmin = x.min(0)
    xmax = x.max(0)
    span = np.where(xmax - xmin < 1e-12, 1.0, xmax - xmin)
    xs = (x - xmin) / span
    final = []
    for alpha, weight in zip(alphas, inv):
        intercept, coefficients = _ridge(xs, y, alpha)
        final.append({
            "name": "ridge_%g" % alpha,
            "alpha": alpha,
            "intercept": intercept,
            "coefficients": coefficients,
            "weight": float(weight),
        })
    fitted_log = sum(
        member["weight"] * (member["intercept"] + xs @ np.asarray(member["coefficients"]))
        for member in final
    )
    residual = y - fitted_log
    qlo, qhi = np.quantile(residual, [0.025, 0.975])

    schema = []
    bindings = []
    for i, (source_column, info) in enumerate(zip(feature_columns, infos)):
        field_name = str(info["parameter_id"])
        dtype = str(info.get("dtype") or "number")
        unit = str(info.get("unit") or "")
        missing_policy = str(info.get("missing_policy") or "training_mean")
        training_mean = float(x[:, i].mean())
        schema.append({
            "field_name": field_name,
            "field_label": str(info.get("label") or source_column),
            "source_column": str(source_column),
            "dtype": dtype,
            "unit": unit,
            "required": bool(info.get("required", True)),
            "training_min": float(xmin[i]),
            "training_max": float(xmax[i]),
            "training_mean": training_mean,
            "generation_min": float(info.get("generation_min", xmin[i])),
            "generation_max": float(info.get("generation_max", xmax[i])),
            "precision": int(info.get("precision", 3)),
            "search_type": str(info.get("search_type") or ("integer" if dtype in ("integer", "ip_grade") else "continuous")),
            "allowed_values": info.get("allowed_values"),
            "editable": bool(info.get("editable", True)),
            "auto_adjustable": bool(info.get("auto_adjustable", True)),
            "description": str(info.get("description") or "价格模型输入属性。"),
            "adjustment_hint": str(info.get("adjustment_hint") or "调整后将重新计算预测价格。"),
        })
        binding = {
            "model_kind": "price",
            "field_name": field_name,
            "field_label": str(info.get("label") or source_column),
            "source_type": str(info.get("source_type") or "product_parameter"),
            "dtype": dtype,
            "unit": unit,
            "required": bool(info.get("required", True)),
            "missing_policy": missing_policy,
            "training_mean": training_mean,
            "model_version": model_version,
            "enabled": True,
        }
        if "configured_value" in info:
            binding["configured_value"] = info["configured_value"]
        bindings.append(binding)

    bundle = {
        "recommendation_contract_version": "4.0",
        "model_kind": "price",
        "product_code": str(product_code),
        "product_name": str(product_name or product_code),
        "model_version": str(model_version),
        "feature_schema": schema,
        "model_input_bindings": bindings,
        "target_name": target,
        "target_unit": "万元",
        "target_divisor_to_wan": float(target_divisor),
        "target_transform": "log",
        "preprocessing": {
            "type": "minmax",
            "feature_order": parameter_ids,
            "source_feature_order": [str(x) for x in feature_columns],
            "min": [float(v) for v in xmin],
            "max": [float(v) for v in xmax],
        },
        "ensemble": {"aggregation": "weighted_mean_log_prediction", "members": final},
        "residual_calibration": {
            "coverage": 0.95,
            "log_residual_lower": float(qlo),
            "log_residual_upper": float(qhi),
            "sample_count": len(clean),
        },
        "training_metrics": {
            "holdout_r2": holdout_r2,
            "holdout_mape": holdout_mape,
            "holdout_count": len(test),
        },
        "training_report": {
            "sample_count": len(clean),
            "holdout_count": len(test),
            "holdout_mape_by_member": {
                member["name"]: member["holdout_mape"] for member in members_holdout
            },
            "feature_columns": [str(x) for x in feature_columns],
            "parameter_ids": parameter_ids,
            "field_mapping": {str(c): str(i["parameter_id"]) for c, i in zip(feature_columns, infos)},
            "leakage_columns_excluded": sorted(EXCLUDE_DEFAULT | {target}),
            "data_sha256": hashlib.sha256(clean.to_csv(index=False).encode("utf-8")).hexdigest(),
            "random_seed": int(random_seed),
            "target_divisor_to_wan": float(target_divisor),
        },
    }
    from model_contract_v4 import validate_bundle
    errors = validate_bundle(bundle, "price")
    if errors:
        raise ValueError("导出模型未通过契约校验: " + ";".join(errors))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return bundle


def notebook_export_from_globals(
    namespace: Dict[str, Any],
    output="price_bundle.json",
    product_code="PRODUCT_CODE",
    target="价格",
    feature_columns=None,
    model_version="price-v19.5",
    field_map=None,
    target_divisor=1.0,
    product_name=None,
):
    if "df" not in namespace:
        raise ValueError("Notebook全局变量中没有df")
    return export_price_bundle(
        namespace["df"], output, product_code, target, feature_columns,
        model_version=model_version, field_map=field_map,
        target_divisor=target_divisor, product_name=product_name,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--product-code", required=True)
    parser.add_argument("--target", default="价格")
    parser.add_argument("--features", default="")
    parser.add_argument("--field-map")
    parser.add_argument("--model-version", default="price-v19.5")
    parser.add_argument("--target-divisor", type=float, default=1.0, help="原始价格除以该数后作为万元，例如原始单位为元时填写10000")
    parser.add_argument("--product-name", default="")
    args = parser.parse_args()
    path = Path(args.data)
    dataframe = pd.read_excel(path) if path.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(path)
    features = [x.strip() for x in args.features.split(",") if x.strip()] or None
    bundle = export_price_bundle(
        dataframe, args.output, args.product_code, args.target, features,
        args.model_version, field_map=args.field_map,
        target_divisor=args.target_divisor, product_name=args.product_name or None,
    )
    print(json.dumps({
        "status": "PASS",
        "output": args.output,
        "features": len(bundle["feature_schema"]),
        "training_metrics": bundle["training_metrics"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
