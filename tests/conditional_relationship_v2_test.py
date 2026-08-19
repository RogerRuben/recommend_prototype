# -*- coding: utf-8 -*-
"""V2 conditional relationships drive projection directly from metadata."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.conditional_constraint import compile_conditional_relationship_v2  # noqa: E402
from app.constraint_projection import project_constraints  # noqa: E402


def main():
    compiled = compile_conditional_relationship_v2(
        controller="attr_001",
        when={"operator": "equals", "business_value": "无", "model_value": 0},
        target="attr_004",
        then={"mode": "not_applicable", "business_value": "无该属性", "model_value": 0},
        otherwise={"mode": "range", "min": 0, "max": 30},
    )
    assert compiled["template_metadata"]["template"] == "conditional_applicability_v2"
    rules = compiled["rules"]
    assert len(rules) == 2

    # Inactive controller -> target uses the configured model value and is inactive.
    result = project_constraints(
        {"attr_001": 0, "attr_004": 5.0}, {}, rules,
    )
    assert result["parameters"]["attr_004"] == 0, result["parameters"]
    assert "attr_004" in result["inactive_parameters"], result

    # Active controller -> range branch clamps/restores a legal value.
    result2 = project_constraints(
        {"attr_001": 1, "attr_004": 5.0}, {}, rules,
    )
    assert result2["parameters"]["attr_004"] == 5.0, result2["parameters"]
    assert "attr_004" not in result2["inactive_parameters"], result2

    # Missing target under active range is created at the midpoint.
    result3 = project_constraints(
        {"attr_001": 1}, {}, rules,
    )
    assert result3["parameters"]["attr_004"] == 15.0, result3["parameters"]

    print(json.dumps({"status": "PASS", "message": "条件属性关系V2投影直接读取Metadata"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
