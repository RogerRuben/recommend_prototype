# -*- coding: utf-8 -*-
"""Verify the field sklearn 0.24.1 runtime and isolated price runtime."""
from __future__ import print_function

import argparse
import importlib
import json
import struct
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPECTED_FIELD = {
    "numpy": "1.19.5", "scipy": "1.7.3", "pandas": "1.2.5",
    "sklearn": "0.24.1", "joblib": "1.0.1", "threadpoolctl": "2.1.0",
    "openpyxl": "3.0.10",
}


def version(name):
    return str(getattr(importlib.import_module(name), "__version__", "unknown"))


def sample_for(schema):
    sample = {}
    for field in schema.get("fields") or []:
        allowed = field.get("allowed_values") or []
        lo, hi = field.get("generation_min"), field.get("generation_max")
        if allowed:
            value = allowed[0]
        elif field.get("default_value") is not None:
            value = field.get("default_value")
        elif lo is not None and hi is not None:
            value = (float(lo) + float(hi)) / 2.0
        elif lo is not None:
            value = lo
        else:
            value = 0
        sample[field.get("field_name")] = value
    return sample


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-python", required=True)
    args = parser.parse_args(argv)
    report = {"field_python": sys.executable, "field_versions": {}, "price": None, "errors": []}
    if sys.version_info[:2] != (3, 8) or struct.calcsize("P") * 8 != 64:
        report["errors"].append("现场运行时必须是64位Python 3.8")
    for name, expected in EXPECTED_FIELD.items():
        try:
            actual = version(name)
            report["field_versions"][name] = actual
            if actual != expected:
                report["errors"].append("%s应为%s，实际为%s" % (name, expected, actual))
        except Exception as exc:
            report["errors"].append("%s导入失败：%s" % (name, exc))
    try:
        from app.server import Application  # noqa: F401
        from cost_effectiveness_analysis.app import CostEffectivenessApplication  # noqa: F401
        from services.effectiveness_service.app import backend_from_package
        effect = backend_from_package(
            ROOT / "services" / "effectiveness_service" / "model" / "current"
            / "effectiveness_runtime_manifest.json"
        )
        evaluated = effect.evaluate(sample_for(effect.schema()))
        if evaluated.get("effectiveness_score") is None:
            report["errors"].append("效能模型没有返回效能分")
    except Exception as exc:
        report["errors"].append("主程序/效能/效费比冒烟失败：%s" % exc)
    price_python = Path(args.price_python).resolve()
    completed = subprocess.run(
        [str(price_python), str(ROOT / "tools" / "verify_model_environment.py"),
         "--profile", "runtime", "--smoke-current-models"],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    try:
        report["price"] = json.loads(completed.stdout)
    except Exception:
        report["price"] = {"raw": completed.stdout}
    if completed.returncode != 0:
        report["errors"].append("独立价格运行时或当前价格模型冒烟失败")
    report["status"] = "PASS" if not report["errors"] else "FAIL"
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
