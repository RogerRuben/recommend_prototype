# -*- coding: utf-8 -*-
"""Application configuration with one documented precedence order.

Defaults < config/model_services.json < environment variables.
"""
from __future__ import print_function

import json
import os
from pathlib import Path


DEFAULT_MODEL_SERVICE_CONFIG = {
    "execution_mode": "local",
    "price_service_url": "http://127.0.0.1:18101",
    "effectiveness_service_url": "http://127.0.0.1:18102",
    "timeout_seconds": 15.0,
    "local_fallback": False,
    "batch_size": 100,
}


def _boolean(value, default=False):
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def load_model_service_config(root):
    root = Path(root)
    result = dict(DEFAULT_MODEL_SERVICE_CONFIG)
    path = root / "config" / "model_services.json"
    if path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("config/model_services.json必须是JSON对象")
        for key in result:
            if key in raw:
                result[key] = raw[key]

    env_map = {
        "execution_mode": "IPDEMO_MODEL_EXECUTION_MODE",
        "price_service_url": "IPDEMO_PRICE_SERVICE_URL",
        "effectiveness_service_url": "IPDEMO_EFFECT_SERVICE_URL",
        "timeout_seconds": "IPDEMO_MODEL_SERVICE_TIMEOUT",
        "local_fallback": "IPDEMO_MODEL_SERVICE_FALLBACK",
        "batch_size": "IPDEMO_MODEL_SERVICE_BATCH_SIZE",
    }
    for key, env_name in env_map.items():
        if env_name in os.environ:
            result[key] = os.environ[env_name]

    result["execution_mode"] = str(result.get("execution_mode") or "local").strip().lower()
    result["price_service_url"] = str(result["price_service_url"]).rstrip("/")
    result["effectiveness_service_url"] = str(result["effectiveness_service_url"]).rstrip("/")
    result["timeout_seconds"] = float(result["timeout_seconds"])
    result["local_fallback"] = _boolean(result.get("local_fallback"), False)
    result["batch_size"] = max(1, int(result["batch_size"]))
    result["config_path"] = str(path)
    result["config_loaded"] = path.is_file()
    return result
