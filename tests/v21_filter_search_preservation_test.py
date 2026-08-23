# -*- coding: utf-8 -*-
"""Grouped indicator search must never choose or rewrite a parameter implicitly."""
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
    assert "addVisibleFilter" not in source
    assert "function refreshParameterOptions(" in add_filter
    assert "function selectParameter(" in add_filter
    assert "function refreshCoverageNote(" in add_filter
    assert "search.oninput=refreshParameterOptions" in add_filter
    assert "group.onchange=function(){saved=null" in add_filter
    assert "button.onclick=function(){selectParameter" in add_filter
    assert "psel.onchange" not in add_filter

    helper = extract_function(source, "filterParametersForRow")
    harness = 'var ALL_PARAMETER_GROUPS="__all__";\n' + helper + r"""
const parameters = [
  {parameter_id:'weight', label:'重量', parameter_group:'结构'},
  {parameter_id:'material', label:'材料', parameter_group:'结构'},
  {parameter_id:'sealed', label:'密封', parameter_group:'环境'},
  {parameter_id:'orphan', label:'未分组指标', parameter_group:''}
];
const preserved = filterParametersForRow(parameters, '结构', '', {weight:true}, true, 'weight');
const crossGroup = filterParametersForRow(parameters, '环境', '', {sealed:true}, true, 'weight');
const allParameters = filterParametersForRow(parameters, '__all__', '', {}, false, '');
const allSearch = filterParametersForRow(parameters, '__all__', '未分组', {}, false, '');
console.log(JSON.stringify({
  preserved:preserved.map(x=>x.parameter_id),
  crossGroup:crossGroup.map(x=>x.parameter_id),
  allParameters:allParameters.map(x=>x.parameter_id),
  allSearch:allSearch.map(x=>x.parameter_id)
}));
"""
    run = subprocess.run(["node", "-e", harness], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    # A tag refresh keeps the existing hard condition even when it is covered.
    assert result["preserved"] == ["weight", "material"]
    # Switching to a group whose only indicator is hidden never leaks weight across groups.
    assert result["crossGroup"] == []
    # New rows start from the complete parameter set, including orphan indicators.
    assert result["allParameters"] == ["weight", "material", "sealed", "orphan"]
    assert result["allSearch"] == ["orphan"]
    assert "全部指标" in add_filter and "搜索全部指标" in add_filter
    assert "group.value!==ALL_PARAMETER_GROUPS" in add_filter
    print("PASS grouped search defaults to all indicators and preserves explicit filters")


if __name__ == "__main__":
    main()
