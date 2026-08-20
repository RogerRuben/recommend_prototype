# -*- coding: utf-8 -*-
"""Requirement targets remain canonical in back end and map only in UI."""
import re
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.requirement_assessment import assess_requirements  # noqa: E402

definition = {"parameter_id": "xx", "label": "是否具备XX", "value_type": "boolean",
              "display_value_mapping_json": '{"0":"无","1":"有"}'}
item = {"params": {"xx": 1}, "tags": []}
request = {"indicator_filters": [{"parameter_id": "xx", "operator": "eq", "value1": 1}], "indicator_filter_mode": "all"}
condition = assess_requirements(item, request, {"xx": definition}, {})["conditions"][0]
assert condition["target"] == 1 and condition["actual"] == 1
assert condition["label"] == "是否具备XX"

source = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
names = ("jsonObject", "displayMapping", "displayValue", "requirementTargetText")
functions = []
for name in names:
    match = re.search(r"function\s+%s\s*\([^\n]+" % name, source)
    assert match, name
    functions.append(match.group(0))
script = "\n".join(functions) + "\nconst d={value_type:'boolean',display_value_mapping_json:'{\"0\":\"无\",\"1\":\"有\"}'};const c={label:'是否具备XX',operator:'eq',target:1,actual:1};if(requirementTargetText(c,d)!=='是否具备XX 等于 有')process.exit(3);"
subprocess.run(["node", "-e", script], check=True)
print("PASS display mapping requirement target")
