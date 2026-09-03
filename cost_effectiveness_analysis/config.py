# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import os
from pathlib import Path


DEFAULTS = {
    "host": "127.0.0.1",
    "port": 17000,
    "database": {"path": "data/protocol_demo.db"},
    "services": {
        "price": {"url": "http://127.0.0.1:18101"},
        "effectiveness": {"url": "http://127.0.0.1:18102"},
    },
    "timeout_seconds": 30.0,
}


def _merge(base, extra):
    result = dict(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(root):
    root = Path(root).resolve()
    path = root / "config" / "cost_effectiveness_analysis.json"
    raw = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if not isinstance(raw, dict):
        raise ValueError("config/cost_effectiveness_analysis.json必须是JSON对象")
    result = _merge(DEFAULTS, raw)
    db_path = os.environ.get("COST_EFFECTIVENESS_DATABASE") or result["database"].get("path")
    db_path = Path(db_path)
    if not db_path.is_absolute():
        db_path = root / db_path
    result["database"]["path"] = str(db_path.resolve())
    result["host"] = os.environ.get("COST_EFFECTIVENESS_HOST", result["host"])
    result["port"] = int(os.environ.get("COST_EFFECTIVENESS_PORT", result["port"]))
    result["services"]["price"]["url"] = os.environ.get(
        "COST_EFFECTIVENESS_PRICE_URL", result["services"]["price"]["url"]
    ).rstrip("/")
    result["services"]["effectiveness"]["url"] = os.environ.get(
        "COST_EFFECTIVENESS_EFFECTIVENESS_URL", result["services"]["effectiveness"]["url"]
    ).rstrip("/")
    result["timeout_seconds"] = float(os.environ.get(
        "COST_EFFECTIVENESS_TIMEOUT_SECONDS", result["timeout_seconds"]
    ))
    result["config_path"] = str(path)
    return result
