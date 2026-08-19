# -*- coding: utf-8 -*-
"""Explicit technical-filter feasibility and anchor-integrity diagnostics."""
from __future__ import print_function

from .value_semantics import normalize_numeric


def _num(value):
    result = normalize_numeric(value)
    return result if result is not None else None


def _merge_requested_interval(rules, definitions):
    """Merge AND constraints for one parameter into a requested interval.

    Returns ``(lower, lower_inclusive, upper, upper_inclusive, conflict)``.
    ``conflict`` is a dict when the user's own conditions are mutually
    inconsistent.
    """
    lower = float("-inf")
    lower_inclusive = True
    upper = float("inf")
    upper_inclusive = True
    conflict = None
    for rule in rules or []:
        op = rule.get("operator")
        v1 = _num(rule.get("value1"))
        v2 = _num(rule.get("value2"))
        key = rule.get("parameter_id")
        definition = definitions.get(key) or {}
        label = definition.get("label", key)
        if op in ("gte", "gt") and v1 is not None:
            new_lower = v1
            new_inclusive = op == "gte"
            if new_lower > lower or (new_lower == lower and new_inclusive and not lower_inclusive):
                lower = new_lower
                lower_inclusive = new_inclusive
        elif op in ("lte", "lt") and v1 is not None:
            new_upper = v1
            new_inclusive = op == "lte"
            if new_upper < upper or (new_upper == upper and new_inclusive and not upper_inclusive):
                upper = new_upper
                upper_inclusive = new_inclusive
        elif op == "eq" and v1 is not None:
            lower = upper = v1
            lower_inclusive = upper_inclusive = True
        elif op == "range_inside" and v1 is not None and v2 is not None:
            lo, hi = min(v1, v2), max(v1, v2)
            lower = max(lower, lo)
            upper = min(upper, hi)
            lower_inclusive = True
            upper_inclusive = True
    if lower > upper or (lower == upper and not (lower_inclusive and upper_inclusive)):
        conflict = {
            "parameter_id": rule.get("parameter_id") if rules else None,
            "label": (definitions.get(rule.get("parameter_id")) or {}).get("label", rule.get("parameter_id")) if rules else None,
            "operator": "and",
            "requested_value": [lower, upper],
            "engineering_min": None, "engineering_max": None,
            "closest_feasible_value": None,
            "reason": "explicit_filters_mutually_inconsistent",
        }
    return lower, lower_inclusive, upper, upper_inclusive, conflict


def assess_explicit_filter_feasibility(indicator_filters, definitions, mode="all"):
    """Check explicit indicator filters against engineering min/max domains.

    AND conditions on the same parameter are merged before comparing with the
    engineering domain, so ``weight>=6 AND weight<=4`` is detected as mutually
    inconsistent instead of passing the per-rule check.
    """
    definitions = definitions or {}
    filters = list(indicator_filters or [])
    conflicts = []

    if mode != "all":
        # Keep the simple per-rule path for OR mode; complex multi-condition OR
        # is intentionally out of scope for this micro patch.
        single_results = []
        for rule in filters:
            key = rule.get("parameter_id")
            definition = definitions.get(key) or {}
            raw_min = definition.get("min_value")
            raw_max = definition.get("max_value")
            if raw_min is None or raw_max is None:
                continue
            engineering_min = float(raw_min)
            engineering_max = float(raw_max)
            op = rule.get("operator")
            v1 = _num(rule.get("value1"))
            conflict = None
            if op in ("lte", "lt") and v1 is not None and (v1 < engineering_min or (op == "lt" and v1 <= engineering_min)):
                conflict = {"parameter_id": key, "label": definition.get("label", key), "operator": op,
                            "requested_value": v1, "engineering_min": engineering_min, "engineering_max": engineering_max,
                            "closest_feasible_value": engineering_min, "reason": "requested_upper_below_engineering_min"}
            elif op in ("gte", "gt") and v1 is not None and (v1 > engineering_max or (op == "gt" and v1 >= engineering_max)):
                conflict = {"parameter_id": key, "label": definition.get("label", key), "operator": op,
                            "requested_value": v1, "engineering_min": engineering_min, "engineering_max": engineering_max,
                            "closest_feasible_value": engineering_max, "reason": "requested_lower_above_engineering_max"}
            if conflict:
                conflicts.append(conflict)
                single_results.append(False)
            else:
                single_results.append(True)
        strictly_feasible = any(single_results) if single_results else True
        return {"strictly_feasible": strictly_feasible, "conflicts": conflicts}

    groups = {}
    for rule in filters:
        key = rule.get("parameter_id")
        if not key or key not in definitions:
            continue
        groups.setdefault(key, []).append(rule)

    for key, rules in groups.items():
        definition = definitions.get(key) or {}
        raw_min = definition.get("min_value")
        raw_max = definition.get("max_value")
        if raw_min is None or raw_max is None:
            continue
        engineering_min = float(raw_min)
        engineering_max = float(raw_max)
        lower, lower_inclusive, upper, upper_inclusive, mutual_conflict = _merge_requested_interval(rules, definitions)
        if mutual_conflict is not None:
            mutual_conflict["engineering_min"] = engineering_min
            mutual_conflict["engineering_max"] = engineering_max
            mutual_conflict["closest_feasible_value"] = engineering_min if abs(engineering_min - lower) <= abs(engineering_max - upper) else engineering_max
            conflicts.append(mutual_conflict)
            continue

        # Strict boundary semantics: a strict bound exactly on the engineering
        # boundary has no intersection.
        below = upper < engineering_min or (upper == engineering_min and not upper_inclusive)
        above = lower > engineering_max or (lower == engineering_max and not lower_inclusive)
        if below:
            conflicts.append({
                "parameter_id": key, "label": definition.get("label", key),
                "operator": "and", "requested_value": [lower, upper],
                "engineering_min": engineering_min, "engineering_max": engineering_max,
                "closest_feasible_value": engineering_min,
                "reason": "requested_upper_below_engineering_min",
            })
        elif above:
            conflicts.append({
                "parameter_id": key, "label": definition.get("label", key),
                "operator": "and", "requested_value": [lower, upper],
                "engineering_min": engineering_min, "engineering_max": engineering_max,
                "closest_feasible_value": engineering_max,
                "reason": "requested_lower_above_engineering_max",
            })

    return {"strictly_feasible": not conflicts, "conflicts": conflicts}


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
