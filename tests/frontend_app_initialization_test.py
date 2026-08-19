# -*- coding: utf-8 -*-
"""Frontend initialization must not throw ReferenceError in frozen-parameter grouping."""
from __future__ import print_function

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "app" / "static" / "app.js"


def _node(*args, **kwargs):
    return subprocess.run(["node"] + list(args), capture_output=True, text=True, **kwargs)


def main():
    # 1. Syntax gate.
    check = _node("--check", str(APP_JS))
    assert check.returncode == 0, check.stderr

    # 2. Minimal DOM/JS harness: run the real renderFrozenParams source from app.js
    # with a stubbed q/esc/refreshFrozenSummary. Before the fix this throws
    # "ReferenceError: groups is not defined" in strict mode.
    app_js = APP_JS.read_text(encoding="utf-8")
    harness = r"""
const vm = require('vm');
const fs = require('fs');
const src = fs.readFileSync(process.argv[1], 'utf8');

function extractFn(source, name) {
  const start = source.indexOf('function ' + name + '(){');
  if (start < 0) throw new Error(name + ' not found');
  const open = source.indexOf('{', start);
  let depth = 0;
  for (let i = open; i < source.length; i++) {
    if (source[i] === '{') depth++;
    else if (source[i] === '}') { depth--; if (depth === 0) return source.slice(start, i + 1); }
  }
  throw new Error('unbalanced ' + name);
}

const fn = extractFn(src, 'renderFrozenParams');
const context = {
  console: console,
  state: {
    bootstrap: {
      parameters: [
        {parameter_id: 'A', label: 'A', model_role: 'shared', parameter_group: 'G'},
        {parameter_id: 'B', label: 'B', model_role: 'shared', parameter_group: 'G'},
      ],
      parameter_groups: [
        {group_name: 'G', enabled: 1, display_order: 1, default_collapsed: 0},
      ],
    },
  },
  q: function(id) { return {innerHTML: '', querySelectorAll: function() { return []; }, style: {}}; },
  esc: function(v) { return String(v); },
  show: function() {},
  hide: function() {},
  refreshFrozenSummary: function() {},
  collectFrozen: function() { return []; },
};
vm.createContext(context);
vm.runInContext(fn + '\nrenderFrozenParams();', context);
console.log('HARNESS_OK');
"""
    run = _node("-e", harness, str(APP_JS))
    assert run.returncode == 0, run.stderr
    assert "HARNESS_OK" in run.stdout, run.stdout + run.stderr

    print(json.dumps({"status": "PASS", "message": "前端初始化 Frozen 分组不再抛 ReferenceError"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
