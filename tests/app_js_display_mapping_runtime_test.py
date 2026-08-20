# -*- coding: utf-8 -*-
"""The browser display mapper has one implementation and executes without recursion."""
from __future__ import print_function

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")

assert len(re.findall(r"function\s+displayValue\s*\(", source)) == 1, "displayValue must have exactly one implementation"

names = ("jsonObject", "displayMapping", "displayValue")
functions = []
for name in names:
    match = re.search(r"function\s+%s\s*\([^\n]+" % name, source)
    assert match, name
    functions.append(match.group(0))
script = "\n".join(functions) + "\nconst d={value_type:'boolean',display_value_mapping_json:'{\"0\":\"无\",\"1\":\"有\"}'};if(displayValue(d,1)!=='有')process.exit(2);"
subprocess.run(["node", "-e", script], check=True)
assert 'q("rangeDiagnosticsPanel").innerHTML=' in source
assert "模型服务不可用，未执行范围诊断" in source
print("PASS app.js display mapping runtime")
