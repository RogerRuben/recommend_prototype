# -*- coding: utf-8 -*-
"""Static guards for frontend generation-criteria dirty tracking and snapshot."""
from __future__ import print_function

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "app" / "static" / "app.js"


def main():
    source = APP_JS.read_text(encoding="utf-8")

    assert "function markGenerationCriteriaDirty" in source, "markGenerationCriteriaDirty missing"
    assert "markGenerationCriteriaDirty()" in source

    # requestSnapshot must include budget/rounds so auto-switch can detect stale tasks.
    snapshot_idx = source.find("function requestSnapshot(){")
    snapshot_body = source[snapshot_idx:source.find("\n", snapshot_idx)]
    assert "generationBudget" in snapshot_body and "generationRounds" in snapshot_body, "snapshot missing budget/rounds"

    # The duplicate collectFrozen from the old UI must be gone.
    assert source.count("function collectFrozen()") == 1, "duplicate collectFrozen still present"

    # Frozen group select and item changes mark generation dirty.
    assert "refreshFrozenSummary();markGenerationCriteriaDirty()" in source

    print(json.dumps({"status": "PASS", "message": "前端生成条件脏标记与 requestSnapshot 已补齐"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
