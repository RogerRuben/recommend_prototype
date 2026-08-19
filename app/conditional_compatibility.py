# -*- coding: utf-8 -*-
"""Save-time compatibility checks for conditional relationship metadata."""
from __future__ import print_function

from .value_semantics import normalize_numeric


def validate_conditional_relationship(metadata, definitions=None, model_specs=None):
    """Return ``{"compatible", "errors", "warnings"}`` for a V2 relationship.

    ``model_specs`` is optional; when absent only the DataMaster definition is
    checked.  The caller decides whether service-offline should downgrade errors
    to warnings.
    """
    definitions = definitions or {}
    model_specs = model_specs or []
    errors = []
    warnings = []
    target = metadata.get("target")
    definition = definitions.get(target) or {}
    target_min = definition.get("min_value")
    target_max = definition.get("max_value")

    for branch_name in ("then", "otherwise"):
        branch = metadata.get(branch_name) or {}
        mode = branch.get("mode") or "not_applicable"
        if mode in ("not_applicable", "fixed"):
            model_value = branch.get("model_value")
            if model_value is not None and target_min is not None and target_max is not None:
                number = normalize_numeric(model_value)
                if number is not None and (number < float(target_min) or number > float(target_max)):
                    errors.append(
                        "从属指标「%s」的%s模型值 %s 不在允许范围 %s~%s 内。"
                        % (target, branch_name, model_value, target_min, target_max)
                    )
        elif mode == "range":
            lo = normalize_numeric(branch.get("min"))
            hi = normalize_numeric(branch.get("max"))
            if lo is not None and hi is not None and lo > hi:
                errors.append("从属指标「%s」的%s范围下限高于上限。" % (target, branch_name))
            if lo is not None and target_min is not None and lo < float(target_min):
                warnings.append("从属指标「%s」的%s范围下限低于指标允许下限。" % (target, branch_name))
            if hi is not None and target_max is not None and hi > float(target_max):
                warnings.append("从属指标「%s」的%s范围上限高于指标允许上限。" % (target, branch_name))

    return {"compatible": not errors, "errors": errors, "warnings": warnings}
