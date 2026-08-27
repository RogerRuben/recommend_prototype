# -*- coding: utf-8 -*-
"""Compile explicit and tag requirements into bounded generation branches."""


def _operator_text(operator):
    return {
        "gte": "不低于", "gt": "高于", "lte": "不高于", "lt": "低于",
        "eq": "等于", "boolean_is": "为", "special_is": "状态为",
        "text_equals": "等于", "text_contains": "包含", "range_inside": "位于区间",
    }.get(operator, str(operator or ""))


def _filter_label(rule, definitions):
    key = str(rule.get("parameter_id") or "")
    definition = (definitions or {}).get(key) or {}
    label = definition.get("label") or key or "技术条件"
    value = rule.get("value1")
    if str(rule.get("operator") or "").startswith("range_"):
        value = "%s～%s" % (value, rule.get("value2"))
    return "%s%s%s" % (label, _operator_text(rule.get("operator")), value)


def compile_explicit_demand_branches(filters, mode="all", definitions=None):
    filters = [dict(rule) for rule in (filters or []) if rule.get("parameter_id")]
    if str(mode or "all") != "any" or len(filters) <= 1:
        label = "联合满足当前技术要求" if filters else "按当前综合需求探索"
        return [{"explicit_branch_id": "BRANCH-ALL", "explicit_filters": filters,
                 "explicit_filter_mode": "all", "title": label, "summary": label}]
    return [
        {"explicit_branch_id": "BRANCH-%02d" % (index + 1), "explicit_filters": [rule],
         "explicit_filter_mode": "all", "title": "优先满足%s" % _filter_label(rule, definitions),
         "summary": "该方向围绕“%s”进行参数探索。" % _filter_label(rule, definitions)}
        for index, rule in enumerate(filters)
    ]


def combine_generation_branches(explicit_branches, tag_branches, max_branches=24):
    explicit = list(explicit_branches or [])
    tags = list(tag_branches or []) or [{"rules": [], "tag_groups": {}, "unresolved_tags": []}]
    result = []
    # Tag-major round robin guarantees every explicit OR branch receives a slot
    # before secondary tag alternatives consume the bounded branch budget.
    for tag_index, tag in enumerate(tags):
        for demand in explicit:
            if len(result) >= max(1, int(max_branches)):
                return result
            branch_id = demand["explicit_branch_id"]
            if len(tags) > 1:
                branch_id += "-TAG-%02d" % (tag_index + 1)
            result.append({
                "branch_id": branch_id,
                "demand_branch_id": demand["explicit_branch_id"],
                "title": demand["title"], "summary": demand["summary"],
                "explicit_filters": list(demand["explicit_filters"]),
                "assessment_filters": list(demand.get("assessment_filters") or []),
                "explicit_filter_mode": demand["explicit_filter_mode"],
                "tag_rules": list(tag.get("rules") or []),
                "tag_groups": dict(tag.get("tag_groups") or {}),
                "unresolved_tags": list(tag.get("unresolved_tags") or []),
            })
    return result
