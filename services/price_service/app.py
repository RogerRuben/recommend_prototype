# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.common.http_service import ServiceApplication, JsonServiceError, run_service
from services.price_service.native_bundle import (
    load_bundle, predict as native_predict, predict_batch as native_predict_batch,
    file_sha256, active_model_names,
)


class PriceService(ServiceApplication):
    service_name = "price-prediction-service"
    service_version = "1.0.1"

    def __init__(self, model_path=None, fallback_json=None, allow_degraded=False, allow_model_fallback=False):
        self.model_path = Path(model_path).resolve() if model_path else None
        self.fallback_json = Path(fallback_json).resolve() if fallback_json else None
        self.allow_degraded = bool(allow_degraded)
        self.allow_model_fallback = bool(allow_model_fallback)
        self.backend = None
        self.bundle = None
        self.load_error = None
        self._load()

    def _load(self):
        if self.model_path and self.model_path.is_file():
            try:
                self.bundle = load_bundle(self.model_path)
                self.backend = "native_pickle"
                return
            except Exception as exc:
                self.load_error = str(exc)
                if not self.fallback_json or not self.allow_model_fallback:
                    raise RuntimeError("原生价格模型存在但加载失败，禁止静默切换模型: %s" % exc)
        if self.fallback_json and self.fallback_json.is_file():
            from app.model_runtime import PriceBundleV4, PriceBundle
            raw = json.loads(self.fallback_json.read_text(encoding="utf-8"))
            if str(raw.get("recommendation_contract_version") or "") == "4.0":
                self.bundle = PriceBundleV4(raw, self.fallback_json)
            else:
                self.bundle = PriceBundle(raw, self.fallback_json)
            self.backend = "portable_json"
            return
        raise RuntimeError("未找到可加载的价格模型。请配置price_native_bundle.pkl或price_bundle.json")

    def schema(self):
        if self.backend == "native_pickle":
            return {
                "service": self.service_name,
                "product_code": self.bundle.get("product_code"),
                "product_name": self.bundle.get("product_name"),
                "model_version": self.bundle.get("model_version"),
                "backend": self.backend,
                "fields": self.bundle.get("feature_schema") or [],
                "feature_order": self.bundle.get("feature_order") or [],
                "model_count": len(active_model_names(self.bundle)),
                "model_names": active_model_names(self.bundle),
                "required_modules": self.bundle.get("required_modules") or [],
                "load_warning": self.load_error,
            }
        fields = []
        for item in self.bundle.raw_contract:
            fields.append({
                "field_name": item.get("key"), "field_label": item.get("label", item.get("key")),
                "dtype": item.get("dtype") or item.get("type", "number"), "unit": item.get("unit", ""),
                "required": bool(item.get("required", True)), "missing_policy": item.get("missing_policy", "reject"),
                "training_mean": item.get("training_mean"), "generation_min": item.get("min"), "generation_max": item.get("max"),
                "parser": item.get("parser"), "allowed_values": item.get("allowed_values"),
                "source": item.get("source", "product_parameter"),
                "default_visible": False,
            })
        product_code = self.bundle.bundle.get("product_code") or self.bundle.bundle.get("manifest", {}).get("product_code")
        model_version = self.bundle.bundle.get("model_version") or self.bundle.bundle.get("manifest", {}).get("model_version")
        return {"service": self.service_name, "product_code": product_code, "model_version": model_version, "backend": self.backend, "fields": fields, "load_warning": self.load_error}

    def health(self):
        data = ServiceApplication.health(self)
        data.update({
            "backend": self.backend,
            "model_version": self.schema().get("model_version"),
            "product_code": self.schema().get("product_code"),
            "model_path": str(self.model_path or self.fallback_json or ""),
            "model_sha256": file_sha256(self.model_path) if self.model_path and self.model_path.is_file() else None,
            "load_warning": self.load_error,
            "exact_mode": self.backend == "native_pickle" and not self.allow_degraded,
            "model_count": self.schema().get("model_count"),
            "model_names": self.schema().get("model_names"),
            "required_modules": self.schema().get("required_modules"),
        })
        return data

    def _one(self, request):
        params = request.get("parameters") or request.get("params") or {}
        if self.backend == "native_pickle":
            result = native_predict(self.bundle, params, allow_degraded=self.allow_degraded)
        else:
            result = self.bundle.predict(params)
            result["prediction_mode"] = "portable_json"
            result["input_status"] = {
                "filled_fields": dict((x.get("parameter_id"), {"value": x.get("value"), "strategy": x.get("policy")}) for x in result.get("imputed_features", [])),
                "ignored_fields": sorted(set(params) - set(x.get("key") for x in self.bundle.raw_contract)),
                "warnings": [str(x) for x in result.get("feature_anomalies", [])],
            }
        return self._response(request, params, result)

    def _response(self, request, params, result):
        return {
            "request_id": request.get("request_id"),
            "candidate_id": request.get("candidate_id"),
            "success": True,
            "prediction": {
                "predicted_price_wan": result.get("predicted_price_wan"),
                "price_interval_wan": result.get("price_interval_wan"),
                "confidence": result.get("confidence") or result.get("price_confidence") or "medium",
            },
            "input_status": result.get("input_status") or {},
            "domain_status": {
                "in_domain": not bool((result.get("domain_assessment") or {}).get("is_anomaly")) and not bool((result.get("input_status") or {}).get("warnings")),
                "warnings": (result.get("input_status") or {}).get("warnings") or [str(x) for x in result.get("feature_anomalies", [])],
            },
            "model": {
                "service_version": self.service_version,
                "model_version": self.schema().get("model_version"),
                "product_code": self.schema().get("product_code"),
                "backend": self.backend,
                "prediction_mode": result.get("prediction_mode"),
                "model_count": self.schema().get("model_count"),
                "model_names": self.schema().get("model_names"),
            },
            "debug": {"member_predictions": result.get("member_predictions"), "skipped_members": result.get("skipped_members")},
        }

    def handle_post(self, path, payload):
        if path == "/api/v1/predict":
            return self._one(payload)
        if path == "/api/v1/predict/batch":
            items = payload.get("items") or []
            if len(items) > 1000:
                raise JsonServiceError("单批最多1000条", 400, "batch_too_large")
            requests = []
            for item in items:
                request = dict(item)
                request.setdefault("request_id", payload.get("request_id"))
                request.setdefault("product_code", payload.get("product_code"))
                requests.append(request)
            if self.backend == "native_pickle":
                params_list = [request.get("parameters") or request.get("params") or {} for request in requests]
                predictions = native_predict_batch(self.bundle, params_list, allow_degraded=self.allow_degraded)
                results = [
                    self._response(request, params, result)
                    for request, params, result in zip(requests, params_list, predictions)
                ]
            else:
                results = [self._one(request) for request in requests]
            return {"request_id": payload.get("request_id"), "success": True, "count": len(results), "items": results, "model": self.health()}
        raise JsonServiceError("接口不存在", 404, "not_found")

    def test_path(self):
        return "/api/v1/predict"

    def batch_path(self):
        return "/api/v1/predict/batch"

    def example_request(self):
        # The online test page must submit a complete runnable request.  Some
        # legacy portable bundles do not contain raw-feature ranges, so never
        # emit None and never truncate required fields.
        example = {}
        for field in self.schema().get("fields", []):
            key = field.get("field_name") or field.get("key")
            dtype = str(field.get("dtype") or "").lower()
            allowed = field.get("allowed_values") or field.get("categories") or []
            if dtype in ("enum", "categorical", "category") and allowed:
                value = allowed[0]
            else:
                value = field.get("training_mean")
            if value is None:
                lower = field.get("generation_min")
                upper = field.get("generation_max")
                if lower is not None and upper is not None:
                    value = (float(lower) + float(upper)) / 2.0
                elif lower is not None:
                    value = lower
                elif dtype in ("boolean", "bool"):
                    value = False
                else:
                    value = 1.0
            example[key] = value
        return {"request_id": "PRICE-DEMO-001", "product_code": self.schema().get("product_code"), "parameters": example}

    def openapi(self):
        return {
            "openapi": "3.0.3",
            "info": {"title": "价格预测服务 API", "version": self.service_version, "description": "独立价格模型服务。原生模式直接加载完整pickle模型包；兼容模式使用纯JSON模型。"},
            "paths": {
                "/health": {"get": {"summary": "健康检查与模型加载状态"}},
                "/api/v1/schema": {"get": {"summary": "价格模型字段契约"}},
                "/api/v1/predict": {"post": {"summary": "单方案价格预测"}},
                "/api/v1/predict/batch": {"post": {"summary": "批量价格预测，最多1000条"}},
                "/openapi.json": {"get": {"summary": "OpenAPI 3.0文档"}},
                "/docs": {"get": {"summary": "简易接口前端"}},
            },
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("PRICE_SERVICE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PRICE_SERVICE_PORT", "18101")))
    parser.add_argument("--model", default=os.environ.get("PRICE_NATIVE_BUNDLE", str(ROOT / "services" / "price_service" / "model" / "price_native_bundle.pkl")))
    parser.add_argument("--fallback-json", default=os.environ.get("PRICE_JSON_BUNDLE", str(ROOT / "models" / "price_bundle.json")))
    parser.add_argument("--allow-degraded", action="store_true", default=str(os.environ.get("PRICE_ALLOW_DEGRADED", "0")).lower() in ("1", "true", "yes"))
    parser.add_argument("--allow-model-fallback", action="store_true", default=str(os.environ.get("PRICE_ALLOW_MODEL_FALLBACK", "0")).lower() in ("1", "true", "yes"))
    args = parser.parse_args()
    model = args.model if Path(args.model).is_file() else None
    fallback = args.fallback_json if Path(args.fallback_json).is_file() else None
    run_service(PriceService(model, fallback, args.allow_degraded, args.allow_model_fallback), args.host, args.port)


if __name__ == "__main__":
    main()
