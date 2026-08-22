# -*- coding: utf-8 -*-
"""Prove that the current Python can load and execute the native price model."""
from __future__ import print_function

import argparse
import math
import platform
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _version(module_name):
    module = __import__(module_name)
    return str(getattr(module, "__version__", "unknown"))


def probe(model_path):
    model = Path(model_path).resolve()
    print("Selected Python: %s" % sys.executable)
    print("Python: %s" % platform.python_version())
    print("Architecture: %s" % platform.architecture()[0])
    for module_name in ("numpy", "sklearn", "scipy", "joblib"):
        print("%s: %s" % (module_name, _version(module_name)))
    print("Model: %s" % model)
    if not model.is_file():
        raise RuntimeError("Native price model does not exist: %s" % model)

    from services.price_service.app import PriceService
    from services.price_service import native_bundle  # noqa: F401 - explicit import smoke

    service = PriceService(
        model_path=model,
        fallback_json=None,
        allow_degraded=False,
        allow_model_fallback=False,
    )
    response = service._one(service.example_request())
    value = ((response.get("prediction") or {}).get("predicted_price_wan"))
    try:
        finite = math.isfinite(float(value))
    except (TypeError, ValueError):
        finite = False
    if not finite:
        raise RuntimeError("Example prediction returned a non-finite predicted_price_wan: %r" % value)
    print("Example predicted_price_wan: %s" % value)
    print("Runtime smoke: PASS")
    return response


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    args = parser.parse_args(argv)
    try:
        probe(args.model)
        return 0
    except Exception:
        print("Runtime smoke: FAIL")
        print("Reason:")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
