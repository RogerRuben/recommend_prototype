# -*- coding: utf-8 -*-
"""Protocol refresh must not replace a generated scheme with model inputs."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.server import Application  # noqa: E402


class _Store(object):
    def parameter_map(self):
        return {}

    def tag_map(self):
        return {}

    def derive_tags(self, params, evaluation=None, inherited_tags=None):
        return list(inherited_tags or [])


class _Generator(object):
    def _demand_assessment(self, item, request, definitions, tag_map):
        return [], 0.0, {}

    def _engineering_conflicts(self, evaluation):
        return [], 0.0


def main():
    app = Application.__new__(Application)
    app.store = _Store()
    app.generator = _Generator()
    app._evaluate_batch_with_rules = lambda items: [{
        "parameters": {"frozen_lock_force": 999, "model_only": 1},
        "predicted_price_wan": 10.0,
        "capability_score": 80.0,
        "physical_gate": {"passed": True},
    }]
    original = {"frozen_lock_force": 42, "business_only": "keep"}
    refreshed = app._refresh_candidates_for_protocol([{
        "agreement_id": "GEN-1",
        "params": dict(original),
        "tags": [],
    }], {"target_protocol": 75})
    assert refreshed[0]["params"] == original, refreshed[0]["params"]
    assert refreshed[0]["evaluation"]["parameters"]["frozen_lock_force"] == 999
    print(json.dumps({"status": "PASS", "message": "协议复评不覆盖生成方案及冻结属性"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
