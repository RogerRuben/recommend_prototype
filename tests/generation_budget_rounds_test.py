# -*- coding: utf-8 -*-
"""User-configurable budget/rounds: dynamic schedule and fingerprint participation."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.generation_tasks import GenerationTaskManager  # noqa: E402
from app.local_generator import build_step_schedule  # noqa: E402


class _App(object):
    class _Runtime(object):
        schema = {"product_code": "PROD"}

        def manifest(self):
            return {"model_versions": {"effectiveness": "e1", "price": "p1"}}

    class _Store(object):
        def master_data_version(self):
            return "0"

    runtime = _Runtime()
    store = _Store()


def main():
    fast6 = build_step_schedule("fast", 6)
    assert len(fast6) == 6 and abs(fast6[0] - 0.52) < 1e-9 and abs(fast6[-1] - 0.09) < 1e-9, fast6
    fast10 = build_step_schedule("fast", 10)
    assert len(fast10) == 10 and fast10[0] > fast10[-1], fast10
    deep = build_step_schedule("deep", 7)
    assert len(deep) == 7 and abs(deep[1] - 0.90) < 1e-9, deep

    # Budget/rounds participate in the generation fingerprint.
    mgr = GenerationTaskManager(_App())
    base = {"session_id": "s", "max_price": 12, "min_capability": 90, "selected_tags": [],
            "indicator_filters": [], "count": 6, "target_protocol": None}
    fp_auto = mgr.fingerprint(dict(base))
    fp_budget = mgr.fingerprint(dict(base, generation_budget=1200, generation_rounds=12))
    assert fp_auto != fp_budget, "budget/rounds must change the fingerprint"

    print(json.dumps({"status": "PASS", "message": "动态轮数schedule与预算/轮数指纹生效"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
