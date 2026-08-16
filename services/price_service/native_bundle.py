# -*- coding: utf-8 -*-
"""Native price model bundle using standard-library pickle.

The bundle keeps the exact fitted estimator objects, scaler, feature order,
ensemble weights, target transformation and calibration information. joblib is
not required. Loading exact estimators still requires the same estimator
libraries and compatible versions used for training.
"""
from __future__ import print_function

import hashlib
import importlib
import json
import math
import os
import pickle
import platform
import sys
from pathlib import Path


FORMAT_VERSION = "price-native-bundle-1.0"


def _version(module_name):
    try:
        module = importlib.import_module(module_name)
        return str(getattr(module, "__version__", "unknown"))
    except Exception:
        return None


def environment_versions():
    return {
        "python": "%s.%s.%s" % sys.version_info[:3],
        "platform": platform.platform(),
        "numpy": _version("numpy"),
        "scikit_learn": _version("sklearn"),
        "xgboost": _version("xgboost"),
        "joblib": _version("joblib"),
    }


def save_bundle(path, bundle):
    data = dict(bundle)
    data["format_version"] = FORMAT_VERSION
    data.setdefault("training_environment", environment_versions())
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("wb") as handle:
        pickle.dump(data, handle, protocol=4)  # protocol 4 is supported by Python 3.8
    os.replace(str(temporary), str(target))
    return target


def load_bundle(path):
    with Path(path).open("rb") as handle:
        bundle = pickle.load(handle)
    if not isinstance(bundle, dict) or bundle.get("format_version") != FORMAT_VERSION:
        raise ValueError("价格模型文件不是%s格式" % FORMAT_VERSION)
    validate_bundle(bundle)
    return bundle


def active_model_names(bundle):
    return [str(item.get("name")) for item in (bundle.get("ensemble", {}).get("members") or [])]


def _category_mapping(spec):
    raw = spec.get("category_mapping")
    if isinstance(raw, dict) and raw:
        mapping = dict((str(key), float(value)) for key, value in raw.items())
    else:
        allowed = spec.get("allowed_values") or []
        mapping = dict((str(value), float(index)) for index, value in enumerate(allowed))
    if not mapping:
        raise ValueError("枚举字段%s缺少category_mapping或allowed_values" % (
            spec.get("field_name") or spec.get("key") or "（未知）"
        ))
    if any(not math.isfinite(value) for value in mapping.values()):
        raise ValueError("枚举字段映射值必须是有限数")
    return mapping


def validate_bundle(bundle):
    required = ["product_code", "model_version", "feature_order", "models", "ensemble", "target_transform"]
    missing = [name for name in required if name not in bundle]
    if missing:
        raise ValueError("价格模型包缺少: %s" % ",".join(missing))
    if not bundle.get("feature_order"):
        raise ValueError("feature_order为空")
    if not bundle.get("models"):
        raise ValueError("models为空")
    members = bundle.get("ensemble", {}).get("members") or []
    names = [str(item.get("name")) for item in members]
    if not names:
        raise ValueError("ensemble.members为空")
    if len(set(names)) != len(names):
        raise ValueError("ensemble.members包含重复模型名")
    unknown = [name for name in names if name not in bundle["models"]]
    if unknown:
        raise ValueError("集成配置引用不存在模型: %s" % ",".join(map(str, unknown)))
    weights = [float(item.get("weight", 0)) for item in members]
    if any((not math.isfinite(weight)) or weight < 0 for weight in weights):
        raise ValueError("集成权重必须是非负有限数")
    if not weights or sum(weights) <= 0:
        raise ValueError("集成权重无效")
    feature_order = [str(item) for item in bundle.get("feature_order") or []]
    schema = _field_map(bundle)
    missing_schema = [key for key in feature_order if key not in schema]
    if missing_schema:
        raise ValueError("feature_schema缺少字段: %s" % ",".join(missing_schema))
    for key in feature_order:
        spec = schema[key]
        dtype = str(spec.get("dtype") or spec.get("data_type") or "number").lower()
        if dtype in ("enum", "category", "categorical"):
            _category_mapping(spec)
    return True


def _parse_bool(value):
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return 1.0 if float(value) != 0 else 0.0
    text = str(value or "").strip().lower()
    if text in ("1", "true", "yes", "y", "on", "是", "有", "具备", "启用"):
        return 1.0
    if text in ("0", "false", "no", "n", "off", "否", "无", "不具备", "停用", ""):
        return 0.0
    raise ValueError("无法识别布尔值: %s" % value)


def _field_map(bundle):
    return dict((str(x.get("field_name") or x.get("key")), x) for x in bundle.get("feature_schema", []))


