# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from model_contract_v4 import evaluate_joint, load_bundle, validate_bundle
from reference_runtime.model_runtime import IntegratedModelRuntime
from validate_and_install_models import build_sample, validate_price_only_fallbacks, validate_shared_bindings


def run(effectiveness_path, price_path):
    effectiveness = load_bundle(effectiveness_path)
    price = load_bundle(price_path)
    errors = validate_bundle(effectiveness, "effectiveness") + validate_bundle(price, "price")
    shared_errors, shared = validate_shared_bindings(effectiveness, price)
    errors += shared_errors + validate_price_only_fallbacks(effectiveness, price)
    assert not errors, errors
    assert effectiveness["product_code"] == price["product_code"]
    assert shared, "价格与效能模型应允许存在共享字段"
    sample = build_sample(effectiveness, price)
    direct = evaluate_joint(effectiveness, price, sample)
    with tempfile.TemporaryDirectory(prefix="v195_export_test_") as temp_name:
        model_dir = Path(temp_name)
        shutil.copy2(str(effectiveness_path), str(model_dir / "effectiveness_bundle.json"))
        shutil.copy2(str(price_path), str(model_dir / "price_bundle.json"))
        runtime = IntegratedModelRuntime(model_dir)
        integrated = runtime.evaluate(sample)
        roles = runtime.feature_roles()
    assert direct["predicted_price_wan"] > 0
    assert 0 <= direct["feasibility_probability"] <= 1
    # Requirement-relative effectiveness may legitimately exceed 100.
    assert direct["capability_score"] >= 0
    assert abs(integrated["predicted_price_wan"] - direct["predicted_price_wan"]) < 1e-9
    assert abs(integrated["capability_score"] - direct["capability_score"]) < 1e-9
    assert roles["shared_features"] and roles["price_only_features"]
    assert all(key in integrated["parameters"] for key in roles["price_only_features"])
    print(json.dumps({
        "status": "PASS", "shared_fields": shared,
        "feature_roles": roles, "joint_result": integrated,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("用法: python test_exported_models.py effectiveness_bundle.json price_bundle.json")
    run(sys.argv[1], sys.argv[2])
