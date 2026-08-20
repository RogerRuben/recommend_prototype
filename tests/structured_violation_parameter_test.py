# -*- coding: utf-8 -*-
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.model_service_client import ModelServiceGateway

effect = {"evaluation": {"effectiveness_score": 80, "feasibility_probability": .5}, "parameters": {"x": 1},
          "hard_violations": [{"parameter_id": "x", "actual": 1, "lower": 2, "upper": 5, "message": "too low"}]}
r = ModelServiceGateway._merge_core({"parameters": {"x": 1}}, effect, 10, [9, 11], [], [], {})
assert r["hard_violation_details"][0]["parameter_id"] == "x"
assert r["hard_violation_details"][0]["source"] == "effectiveness_service"
assert isinstance(r["hard_violations"][0], dict)
print("PASS structured hard violation is preserved")