def _named_matrix(bundle, rows):
    """Build a column-named frame so fitted estimators can validate feature order.

    The bundled scaler and every estimator were fitted on a pandas DataFrame, so
    they carry ``feature_names_in_``.  Feeding them a bare numpy array produces
    the ``X does not have valid feature names`` warning and, more importantly,
    skips sklearn's column-order validation.  Return a named frame when pandas is
    available, otherwise fall back to a plain numeric array (order is preserved).
    """
    columns = [str(x) for x in bundle.get("feature_order") or []]
    try:
        import pandas as pd
        return pd.DataFrame(rows, columns=columns)
    except Exception:
        try:
            import numpy as np
            return np.asarray(rows, dtype=float)
        except Exception:
            return list(rows)


def _named_transform(preprocessor, frame, fallback_names):
    """Transform a named frame and re-attach feature names on the output."""
    transformed = preprocessor.transform(frame)
    if hasattr(transformed, "columns"):
        return transformed
    names = list(fallback_names or [])
    try:
        names = list(preprocessor.get_feature_names_out())
    except Exception:
        pass
    try:
        import pandas as pd
        return pd.DataFrame(transformed, columns=names)
    except Exception:
        return transformed


def _matrix_rows(matrix):
    """Convert a frame/array to a list of row lists for rebuilding a matrix."""
    try:
        import numpy as np
        arr = np.asarray(matrix)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return arr.tolist()
    except Exception:
        return list(matrix)


def prepare_vector(bundle, parameters):
    parameters = dict(parameters or {})
    specs = _field_map(bundle)
    values, filled, ignored, warnings = [], {}, [], []
    for key in bundle["feature_order"]:
        spec = specs.get(key, {})
        value = parameters.get(key)
        if value in (None, ""):
            policy = str(spec.get("missing_policy") or ("reject" if spec.get("required", True) else "training_mean"))
            if policy == "reject":
                raise ValueError("价格模型缺少必填字段%s" % key)
            if policy == "training_mean":
                value = spec.get("training_mean")
            elif policy in ("default", "configured_value", "constant"):
                value = spec.get("default_value", spec.get("configured_value", spec.get("constant")))
            elif policy == "zero":
                value = 0
            elif policy == "mode":
                value = spec.get("training_mode")
            else:
                raise ValueError("字段%s缺失策略不支持: %s" % (key, policy))
            if value in (None, ""):
                raise ValueError("字段%s缺失且补全值为空" % key)
            filled[key] = {"value": value, "strategy": policy}
        dtype = str(spec.get("dtype") or spec.get("data_type") or "number")
        if dtype == "boolean":
            numeric = _parse_bool(value)
        elif dtype == "ip_grade":
            numeric = float(str(value).strip().upper().replace("IP", ""))
        elif dtype in ("enum", "category", "categorical"):
            mapping = _category_mapping(spec)
            text = str(value).strip()
            if text in mapping:
                numeric = mapping[text]
            else:
                normalized = dict((key.strip().lower(), numeric_value) for key, numeric_value in mapping.items())
                lookup = text.lower()
                if lookup not in normalized:
                    raise ValueError(
                        "字段%s枚举值%s不在允许范围%s"
                        % (key, value, "、".join(mapping.keys()))
                    )
                numeric = normalized[lookup]
        else:
            numeric = float(value)
        lo, hi = spec.get("training_min"), spec.get("training_max")
        if lo is not None and numeric < float(lo):
            warnings.append("%s低于训练范围下限%s" % (spec.get("field_label", key), lo))
        if hi is not None and numeric > float(hi):
            warnings.append("%s高于训练范围上限%s" % (spec.get("field_label", key), hi))
        values.append(numeric)
    ignored = sorted(set(parameters) - set(bundle["feature_order"]))
    array = _named_matrix(bundle, [values])
    preprocessor = bundle.get("preprocessor")
    if preprocessor is not None:
        array = _named_transform(preprocessor, array, bundle.get("feature_order"))
    return array, {"filled_fields": filled, "ignored_fields": ignored, "warnings": warnings}


def _model_prediction(model, prepared):
    value = model.predict(prepared)
    try:
        return float(value[0])
    except Exception:
        return float(value)


def _declared_transform(bundle):
    return "log" if str(bundle.get("model_output_transform") or "log") == "log" else "identity"


def _apply_transform(raw, transform):
    return math.exp(raw) if transform == "log" else raw


