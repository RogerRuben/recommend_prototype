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


def _rule_gap(params, rule, definition, matched):
    """Normalised distance to satisfying one indicator rule (0.0 when satisfied).

    Numeric operators use the attribute's own span so ``99 vs 100`` and ``10 vs
    100`` are no longer the same binary penalty; boolean/text/range rules that
    fail collapse to 1.0 (there is no meaningful continuous distance).
    """
    if matched:
        return 0.0
    operator = rule.get("operator")
    value1 = rule.get("value1")
    value2 = rule.get("value2")
    actual = params.get(rule.get("parameter_id"))
    definition = definition or {}
    span = max(float(definition.get("max_value") or 1) - float(definition.get("min_value") or 0), 1e-9)
    a = _number(actual)
    if operator in ("gte", "gt", "lte", "lt", "eq"):
        b = _number(value1)
        if a is None or b is None:
            return 1.0
        if operator == "gte":
            return (b - a) / span
        if operator == "gt":
            return (b - a + 1e-7) / span
        if operator == "lte":
            return (a - b) / span
        if operator == "lt":
            return (a - b + 1e-7) / span
        return abs(a - b) / span
    if str(operator).startswith("range_") and a is not None:
        b1, b2 = _number(value1), _number(value2)
        if b1 is not None and b2 is not None:
            lo, hi = min(b1, b2), max(b1, b2)
            return (lo - a if a < lo else a - hi) / span
    return 1.0


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
        results = [filter_match(params, rule, definitions.get(rule.get("parameter_id"))) for rule in rules]
        gaps = [_rule_gap(params, rule, definitions.get(rule.get("parameter_id")), ok) for rule, ok in zip(rules, results)]
        mode = str(request.get("indicator_filter_mode") or "all")
        group_matched = any(results) if mode == "any" else all(results)
        if group_matched:
            matched += 1
        else:
            unmatched += 1
            penalty += min(gaps) if mode == "any" else sum(gaps)
        for rule, ok, gap in zip(rules, results, gaps):
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
                "gap": round(gap, 6), "group": mode, "group_matched": group_matched,
            })
        conditions.append({
            "kind": "parameter_group", "key": "__indicator_filters__",
            "label": "技术指标条件（%s）" % ("任一满足" if mode == "any" else "全部满足"),
            "matched": group_matched, "status": "matched" if group_matched else "unmatched",
            "mode": mode, "gap": round(0.0 if group_matched else sum(gaps), 6),
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
    strict_satisfied = unmatched == 0 and unknown == 0
    if unmatched > 0:
        assessment_status = "partial"
    elif unknown > 0:
        assessment_status = "unknown"
    else:
        assessment_status = "satisfied"
    fit_ratio = round(matched / total, 4) if total else 1.0
    return {
        "conditions": conditions,
        "matched_count": matched,
        "unmatched_count": unmatched,
        "unknown_count": unknown,
        "total_count": total,
        "demand_penalty": round(penalty, 6),
        "strict_satisfied": strict_satisfied,
        "assessment_status": assessment_status,
        "fit_ratio": fit_ratio,
    }


def _operator_text(operator):
    return {
        "gte": "不低于", "gt": "高于", "lte": "不高于", "lt": "低于", "eq": "等于",
        "boolean_is": "为", "text_equals": "等于", "text_contains": "包含",
        "range_inside": "位于区间", "range_contains": "覆盖区间", "range_overlap": "与区间相交",
    }.get(operator, operator)
