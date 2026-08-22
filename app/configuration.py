# -*- coding: utf-8 -*-
"""Application configuration with one documented precedence order.

Defaults < config/model_services.json < environment variables.
"""
from __future__ import print_function

import json
import os
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_MODEL_SERVICE_CONFIG = {
    "execution_mode": "local",
    "price_service_url": "http://127.0.0.1:18101",
    "effectiveness_service_url": "http://127.0.0.1:18102",
    "timeout_seconds": 15.0,
    "local_fallback": False,
    "batch_size": 100,
}

DEFAULT_SERVICE_PORTAL_CONFIG = {
    "title": "工业技术协议智能系统",
    "services": {
        "recommendation": {"label": "智能方案推荐", "url": "/", "visible": True, "enabled": True},
        "quick_price": {"label": "简易价格预测", "url": "/price", "visible": True, "enabled": True},
        "advanced_price": {"label": "价格深度分析", "url": "", "visible": True, "enabled": False},
        "effectiveness": {"label": "简易效能评价", "url": "/effectiveness", "visible": True, "enabled": True},
        "admin": {"label": "数据管理中心", "url": "/admin", "visible": True, "enabled": True},
    },
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


def _load_json_object(path, default, label):
    result = json.loads(json.dumps(default, ensure_ascii=False))
    if path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("%s必须是JSON对象" % label)
        result.update(raw)
    result["config_path"] = str(path)
    result["config_loaded"] = path.is_file()
    return result


def load_service_portal_config(root):
    path = Path(root) / "config" / "service_portal.json"
    raw = {}
    if path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("config/service_portal.json必须是JSON对象")
    raw_services = raw.get("services", {})
    if not isinstance(raw_services, dict):
        raise ValueError("config/service_portal.json的services必须是JSON对象")
    result = json.loads(json.dumps(DEFAULT_SERVICE_PORTAL_CONFIG, ensure_ascii=False))
    for key, value in raw.items():
        if key != "services":
            result[key] = value
    services = dict(result["services"])
    for key, value in raw_services.items():
        if isinstance(value, dict):
            services[key] = dict(services.get(key) or {}, **value)
    validated = {}
    for key, value in services.items():
        if not isinstance(value, dict):
            continue
        key, item = str(key), dict(value)
        enabled = _boolean(item.get("enabled"), True)
        visible = _boolean(item.get("visible"), True)
        url = str(item.get("url") or "").strip()
        if url:
            parsed = urlparse(url)
            local = url.startswith("/") and not url.startswith("//") and not parsed.scheme and not parsed.netloc
            external = parsed.scheme in ("http", "https") and bool(parsed.netloc)
            if ("\\" in url or any(ord(char) < 32 for char in url) or not (local or external)):
                raise ValueError("config/service_portal.json服务%s的url不安全或无效" % key)
        elif enabled:
            raise ValueError("config/service_portal.json服务%s启用时必须配置url" % key)
        item["url"], item["enabled"], item["visible"] = url, enabled, visible
        validated[key] = item
    result["services"] = validated
    result["config_path"] = str(path)
    result["config_loaded"] = path.is_file()
    return result


def load_workbench_defaults(root):
    path = Path(root) / "config" / "workbench_defaults.json"
    return _load_json_object(path, {"historical_example_agreement_id": ""}, "config/workbench_defaults.json")
