# -*- coding: utf-8 -*-
"""Non-empty best-effort results must surface engineering-infeasible filter diagnostics."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "app" / "static" / "app.js"
STYLES = ROOT / "app" / "static" / "styles.css"


def main():
    source = APP_JS.read_text(encoding="utf-8")
    css = STYLES.read_text(encoding="utf-8")

    assert "function feasibilityReportHtml" in source
    assert "state.generationFeasibility" in source
    # The best-effort report must append the same feasibility block.
    assert "feasibilityReportHtml(state.generationFeasibility)" in source
    assert "empty-feasibility" in css

    print(json.dumps({"status": "PASS", "message": "非空 best-effort 页面也展示工程不可行提示"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