def _ensemble_price(bundle, prepared, transform, allow_degraded):
    """Ensemble price for one prepared row under a given output transform."""
    members = bundle["ensemble"]["members"]
    predictions, skipped = [], []
    for item in members:
        name = item["name"]
        model = bundle["models"].get(name)
        if model is None:
            skipped.append({"name": name, "reason": "model_missing"})
            continue
        try:
            raw = _model_prediction(model, prepared)
        except Exception as exc:
            if not allow_degraded:
                raise
            skipped.append({"name": name, "reason": str(exc)})
            continue
        predictions.append({
            "name": name, "weight": float(item.get("weight", 1)),
            "raw": raw, "price_native": _apply_transform(raw, transform),
        })
    if not predictions:
        raise RuntimeError("没有可用的价格子模型")
    total_weight = sum(max(0.0, x["weight"]) for x in predictions)
    if total_weight <= 0:
        raise RuntimeError("可用模型权重总和为0")
    method = bundle.get("ensemble", {}).get("aggregation", "weighted_mean_price")
    if method == "weighted_mean_log_prediction":
        log_value = sum(max(0.0, x["weight"]) * x["raw"] for x in predictions) / total_weight
        price_native = math.exp(log_value)
    else:
        price_native = sum(max(0.0, x["weight"]) * x["price_native"] for x in predictions) / total_weight
    return price_native, predictions, skipped


def _self_check_transform(bundle, prepared, transform, price_wan, allow_degraded):
    """Return the alternative transform when the current one is implausible.

    A bundle whose ``model_output_transform`` is wrong produces prices many
    orders of magnitude away from the target's typical value.  The exporter
    stores ``target_reference_wan`` (the median held-out price) for exactly this
    guard: if the declared transform lands far outside the reference, retry with
    the opposite transform and keep it only when it is closer.
    """
    reference = bundle.get("target_reference_wan")
    if reference in (None, ""):
        return None
    try:
        reference = float(reference)
    except (TypeError, ValueError):
        return None
    if not (reference > 0 and price_wan > 0):
        return None
    ratio = price_wan / reference
    if 0.01 <= ratio <= 100.0:
        return None
    alt = "identity" if transform == "log" else "log"
    divisor = float(bundle.get("target_divisor_to_wan") or 1.0)
    try:
        alt_native, _alt_pred, _alt_skip = _ensemble_price(bundle, prepared, alt, allow_degraded)
        alt_wan = alt_native / divisor
    except Exception:
        return None
    if alt_wan <= 0:
        return None
    alt_ratio = alt_wan / reference
    if abs(alt_ratio - 1.0) < abs(ratio - 1.0):
        return alt
    return None


def predict(bundle, parameters, allow_degraded=False):
    prepared, input_status = prepare_vector(bundle, parameters)
    transform = _declared_transform(bundle)
    price_native, predictions, skipped = _ensemble_price(bundle, prepared, transform, allow_degraded)
    divisor = float(bundle.get("target_divisor_to_wan") or 1.0)
    price_wan = price_native / divisor
    corrected_transform = _self_check_transform(bundle, prepared, transform, price_wan, allow_degraded)
    corrected = False
    if corrected_transform is not None and corrected_transform != transform:
        price_native, predictions, skipped = _ensemble_price(bundle, prepared, corrected_transform, allow_degraded)
        price_wan = price_native / divisor
        corrected = True
    residual = bundle.get("residual_calibration") or {}
    if residual.get("space") == "log":
        lower = price_wan * math.exp(float(residual.get("lower", 0)))
        upper = price_wan * math.exp(float(residual.get("upper", 0)))
    else:
        delta = float(residual.get("half_width_native", residual.get("half_width", 0))) / divisor
        lower, upper = max(0.0, price_wan - delta), price_wan + delta
    status = "exact" if not skipped else "degraded"
    result = {
        "predicted_price_wan": round(price_wan, 6),
        "price_interval_wan": [round(lower, 6), round(upper, 6)],
        "prediction_mode": "native_pickle_%s" % status,
        "member_predictions": predictions,
        "skipped_members": skipped,
        "input_status": input_status,
        "confidence": "low" if skipped or input_status["warnings"] else "medium",
    }
    if corrected:
        result["output_transform_corrected"] = corrected_transform
    return result


