# -*- coding: utf-8 -*-
"""Shared requirement assessment for historical recommendation and generation.

One source of truth for "does this candidate meet the user's conditions, and if
not, by how much".  It returns per-condition evidence plus a numeric penalty so
the same logic powers historical soft-recommendation, seed selection and the
generator's demand anchoring.
"""
from __future__ import print_function

from .recommender import filter_match
from .value_semantics import normalize_numeric


def _number(value):
    return normalize_numeric(value)


def assess_requirements(item, request, definitions=None, tag_map=None):
    """Assess one candidate against the user's requirements.

    Returns::

        {
          "conditions": [ {kind, key, label, operator, target, actual, matched, gap}, ... ],
          "matched_count", "unmatched_count", "unknown_count", "total_count",
          "demand_penalty", "strict_satisfied", "fit_ratio",
        }

    ``unknown`` means the value cannot be judged right now (e.g. the model
    service is down); it is never treated as a failure.
    """
    definitions = definitions or {}
    tag_map = tag_map or {}
    conditions = []
    penalty = 0.0
    matched = 0
    unmatched = 0
    unknown = 0

    price = item.get("predicted_price_wan")
    if price in (None, ""):
        price = item.get("historical_price_wan")
    price_num = _number(price)
    max_price = request.get("max_price")
    if max_price not in (None, ""):
        target = float(max_price)
        actual = price_num
        if actual is None:
            status, gap = "unknown", None
            unknown += 1
        elif actual <= target:
            status, gap = "matched", 0.0
            matched += 1
        else:
            status, gap = "unmatched", round(actual - target, 6)
            unmatched += 1
            penalty += 1.5 + gap / max(abs(target), 1.0)
        conditions.append({
            "kind": "price", "key": "max_price", "label": "价格 ≤ %.3f万元" % target,
            "operator": "lte", "target": target, "actual": actual, "matched": status == "matched", "status": status, "gap": gap,
        })

    capability = _number(item.get("capability_score"))
    min_capability = request.get("min_capability")
    if min_capability not in (None, ""):
        target = float(min_capability)
        if capability is None:
            status, gap = "unknown", None
            unknown += 1
        elif capability >= target:
            status, gap = "matched", 0.0
            matched += 1
        else:
            status, gap = "unmatched", round(target - capability, 6)
            unmatched += 1
            penalty += 1.5 + gap / max(abs(target), 1.0)
        conditions.append({
            "kind": "capability", "key": "min_capability", "label": "效能 ≥ %.3f" % target,
            "operator": "gte", "target": target, "actual": capability, "matched": status == "matched", "status": status, "gap": gap,
        })

    # Technical indicator filters honour AND/OR semantics as one grouped condition.
    rules = list(request.get("indicator_filters") or [])
    if rules:
        params = item.get("params") or {}
        results = [filter_match(params, rule) for rule in rules]
        mode = str(request.get("indicator_filter_mode") or "all")
        group_matched = any(results) if mode == "any" else all(results)
        if group_matched:
            matched += 1
        else:
            unmatched += 1
            penalty += 1.0
        for rule, ok in zip(rules, results):
            key = rule.get("parameter_id")
            definition = definitions.get(key, {})
            label = definition.get("label", key)
            operator = rule.get("operator")
            value1 = rule.get("value1")
            value2 = rule.get("value2")
            expected = "%s～%s" % (value1, value2) if str(operator).startswith("range_") else str(value1)
            conditions.append({
                "kind": "parameter", "key": key, "parameter_id": key,
                "label": "%s %s %s" % (label, _operator_text(operator), expected),
                "operator": operator, "actual": params.get(key),
                "matched": bool(ok), "status": "matched" if ok else "unmatched",
                "gap": None, "group": mode,
            })
        conditions.append({
            "kind": "parameter_group", "key": "__indicator_filters__",
            "label": "技术指标条件（%s）" % ("任一满足" if mode == "any" else "全部满足"),
            "matched": group_matched, "status": "matched" if group_matched else "unmatched",
            "mode": mode, "gap": None,
        })

    selected_tags = list(request.get("selected_tags") or [])
    own_tags = set(item.get("tags") or [])
    for tag_id in selected_tags:
        label = tag_map.get(tag_id, {}).get("tag_name", tag_id)
        ok = tag_id in own_tags
        if ok:
            matched += 1
        else:
            unmatched += 1
            penalty += 2.0 * float(tag_map.get(tag_id, {}).get("weight", 1.0))
        conditions.append({
            "kind": "tag", "key": tag_id, "label": label,
            "matched": ok, "status": "matched" if ok else "unmatched", "gap": None,
        })

    total = matched + unmatched + unknown
    strict_satisfied = unmatched == 0
    fit_ratio = round(matched / total, 4) if total else 1.0
    return {
        "conditions": conditions,
        "matched_count": matched,
        "unmatched_count": unmatched,
        "unknown_count": unknown,
        "total_count": total,
        "demand_penalty": round(penalty, 6),
        "strict_satisfied": strict_satisfied,
        "fit_ratio": fit_ratio,
    }


def _operator_text(operator):
    return {
        "gte": "不低于", "gt": "高于", "lte": "不高于", "lt": "低于", "eq": "等于",
        "boolean_is": "为", "text_equals": "等于", "text_contains": "包含",
        "range_inside": "位于区间", "range_contains": "覆盖区间", "range_overlap": "与区间相交",
    }.get(operator, operator)
