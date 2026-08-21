# -*- coding: utf-8 -*-
"""Global indicator search must never rewrite an established explicit row."""
from __future__ import print_function

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "app/static/app.js"


def extract_function(source, name):
    start = source.index("function " + name + "(")
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError("unbalanced function %s" % name)


def main():
    source = APP_JS.read_text(encoding="utf-8")
    add_filter = source[source.index("function addFilter("):source.index("function collectFilters(")]
    assert 'q("parameterSearch")' not in add_filter
    assert 'q("parameterSearch").oninput' not in source

    helper = extract_function(source, "filterParametersForRow")
    refresh_helper = extract_function(source, "shouldRefreshFilterControls")
    harness = helper + "\n" + refresh_helper + r"""
const parameters = [
  {parameter_id:'weight', label:'重量', parameter_group:'结构'},
  {parameter_id:'material', label:'材料', parameter_group:'结构'},
  {parameter_id:'sealed', label:'密封', parameter_group:'环境'}
];
const preserved = filterParametersForRow(parameters, '结构', '', {weight:true}, true, 'weight');
const crossGroup = filterParametersForRow(parameters, '环境', '', {sealed:true}, true, 'weight');
console.log(JSON.stringify({
  preserved:preserved.map(x=>x.parameter_id),
  crossGroup:crossGroup.map(x=>x.parameter_id),
  tagRefreshRebuildsValue:shouldRefreshFilterControls('weight','weight',true,true),
  changedParameterRebuildsValue:shouldRefreshFilterControls('weight','material',true,true)
}));
"""
    run = subprocess.run(["node", "-e", harness], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    # A tag refresh keeps the existing hard condition even when it is covered.
    assert result["preserved"] == ["weight", "material"]
    # Switching to a group whose only indicator is hidden never leaks weight across groups.
    assert result["crossGroup"] == []
    assert result["tagRefreshRebuildsValue"] is False
    assert result["changedParameterRebuildsValue"] is True
    print("PASS V21 global search and tag refresh preserve explicit filters")


if __name__ == "__main__":
    main()
