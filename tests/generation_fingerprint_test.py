# -*- coding: utf-8 -*-
"""Generation fingerprint must include frozen_parameters (and exclude sort)."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.generation_tasks import GenerationTaskManager  # noqa: E402


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
    mgr = GenerationTaskManager(_App())
    base = {"session_id": "s", "max_price": 12, "min_capability": 90,
            "selected_tags": [], "indicator_filters": [], "count": 6, "target_protocol": None}

    # Frozen set participates in the fingerprint: a different lock set must never
    # reuse a previously cached batch.
    fp_env = mgr.fingerprint(dict(base, frozen_parameters=["env"]))
    fp_humidity = mgr.fingerprint(dict(base, frozen_parameters=["humidity"]))
    fp_none = mgr.fingerprint(dict(base, frozen_parameters=[]))
    assert fp_env != fp_humidity, "frozen_parameters must change the generation fingerprint"
    assert fp_env != fp_none and fp_humidity != fp_none, "frozen vs unfrozen must differ"

    # Order-insensitive within the same frozen set.
    assert mgr.fingerprint(dict(base, frozen_parameters=["b", "a"])) == mgr.fingerprint(dict(base, frozen_parameters=["a", "b"]))

    # sort_by / sort_order still must not change the fingerprint.
    assert mgr.fingerprint(dict(base, sort_by="comprehensive", sort_order="desc")) == \
           mgr.fingerprint(dict(base, sort_by="price", sort_order="asc"))

    # Scenario semantics select different seeds and must never reuse a batch.
    fp_cost = mgr.fingerprint(dict(base, scenario="cost", optimization_intensity="target"))
    fp_performance = mgr.fingerprint(dict(base, scenario="performance", optimization_intensity="target"))
    fp_extreme = mgr.fingerprint(dict(base, scenario="cost", optimization_intensity="extreme"))
    assert fp_cost != fp_performance
    assert fp_cost != fp_extreme

    print(json.dumps({"status": "PASS", "message": "生成指纹包含冻结参数且不含排序"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
