# -*- coding: utf-8 -*-
"""Offline historical recommendation: soft keep, unknown semantics, descending sort."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.recommender import rank_historical_products  # noqa: E402


def _hist(name, price, params=None, tags=None):
    return {
        "agreement_id": name, "agreement_name": name, "agreement_source": "historical",
        "is_generated": False, "historical_price_wan": price,
        "params": params or {}, "tags": tags or [],
    }


def _ids(ranked):
    return [item["agreement_id"] for item in ranked]


def main():
    definitions = {"protection_grade": {"parameter_id": "protection_grade", "label": "防护等级", "value_type": "ip_grade"}}
    tag_map = {}

    # Soft keep: a history row over max_price stays visible with an unmet price.
    items = [_hist("CHEAP", 9), _hist("OVER", 13)]
    ranked = rank_historical_products(items, {"max_price": 10, "sort_by": "price", "sort_order": "asc"},
                                      {}, definitions=definitions, tag_map=tag_map)
    assert len(ranked) == 2, "offline fallback must keep over-budget history"
    assert _ids(ranked) == ["CHEAP", "OVER"], _ids(ranked)
    assert ranked[1]["requirement_assessment"]["strict_satisfied"] is False
    assert any(c["kind"] == "price" and c["status"] == "unmatched"
               for c in ranked[1]["requirement_assessment"]["conditions"])

    # Model-only threshold offline -> unknown -> not strict.
    ranked2 = rank_historical_products(items, {"min_capability": 100, "sort_by": "price", "sort_order": "asc"},
                                       {}, definitions=definitions, tag_map=tag_map)
    assert all(r["requirement_assessment"]["strict_satisfied"] is False for r in ranked2)
    assert all(r["requirement_assessment"]["assessment_status"] == "unknown" for r in ranked2)

    # Descending price must not promote a missing price to the front.
    items3 = [_hist("A", 10), _hist("B", 12), _hist("NOPRICE", None)]
    ranked3 = rank_historical_products(items3, {"sort_by": "price", "sort_order": "desc"},
                                       {}, definitions=definitions, tag_map=tag_map)
    assert _ids(ranked3) == ["B", "A", "NOPRICE"], _ids(ranked3)

    print(json.dumps({"status": "PASS", "message": "离线软推荐保留历史方案、unknown不计为满足、缺失价格排最后"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
