# -*- coding: utf-8 -*-
"""Conditional-constraint projection and active search-space computation (Phase 5B).

``project_constraints`` makes the *controller -> subordinate* applicability
relationship deterministic *before* a candidate is sent to the model, instead of
letting a post-hoc rule emit a penalty.  A subordinate that is inactive collapses
to its configured ``inactive_value``; one that just became active is restored to a
legal active value (seed history -> default -> active-range midpoint).

The same module also answers "which parameters may the search touch" via
``active_parameter_set``, so single/pair/correlated moves never pick an inactive
subordinate.
"""
from __future__ import print_function

from .conditional_constraint import TEMPLATE_KIND, expected_range, parse_template_metadata
from .value_semantics import normalize_numeric


def _num(value, default=None):
    result = normalize_numeric(value)
    return result if result is not None else default


def _group_conditional_rules(rules):
    groups = {}
    for rule in rules or []:
        kind = rule.get("rule_kind")
        group = rule.get("constraint_group")
        if kind in ("conditional_lower", "conditional_upper") and group:
            groups.setdefault(group, []).append(rule)
    return groups


def _restore_active_value(target, definitions, seed_values, active_min, active_max):
    if seed_values:
        seed = _num(seed_values.get(target))
        if seed is not None and active_min <= seed <= active_max:
            return seed
    definition = (definitions or {}).get(target, {})
    default = _num(definition.get("default_value"))
    if default is not None and active_min <= default <= active_max:
        return default
    return (active_min + active_max) / 2.0


def project_constraints(params, definitions, rules, locked=None, seed_values=None):
    """Apply conditional templates to ``params``.

    Returns ``{"parameters", "repairs", "inactive_parameters", "conflicts"}``.
    A frozen/anchor subordinate that a controller forces inactive is reported as a
    ``conflict`` and is *not* silently overwritten.
    """
    locked = set(locked or [])
    params = dict(params or {})
    definitions = definitions or {}
    repairs = []
    inactive_parameters = []
    conflicts = []

    for group, group_rules in _group_conditional_rules(rules).items():
        meta = parse_template_metadata(group_rules[0])
        if not meta or meta.get("template") != TEMPLATE_KIND:
            continue
        controller = meta.get("controller")
        target = meta.get("target")
        active_value = meta.get("active_value", 1)
        inactive_value = float(meta.get("inactive_value", -1))
        active_min = float(meta.get("active_min", 0))
        active_max = float(meta.get("active_max", 1))
        if controller not in params:
            continue
        active = str(params[controller]).strip() == str(active_value).strip()
        current = params.get(target)
        current_num = _num(current)

        if active:
            if current_num is None or abs(current_num - inactive_value) < 1e-9:
                restored = _restore_active_value(target, definitions, seed_values, active_min, active_max)
                params[target] = restored
                repairs.append({
                    "type": "conditional_activation", "parameter": target,
                    "before": current, "after": restored,
                    "reason": "控制指标%s激活，从属指标恢复为有效值" % controller,
                })
            elif current_num < active_min:
                params[target] = active_min
                repairs.append({"type": "conditional_clamp", "parameter": target, "before": current, "after": active_min,
                                "reason": "从属指标低于激活范围下限"})
            elif current_num > active_max:
                params[target] = active_max
                repairs.append({"type": "conditional_clamp", "parameter": target, "before": current, "after": active_max,
                                "reason": "从属指标高于激活范围上限"})
        else:
            inactive_parameters.append(target)
            if target in locked:
                if current_num is not None and abs(current_num - inactive_value) >= 1e-9:
                    conflicts.append({
                        "type": "frozen_conditional_conflict", "parameter": target,
                        "controller": controller, "controller_value": params[controller],
                        "frozen_value": current, "required_inactive_value": inactive_value,
                        "reason": "用户冻结 %s=%s 与 %s=%s -> %s 不适用冲突" % (target, current, controller, params[controller], target),
                    })
                continue
            if current_num is None or abs(current_num - inactive_value) >= 1e-9:
                params[target] = inactive_value
                repairs.append({
                    "type": "conditional_deactivation", "parameter": target,
                    "before": current, "after": inactive_value,
                    "reason": "控制指标%s不满足，从属指标设为不适用值" % controller,
                })

    return {"parameters": params, "repairs": repairs, "inactive_parameters": inactive_parameters, "conflicts": conflicts}


def active_parameter_set(params, definitions, rules, locked=None):
    """Return ``{"active_parameters", "inactive_parameters"}`` for search moves.

    Only adjustable (non-locked) parameters that are not forced inactive are
    eligible; locked/inactive parameters never enter a proposal.
    """
    locked = set(locked or [])
    projection = project_constraints(params, definitions, rules, locked=locked)
    inactive = set(projection["inactive_parameters"])
    adjustable = {
        key for key, definition in (definitions or {}).items()
        if definition.get("auto_adjustable", 1) and key not in locked and key not in inactive
    }
    return {
        "active_parameters": sorted(adjustable),
        "inactive_parameters": sorted(inactive),
        "conflicts": projection["conflicts"],
    }
