# -*- coding: utf-8 -*-
"""Business-input adapter for the exceptional Lock V17 frozen runtime."""
from __future__ import print_function

import copy
import json
import math
from pathlib import Path


class LockV17AdapterError(ValueError):
    """Raised when the special Lock V17 input contract is inconsistent."""


def _is_missing(value):
    return value is None or value == ""


def _same_value(left, right):
    try:
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)
    except (TypeError, ValueError):
        return str(left) == str(right)


def _dtype(attribute):
    raw = str(attribute.get("dtype") or attribute.get("data_type") or "number").lower()
    return {
        "continuous": "number",
        "float": "number",
        "categorical": "enum",
        "category": "enum",
        "bool": "boolean",
    }.get(raw, raw)


def _field_from_attribute(attribute):
    key = str(attribute.get("field_name") or attribute.get("key") or "").strip()
    return {
        "field_name": key,
        "field_label": attribute.get("field_label") or attribute.get("label") or key,
        "dtype": _dtype(attribute),
        "unit": attribute.get("unit") or "",
        "required": bool(attribute.get("required", True)),
        "generation_min": attribute.get("generation_min"),
        "generation_max": attribute.get("generation_max"),
        "feasible_min": attribute.get("feasible_min"),
        "feasible_max": attribute.get("feasible_max"),
        "precision": attribute.get("precision", 3),
        "preference_direction": attribute.get("preference_direction", "neutral"),
        "participates_generation": bool(attribute.get("participates_generation", True)),
        "allowed_values": copy.deepcopy(attribute.get("allowed_values")),
        "parser": attribute.get("parser"),
        "default_visible": bool(attribute.get("default_visible", True)),
        "source": "product_parameter",
    }


