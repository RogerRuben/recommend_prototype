# -*- coding: utf-8 -*-
"""sort_order (asc/desc) for price/capability, and sort never triggers generation."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.recommender import rank_agreements  # noqa: E402
from app.generation_tasks import GenerationTaskManager  # noqa: E402


def _item(name, capability, price):
    return {
        "agreement_id": name, "agreement_name": name, "agreement_source": "historical",
        "is_generated": False, "model_evaluation_available": True,
        "capability_score": capability, "conservative_capability_score": capability,
        "predicted_price_wan": price, "cost_effectiveness": capability / price,
        "feasibility_probability": 0.8, "physical_gate": {"passed": True},
        "hard_risk_reasons": [], "params": {"attr_001": 1}, "tags": [],
    }


def _ids(ranked):
    return [item["agreement_id"] for item in ranked]


def main():
    items = [_item("A", 90, 12.0), _item("B", 100, 15.0), _item("C", 80, 9.0)]

    # price asc / desc.
    asc = rank_agreements(items, {"sort_by": "price", "sort_order": "asc"}, {})
    desc = rank_agreements(items, {"sort_by": "price", "sort_order": "desc"}, {})
    assert _ids(asc) == ["C", "A", "B"], _ids(asc)
    assert _ids(desc) == ["B", "A", "C"], _ids(desc)

    # capability asc / desc.
    cap_asc = rank_agreements(items, {"sort_by": "capability", "sort_order": "asc"}, {})
    cap_desc = rank_agreements(items, {"sort_by": "capability", "sort_order": "desc"}, {})
    assert _ids(cap_asc) == ["C", "A", "B"], _ids(cap_asc)
    assert _ids(cap_desc) == ["B", "A", "C"], _ids(cap_desc)

    # Changing sort must not change the generation fingerprint.
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

    mgr = GenerationTaskManager(_App())
    base = {"session_id": "s", "max_price": 12, "min_capability": 90,
            "selected_tags": [], "indicator_filters": [], "count": 6, "target_protocol": None}
    fp1 = mgr.fingerprint(dict(base, sort_by="comprehensive", sort_order="desc"))
    fp2 = mgr.fingerprint(dict(base, sort_by="price", sort_order="asc"))
    assert fp1 == fp2, "sort_by/sort_order must not change the generation fingerprint"

    print(json.dumps({"status": "PASS", "message": "排序升降序正确且不影响生成指纹"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
