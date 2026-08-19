# -*- coding: utf-8 -*-
"""Explicit technical-filter feasibility and anchor-integrity diagnostics."""
from __future__ import print_function

from .value_semantics import normalize_numeric


def _num(value):
    result = normalize_numeric(value)
    return result if result is not None else None


def assess_explicit_filter_feasibility(indicator_filters, definitions, mode="all"):
    """Check explicit indicator filters against engineering min/max domains.

    Returns ``{"strictly_feasible", "conflicts"}``.  A conflict means the user's
    requested technical condition has no intersection with the engineering
    domain; the closest feasible boundary is reported.
    """
    definitions = definitions or {}
    filters = list(indicator_filters or [])
    conflicts = []
    single_results = []

    for rule in filters:
        key = rule.get("parameter_id")
        op = rule.get("operator")
        definition = definitions.get(key) or {}
        raw_min = definition.get("min_value")
        raw_max = definition.get("max_value")
        if raw_min is None or raw_max is None:
            continue
        engineering_min = float(raw_min)
        engineering_max = float(raw_max)
        v1 = _num(rule.get("value1"))
        v2 = _num(rule.get("value2"))
        conflict = None

        if op in ("lte", "lt") and v1 is not None:
            if v1 < engineering_min:
                conflict = {
                    "parameter_id": key, "label": definition.get("label", key),
                    "operator": op, "requested_value": v1,
                    "engineering_min": engineering_min, "engineering_max": engineering_max,
                    "closest_feasible_value": engineering_min,
                    "reason": "requested_upper_below_engineering_min",
                }
        elif op in ("gte", "gt") and v1 is not None:
            if v1 > engineering_max:
                conflict = {
                    "parameter_id": key, "label": definition.get("label", key),
                    "operator": op, "requested_value": v1,
                    "engineering_min": engineering_min, "engineering_max": engineering_max,
                    "closest_feasible_value": engineering_max,
                    "reason": "requested_lower_above_engineering_max",
                }
        elif op == "eq" and v1 is not None:
            if not (engineering_min <= v1 <= engineering_max):
                closest = engineering_min if v1 < engineering_min else engineering_max
                conflict = {
                    "parameter_id": key, "label": definition.get("label", key),
                    "operator": op, "requested_value": v1,
                    "engineering_min": engineering_min, "engineering_max": engineering_max,
                    "closest_feasible_value": closest,
                    "reason": "requested_value_outside_engineering_domain",
                }
        elif op == "range_inside" and v1 is not None and v2 is not None:
            lo, hi = min(v1, v2), max(v1, v2)
            inter_lo = max(lo, engineering_min)
            inter_hi = min(hi, engineering_max)
            if inter_lo > inter_hi:
                if hi < engineering_min:
                    closest = engineering_min
                elif lo > engineering_max:
                    closest = engineering_max
                else:
                    closest = engineering_min if abs(engineering_min - lo) <= abs(engineering_max - hi) else engineering_max
                conflict = {
                    "parameter_id": key, "label": definition.get("label", key),
                    "operator": op, "requested_value": [lo, hi],
                    "engineering_min": engineering_min, "engineering_max": engineering_max,
                    "closest_feasible_value": closest,
                    "reason": "requested_range_outside_engineering_domain",
                }

        if conflict is not None:
            conflicts.append(conflict)
            single_results.append(False)
        else:
            single_results.append(True)

    if mode == "any":
        strictly_feasible = any(single_results) if single_results else True
    else:
        strictly_feasible = all(single_results) if single_results else True
    return {"strictly_feasible": strictly_feasible, "conflicts": conflicts}


def validate_anchor_integrity(params, indicator_filters, definitions, mode="all"):
    """Return anchor-invariant violations for explicitly feasible filters.

    Infeasible conditions are excluded because they are expected to project to
    the nearest engineering boundary.  Feasible conditions that are violated by
    the final candidate are treated as generator bugs.
    """
    feasibility = assess_explicit_filter_feasibility(indicator_filters, definitions, mode=mode)
    infeasible_keys = {c["parameter_id"] for c in feasibility["conflicts"]}
    checks = []
    for rule in indicator_filters or []:
        key = rule.get("parameter_id")
        if key in infeasible_keys:
            continue
        op = rule.get("operator")
        value = _num(params.get(key))
        if value is None:
            continue
        v1 = _num(rule.get("value1"))
        v2 = _num(rule.get("value2"))
        ok = True
        if op == "lte":
            ok = v1 is not None and value <= v1
        elif op == "lt":
            ok = v1 is not None and value < v1
        elif op == "gte":
            ok = v1 is not None and value >= v1
        elif op == "gt":
            ok = v1 is not None and value > v1
        elif op == "eq":
            ok = v1 is not None and abs(value - v1) < 1e-9
        elif op == "range_inside":
            ok = v1 is not None and v2 is not None and min(v1, v2) <= value <= max(v1, v2)
        else:
            continue
        checks.append((key, ok))

    if mode == "any":
        violations = [] if any(ok for _key, ok in checks) else [
            {"stage": "anchor_integrity", "parameter_id": key, "requested": rule, "actual": params.get(key)}
            for key, ok in checks if not ok
        ]
    else:
        violations = [
            {"stage": "anchor_integrity", "parameter_id": key, "requested": rule, "actual": params.get(key)}
            for key, ok in checks if not ok
        ]
    return violations
