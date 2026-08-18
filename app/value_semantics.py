# -*- coding: utf-8 -*-
"""Unified business-value semantics shared by filtering, generation and display.

One source of truth for the questions that keep recurring across the codebase:

* is ``1`` / ``1.0`` / ``"1"`` / ``"1.0"`` the same value?  (yes, numerically)
* is ``1.0`` the same boolean as ``"有"``?                 (yes, both truthy)
* how do we render a stored ``1`` back to the operator?    (``有``, or the mapped label)

The model encoding stays untouched: ``Store.runtime_parameters()`` continues to
own the business-value -> model-value mapping.  This module only normalises
comparisons and display so every consumer uses identical semantics.
"""
from __future__ import print_function

import json
import math

_TRUE_TOKENS = {"1", "1.0", "true", "yes", "y", "on", "是", "有", "具备", "支持", "启用"}
_FALSE_TOKENS = {"0", "0.0", "false", "no", "n", "off", "否", "无", "不具备", "不支持", "停用", ""}


def normalize_numeric(value):
    """Return ``float(value)`` or ``None``. ``"IP65"``/``65`` both yield ``65.0``."""
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    text = str(value).strip()
    if text.upper().startswith("IP"):
        text = text[2:].strip()
    if text == "":
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def normalize_boolean(value):
    """Return ``True``/``False`` for any legal boolean form, else ``None``.

    Recognises ``True/1/1.0/"1"/"1.0"/"true"/"yes"/"是"/"有"`` as truthy and
    ``False/0/0.0/"0"/"0.0"/"false"/"no"/"否"/"无"`` as falsy.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number == 1.0:
            return True
        if number == 0.0:
            return False
        return None
    text = str(value).strip().lower()
    if text in _TRUE_TOKENS:
        return True
    if text in _FALSE_TOKENS:
        return False
    return None


def definition_value_type(definition):
    if not definition:
        return None
    return str(definition.get("value_type") or definition.get("dtype") or "").strip().lower()


def definition_mapping(definition):
    """Return the business-value -> model-value mapping of a definition, if any."""
    if not definition:
        return {}
    raw = definition.get("model_value_mapping_json")
    if raw in (None, ""):
        return {}
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items()}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return {str(k): v for k, v in parsed.items()} if isinstance(parsed, dict) else {}


def mapping_target(value, definition=None):
    """Return the model value a business label/encoding maps to, else ``None``.

    Unlike :func:`canonical_filter_value` this never falls back to boolean truth,
    so a declared third state (``无该属性 -> -1``) survives to the caller.
    """
    mapping = definition_mapping(definition)
    if not mapping:
        return None
    text = str(value).strip()
    for business, model in mapping.items():
        if str(business).strip() == text:
            return model
    number = normalize_numeric(value)
    if number is not None:
        for business, model in mapping.items():
            business_num = normalize_numeric(business)
            if business_num is not None and math.isclose(business_num, number, rel_tol=1e-9, abs_tol=1e-9):
                return model
    return None


def values_equal(left, right, definition=None):
    """Compare two business values with boolean/numeric tolerance.

    Boolean-typed fields compare as booleans; everything else compares
    numerically when both sides are numeric and falls back to trimmed strings.
    """
    value_type = definition_value_type(definition)
    if value_type in ("boolean", "bool"):
        left_bool = normalize_boolean(left)
        right_bool = normalize_boolean(right)
        if left_bool is not None and right_bool is not None:
            return left_bool == right_bool
        return str(left).strip() == str(right).strip()
    left_num = normalize_numeric(left)
    right_num = normalize_numeric(right)
    if left_num is not None and right_num is not None:
        decimal_places = int((definition or {}).get("decimal_places", 3) or 3)
        tolerance = 10.0 ** (-max(2, decimal_places))
        return abs(left_num - right_num) <= tolerance
    return str(left).strip() == str(right).strip()


def canonical_filter_value(value, definition=None):
    """Convert a business filter value to the canonical comparison/model form."""
    value_type = definition_value_type(definition)
    if value_type in ("boolean", "bool"):
        return normalize_boolean(value)
    if value_type == "ip_grade":
        number = normalize_numeric(value)
        return number
    mapping = definition_mapping(definition)
    if mapping:
        text = str(value).strip()
        for business, model in mapping.items():
            if business.strip() == text:
                return model
        # numeric business labels may be written "1.0"
        number = normalize_numeric(value)
        for business, model in mapping.items():
            business_num = normalize_numeric(business)
            if business_num is not None and number is not None and math.isclose(business_num, number, rel_tol=1e-9, abs_tol=1e-9):
                return model
    return value


def business_display_value(value, definition=None):
    """Render a stored model/DB value back in business language.

    ``-1`` is only shown as ``无该属性`` when the DataMaster mapping explicitly
    declares it; it is never a global convention.
    """
    if value is None:
        return ""
    value_type = definition_value_type(definition)
    if value_type in ("boolean", "bool"):
        boolean = normalize_boolean(value)
        if boolean is True:
            return "有"
        if boolean is False:
            return "无"
    mapping = definition_mapping(definition)
    if mapping:
        reverse = {}
        for business, model in mapping.items():
            reverse.setdefault(str(model), business)
        if str(value) in reverse:
            return reverse[str(value)]
    if value_type == "ip_grade":
        number = normalize_numeric(value)
        if number is not None:
            return "IP%d" % int(number) if float(number).is_integer() else "IP%s" % value
        return "IP%s" % value
    return str(value)