class LockV17InputAdapter(object):
    """Compile business parameters into one immutable V17 model request."""

    def __init__(self, config, model_schema):
        self.config = copy.deepcopy(config or {})
        self.model_schema = copy.deepcopy(model_schema or {})
        self._validate()

    @classmethod
    def from_file(cls, path, model_schema):
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError("Lock V17适配配置不存在: %s" % path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError("Lock V17适配配置不是有效JSON: %s" % exc)
        instance = cls(raw, model_schema)
        instance.config_path = path
        return instance

    def _validate(self):
        if not bool(self.config.get("enabled", True)):
            raise RuntimeError("Lock V17适配配置未启用")
        backend = self.config.get("backend") or {}
        package_format = backend.get("package_format")
        if package_format not in (None, "", "lock-product-reuse-runtime-package-17.0"):
            raise RuntimeError("Lock V17适配配置声明了不兼容的运行包格式")
        derived = self.config.get("derived_feature") or {}
        if derived.get("operation") != "abs_diff_product":
            raise RuntimeError("Lock V17仅支持abs_diff_product派生操作")
        if derived.get("input_precedence", "always_recompute") != "always_recompute":
            raise RuntimeError("Lock V17派生输入优先级必须为always_recompute")
        self.target_field = str(derived.get("target_field") or "").strip()
        self.x1_fields = [str(item) for item in ((derived.get("x1") or {}).get("fields") or [])]
        self.x2_fields = [str(item) for item in ((derived.get("x2") or {}).get("fields") or [])]
        if not self.target_field:
            raise RuntimeError("Lock V17适配配置缺少derived_feature.target_field")
        if len(self.x1_fields) != 2 or len(self.x2_fields) != 2:
            raise RuntimeError("Lock V17派生属性x1/x2必须各配置两个业务字段")
        if len(set(self.x1_fields + self.x2_fields)) != 4:
            raise RuntimeError("Lock V17派生属性的四个业务字段必须唯一")
        absence = derived.get("absence") or {}
        if absence.get("partial_group_policy", "reject") != "reject":
            raise RuntimeError("Lock V17 partial_group_policy必须为reject")
        if absence.get("if_any_group_absent", "zero") != "zero":
            raise RuntimeError("Lock V17缺失组当前只支持派生值归零")
        self.sentinel_values = list(absence.get("sentinel_values") or [-1])
        self.all_missing_group_is_absent = bool(absence.get("all_missing_group_is_absent", True))
        self.zero_value = float(absence.get("zero_value", 0.0))
        self.public_source_fields = copy.deepcopy(self.config.get("public_source_fields") or {})
        missing_metadata = [key for key in self.source_fields if key not in self.public_source_fields]
        if missing_metadata:
            raise RuntimeError(
                "Lock V17适配配置缺少业务源字段定义: %s" % "、".join(missing_metadata)
            )
        self.model_attributes = list(self.model_schema.get("attributes") or [])
        self.model_field_names = [
            str(item.get("key") or item.get("field_name") or "").strip()
            for item in self.model_attributes
        ]
        if self.target_field not in self.model_field_names:
            raise RuntimeError(
                "Lock V17派生目标字段%s不在冻结模型Schema中" % self.target_field
            )

    @property
    def source_fields(self):
        return self.x1_fields + self.x2_fields

    def _is_sentinel(self, value):
        return any(_same_value(value, sentinel) for sentinel in self.sentinel_values)

    def group_state(self, business_params, fields):
        values = [business_params.get(key) for key in fields]
        missing = [_is_missing(value) for value in values]
        absent = [False if is_missing else self._is_sentinel(value) for value, is_missing in zip(values, missing)]
        if all(missing):
            if self.all_missing_group_is_absent:
                return "absent"
            return "invalid_partial"
        if all(absent):
            return "absent"
        if not any(missing) and not any(absent):
            return "present"
        return "invalid_partial"

    def prepare(self, business_params):
        if not isinstance(business_params, dict):
            raise LockV17AdapterError("Lock V17待评价方案必须是参数对象")
        x1_status = self.group_state(business_params, self.x1_fields)
        x2_status = self.group_state(business_params, self.x2_fields)
        if "invalid_partial" in (x1_status, x2_status):
            invalid = "x1" if x1_status == "invalid_partial" else "x2"
            fields = self.x1_fields if invalid == "x1" else self.x2_fields
            raise LockV17AdapterError(
                "Lock V17派生属性组%s状态不完整，字段%s必须同时为正常值、同时为-1或同时缺失"
                % (invalid, "、".join(fields))
            )

        if x1_status == "present" and x2_status == "present":
            try:
                a, c = [float(business_params[key]) for key in self.x1_fields]
                b, d = [float(business_params[key]) for key in self.x2_fields]
            except (TypeError, ValueError, KeyError):
                raise LockV17AdapterError("Lock V17派生属性源字段必须是有效数值")
            if not all(math.isfinite(value) for value in (a, b, c, d)):
                raise LockV17AdapterError("Lock V17派生属性源字段必须是有限数值")
            derived_value = abs(a - b) * abs(c - d)
            status = "derived_complete"
        else:
            derived_value = self.zero_value
            status = "forced_zero_due_to_group_absence"

        model_params = {}
        for key in self.model_field_names:
            if key == self.target_field:
                continue
            if key in business_params and not _is_missing(business_params.get(key)):
                model_params[key] = copy.deepcopy(business_params[key])
        model_params[self.target_field] = derived_value
        diagnostics = {
            "derived_features": {
                self.target_field: {
                    "value": derived_value,
                    "status": status,
                    "operation": "abs_diff_product",
                    "x1_status": x1_status,
                    "x2_status": x2_status,
                    "sources": list(self.source_fields),
                    "external_value_ignored": self.target_field in business_params,
                }
            }
        }
        return model_params, diagnostics

    def public_fields(self):
        fields = []
        seen = set()
        for key in self.source_fields:
            raw = copy.deepcopy(self.public_source_fields[key])
            raw["field_name"] = key
            raw.setdefault("field_label", key)
            raw.setdefault("dtype", "number")
            # Each source group is conditionally required: an entire x1/x2
            # group may be absent, while a partial group is rejected by
            # ``prepare``.  Advertising these fields as globally required
            # would make schema-driven clients reject valid absent groups.
            raw["required"] = False
            raw.setdefault("participates_generation", True)
            raw.setdefault("default_visible", True)
            raw["source"] = "product_parameter"
            fields.append(raw)
            seen.add(key)
        for attribute in self.model_attributes:
            field = _field_from_attribute(attribute)
            key = field["field_name"]
            if not key or key == self.target_field or key in seen:
                continue
            fields.append(field)
            seen.add(key)
        return fields

    def derived_feature_schema(self):
        return {
            "field_name": self.target_field,
            "source": "derived",
            "editable": False,
            "participates_generation": False,
            "operation": "abs_diff_product",
            "dependencies": list(self.source_fields),
            "absence_result": self.zero_value,
        }


__all__ = ["LockV17AdapterError", "LockV17InputAdapter"]
