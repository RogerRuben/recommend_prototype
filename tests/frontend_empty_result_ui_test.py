# -*- coding: utf-8 -*-
"""Frontend must consume empty_result/rejection diagnostics instead of showing a blank page."""
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

    assert "function showEmptyGeneration" in source
    assert "function generationEmptyReportHtml" in source
    assert "empty_result" in source
    assert "stopping_reason" in source
    assert "rejection_statistics" in source
    assert "rejection_details" in source
    assert "retryGenerationBtn" in source
    assert "empty-preflight" in source

    # Empty completed tasks must not auto-switch to the generated empty view.
    assert 'if(task.result&&task.result.empty_result){showEmptyGeneration(task);return}' in source
    assert 'if(gt.result&&gt.result.empty_result){renderResults(data);showEmptyGeneration(gt);return}' in source

    # The report has visible styles.
    assert "generation-empty-report" in css
    assert "empty-preflight" in css

    print(json.dumps({"status": "PASS", "message": "前端已消费空结果与失败诊断，空结果不再自动切空页"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