def _batch_rows(bundle, member_values, input_statuses, transform, skipped, allow_degraded):
    method = bundle.get("ensemble", {}).get("aggregation", "weighted_mean_price")
    divisor = float(bundle.get("target_divisor_to_wan") or 1.0)
    residual = bundle.get("residual_calibration") or {}
    total_weight = sum(max(0.0, item["weight"]) for item in member_values) or 1.0
    results = []
    for row_index, input_status in enumerate(input_statuses):
        predictions = []
        for member in member_values:
            raw = member["raw_values"][row_index]
            predictions.append({
                "name": member["name"], "weight": member["weight"],
                "raw": raw, "price_native": _apply_transform(raw, transform),
            })
        if method == "weighted_mean_log_prediction":
            log_value = sum(max(0.0, item["weight"]) * item["raw"] for item in predictions) / total_weight
            price_native = math.exp(log_value)
        else:
            price_native = sum(max(0.0, item["weight"]) * item["price_native"] for item in predictions) / total_weight
        price_wan = price_native / divisor
        if residual.get("space") == "log":
            lower = price_wan * math.exp(float(residual.get("lower", 0)))
            upper = price_wan * math.exp(float(residual.get("upper", 0)))
        else:
            delta = float(residual.get("half_width_native", residual.get("half_width", 0))) / divisor
            lower, upper = max(0.0, price_wan - delta), price_wan + delta
        status = "exact" if not skipped else "degraded"
        results.append({
            "predicted_price_wan": round(price_wan, 6),
            "price_interval_wan": [round(lower, 6), round(upper, 6)],
            "prediction_mode": "native_pickle_%s" % status,
            "member_predictions": predictions,
            "skipped_members": list(skipped),
            "input_status": input_status,
            "confidence": "low" if skipped or input_status["warnings"] else "medium",
        })
    return results


def predict_batch(bundle, parameter_items, allow_degraded=False):
    """Predict a candidate matrix with one estimator call per ensemble member.

    Candidate generation commonly evaluates tens or hundreds of parameter sets.
    Calling every sklearn estimator once per row adds substantial Python overhead,
    especially for tree ensembles.  Preparation remains row-aware so missing-value
    and domain diagnostics are preserved, while fitted estimators receive the
    complete matrix in one call.
    """
    parameter_items = list(parameter_items or [])
    if not parameter_items:
        return []
    prepared_rows, input_statuses = [], []
    for parameters in parameter_items:
        prepared, input_status = prepare_vector(bundle, parameters)
        prepared_rows.append(prepared)
        input_statuses.append(input_status)
    # Rebuild one named frame from the per-row prepared matrices so every
    # estimator receives a DataFrame and can validate feature order.
    flat_rows = []
    for row in prepared_rows:
        flat_rows.extend(_matrix_rows(row))
    prepared_matrix = _named_matrix(bundle, flat_rows)

    member_values, skipped = [], []
    for item in bundle["ensemble"]["members"]:
        name = item["name"]
        model = bundle["models"].get(name)
        if model is None:
            skipped.append({"name": name, "reason": "model_missing"})
            continue
        try:
            raw_values = model.predict(prepared_matrix)
            raw_values = [float(value) for value in raw_values]
            if len(raw_values) != len(parameter_items):
                raise ValueError("价格子模型批量返回数量不一致")
        except Exception as exc:
            if not allow_degraded:
                raise
            skipped.append({"name": name, "reason": str(exc)})
            continue
        member_values.append({
            "name": name,
            "weight": float(item.get("weight", 1)),
            "raw_values": raw_values,
        })
    if not member_values:
        raise RuntimeError("没有可用的价格子模型")

    transform = _declared_transform(bundle)
    results = _batch_rows(bundle, member_values, input_statuses, transform, skipped, allow_degraded)
    corrected = _batch_self_check(bundle, member_values, input_statuses, transform, skipped, allow_degraded, results)
    if corrected is not None:
        results = _batch_rows(bundle, member_values, input_statuses, corrected, skipped, allow_degraded)
        for result in results:
            result["output_transform_corrected"] = corrected
    return results


def _batch_self_check(bundle, member_values, input_statuses, transform, skipped, allow_degraded, results):
    """Flip the batch transform when the first row lands far outside the reference."""
    if not results:
        return None
    reference = bundle.get("target_reference_wan")
    if reference in (None, ""):
        return None
    try:
        reference = float(reference)
        first_wan = float(results[0]["predicted_price_wan"])
    except (TypeError, ValueError):
        return None
    if not (reference > 0 and first_wan > 0):
        return None
    ratio = first_wan / reference
    if 0.01 <= ratio <= 100.0:
        return None
    alt = "identity" if transform == "log" else "log"
    alt_results = _batch_rows(bundle, member_values, input_statuses, alt, skipped, allow_degraded)
    if not alt_results:
        return None
    alt_wan = float(alt_results[0]["predicted_price_wan"])
    if alt_wan <= 0:
        return None
    if abs(alt_wan / reference - 1.0) < abs(ratio - 1.0):
        return alt
    return None


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()
