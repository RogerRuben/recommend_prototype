# -*- coding: utf-8 -*-
"""Verify the isolated Python 3.8 model runtime or price-training environment."""
from __future__ import print_function

import argparse
import importlib
import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


EXPECTED = {
    "numpy": "1.24.4",
    "scipy": "1.10.1",
    "openpyxl": "3.1.3",
    "sklearn": "1.3.2",
    "xgboost": "1.7.6",
    "joblib": "1.4.2",
    "threadpoolctl": "3.5.0",
    "pandas": "1.5.3",
    "matplotlib": "3.7.5",
    "seaborn": "0.13.2",
    "notebook": "6.5.6",
    "ipykernel": "6.29.5",
}


def module_version(name):
    module = importlib.import_module(name)
    return str(getattr(module, "__version__", "unknown"))


def verify_modules(profile):
    required = [
        "numpy", "scipy", "openpyxl", "sklearn", "xgboost",
        "joblib", "threadpoolctl",
    ]
    if profile == "training":
        required.extend([
            "pandas", "matplotlib", "seaborn", "notebook", "ipykernel",
        ])
    versions = {}
    errors = []
    for name in required:
        try:
            actual = module_version(name)
            versions[name] = actual
            expected = EXPECTED.get(name)
            if expected and actual != expected:
                errors.append("%s版本应为%s，实际为%s" % (name, expected, actual))
        except Exception as exc:
            errors.append("%s导入失败: %s" % (name, exc))
    return versions, errors


def smoke_current_models():
    from services.effectiveness_service.app import backend_from_package
    from services.price_service.app import PriceService

    price_path = ROOT / "services" / "price_service" / "model" / "price_native_bundle.pkl"
    effect_path = (
        ROOT / "services" / "effectiveness_service" / "model" / "current"
        / "effectiveness_runtime_manifest.json"
    )
    errors = []
    result = {}
    try:
        price = PriceService(price_path, fallback_json=None)
        result["price"] = price.health()
        if price.backend != "native_pickle":
            errors.append("当前价格服务不是native_pickle")
        price._one(price.example_request())
    except Exception as exc:
        errors.append("当前价格模型冒烟失败: %s" % exc)
    try:
        effect = backend_from_package(effect_path)
        result["effectiveness"] = {
            "backend": effect.name,
            "product_code": effect.product_code,
            "model_version": effect.model_version,
        }
        effect.evaluate(effect.app.project.schemes[0].params)
    except Exception as exc:
        errors.append("当前效能模型冒烟失败: %s" % exc)
    if (
        result.get("price", {}).get("product_code")
        and result.get("effectiveness", {}).get("product_code")
        and result["price"]["product_code"] != result["effectiveness"]["product_code"]
    ):
        errors.append("当前价格与效能模型product_code不一致")
    return result, errors


def main():
    parser = argparse.ArgumentParser(description="验证模型Python隔离环境")
    parser.add_argument("--profile", choices=("runtime", "training"), required=True)
    parser.add_argument("--smoke-current-models", action="store_true")
    args = parser.parse_args()
    report = {
        "profile": args.profile,
        "python": sys.version,
        "executable": sys.executable,
        "architecture_bits": struct.calcsize("P") * 8,
        "versions": {},
        "models": None,
        "errors": [],
    }
    if sys.version_info[:2] != (3, 8):
        report["errors"].append("必须使用Python 3.8")
    if struct.calcsize("P") * 8 != 64:
        report["errors"].append("必须使用64位Python")
    versions, errors = verify_modules(args.profile)
    report["versions"] = versions
    report["errors"].extend(errors)
    if args.smoke_current_models:
        models, model_errors = smoke_current_models()
        report["models"] = models
        report["errors"].extend(model_errors)
    report["status"] = "PASS" if not report["errors"] else "FAIL"
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
