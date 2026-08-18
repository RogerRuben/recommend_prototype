# -*- coding: utf-8 -*-
"""Generator seed distance reuses the shared RequirementAssessment (OR-group safe)."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator  # noqa: E402
from app.requirement_assessment import assess_requirements  # noqa: E402


DEFINITIONS = {
    "protection_grade": {"parameter_id": "protection_grade", "label": "防护等级", "value_type": "ip_grade"},
    "low_temp": {"parameter_id": "low_temp", "label": "低温启动", "value_type": "boolean"},
}


class _MockStore(object):
    def parameter_map(self):
        return DEFINITIONS

    def tag_map(self):
        return {}


class _MockRuntime(object):
    schema = {"product_code": "X"}


def main():
    gen = HistorySeededGenerator(_MockStore(), _MockRuntime(), None)
    request = {
        "indicator_filters": [
            {"parameter_id": "protection_grade", "operator": "gte", "value1": "IP65"},
            {"parameter_id": "low_temp", "operator": "boolean_is", "value1": "有"},
        ],
        "indicator_filter_mode": "any",
        "selected_tags": [],
    }

    # OR-satisfied seed: IP64 fails, but low_temp=有 passes -> the group is satisfied.
    item_or = {"params": {"protection_grade": "IP64", "low_temp": 1}, "tags": [],
               "predicted_price_wan": None, "historical_price_wan": None, "capability_score": None}
    assessment = assess_requirements(item_or, request, DEFINITIONS, {})
    assert assessment["demand_penalty"] == 0.0, assessment["demand_penalty"]
    assert gen._request_distance(item_or, request, DEFINITIONS, {}) == 0.0

    # OR-failed seed: both rules fail -> the group is unmatched and the distance matches.
    item_bad = {"params": {"protection_grade": "IP64", "low_temp": 0}, "tags": [],
                "predicted_price_wan": None, "historical_price_wan": None, "capability_score": None}
    bad_assessment = assess_requirements(item_bad, request, DEFINITIONS, {})
    assert bad_assessment["demand_penalty"] > 0.0
    assert gen._request_distance(item_bad, request, DEFINITIONS, {}) == bad_assessment["demand_penalty"]

    print(json.dumps({"status": "PASS", "message": "生成器Seed距离复用共享需求评估，OR组语义一致"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
