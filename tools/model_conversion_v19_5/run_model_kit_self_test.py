# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from model_contract_v4 import evaluate_joint, load_bundle, validate_bundle
from reference_runtime.model_runtime import IntegratedModelRuntime
from validate_and_install_models import (
    build_sample, validate_price_only_fallbacks, validate_shared_bindings,
)


def main():
    e_path = HERE / "examples" / "effectiveness_bundle_from_uploaded_workbook_baseline.json"
    p_path = HERE / "examples" / "price_bundle_synthetic_validation.json"
    effectiveness = load_bundle(e_path)
    price = load_bundle(p_path)
    errors = validate_bundle(effectiveness, "effectiveness") + validate_bundle(price, "price")
    shared_errors, shared = validate_shared_bindings(effectiveness, price)
    errors += shared_errors + validate_price_only_fallbacks(effectiveness, price)
    if effectiveness.get("product_code") != price.get("product_code"):
        errors.append("两个示例模型product_code不一致")
    if errors:
        raise SystemExit(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))

    sample = build_sample(effectiveness, price)
    direct = evaluate_joint(effectiveness, price, sample)
    with tempfile.TemporaryDirectory(prefix="v195_model_kit_") as temp_name:
        model_dir = Path(temp_name)
        shutil.copy2(str(e_path), str(model_dir / "effectiveness_bundle.json"))
        shutil.copy2(str(p_path), str(model_dir / "price_bundle.json"))
        runtime = IntegratedModelRuntime(model_dir)
        integrated = runtime.evaluate(sample)
    assert abs(direct["predicted_price_wan"] - integrated["predicted_price_wan"]) < 1e-9
    assert abs(direct["capability_score"] - integrated["capability_score"]) < 1e-9
    assert abs(direct["feasibility_probability"] - integrated["feasibility_probability"]) < 1e-9
    roles = runtime.feature_roles()
    assert roles["shared_features"]
    assert roles["price_only_features"]
    assert all(key in integrated["parameters"] for key in roles["price_only_features"])
    print(json.dumps({
        "status": "PASS", "shared_fields": shared,
        "feature_roles": roles, "joint_result": integrated,
        "runtime": "integrated app/model_runtime.py reference",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
