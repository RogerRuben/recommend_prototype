# -*- coding: utf-8 -*-
"""Historical samples are evaluated effectiveness-only: no price re-prediction.

Unchanged historical agreements already carry a real transaction price. The
recommendation layer must run only the effectiveness service for them and keep
the stored ``historical_price_wan``, while generated/modified candidates still
receive a full price+effectiveness evaluation.
"""
from __future__ import print_function

import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.model_service_client import ModelServiceGateway, ServiceBackedRuntime
from services.common.http_service import ServiceApplication, make_handler


class EffectStub(ServiceApplication):
    def schema(self):
        return {"product_code": "PROD", "product_name": "p", "backend": "stub",
                "model_version": "E", "fields": [
                    {"field_name": "attr_001", "dtype": "number", "required": True},
                ]}

    def handle_post(self, path, payload):
        candidate = payload.get("candidate_id")
        one = {"candidate_id": candidate, "success": True,
               "parameters": payload.get("parameters") or {},
               "evaluation": {"effectiveness_score": 88.0, "feasibility_probability": 0.9},
               "model": {"model_version": "E", "backend": "stub"}}
        if path.endswith("/batch"):
            return {"success": True, "items": [self.handle_post(path[:-6], i) for i in payload.get("items") or []]}
        return one


class PriceStub(ServiceApplication):
    def __init__(self):
        self.predict_calls = 0

    def schema(self):
        return {"product_code": "PROD", "product_name": "p", "backend": "stub",
                "model_version": "P", "fields": [
                    {"field_name": "attr_001", "dtype": "number", "required": True},
                ]}

    def handle_post(self, path, payload):
        self.predict_calls += 1
        candidate = payload.get("candidate_id")
        one = {"candidate_id": candidate, "success": True,
               "prediction": {"predicted_price_wan": 99.9, "price_interval_wan": [99, 100]},
               "input_status": {}, "domain_status": {"in_domain": True},
               "model": {"model_version": "P", "backend": "stub"}}
        if path.endswith("/batch"):
            return {"success": True, "items": [self.handle_post(path[:-6], i) for i in payload.get("items") or []]}
        return one


def start(app):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server, thread, "http://127.0.0.1:%d" % server.server_address[1]


def main():
    price = PriceStub()
    effect = EffectStub()
    pserver, pthread, purl = start(price)
    eserver, ethread, eurl = start(effect)
    try:
        gateway = ModelServiceGateway(None, purl, eurl, timeout=5, fallback=False)
        runtime = ServiceBackedRuntime(gateway)

        # Effectiveness-only single evaluation keeps the historical price.
        single = runtime.evaluate_effectiveness_only({"attr_001": 1}, historical_price_wan=12.6)
        assert single["price_source"] == "historical", single.get("price_source")
        assert single["predicted_price_wan"] == 12.6
        assert single["capability_score"] == 88.0
        assert single["model_versions"]["price"] is None

        # Effectiveness-only batch never calls the price service.
        price.predict_calls = 0
        batch = runtime.evaluate_batch_effectiveness_only([
            {"candidate_id": "A", "parameters": {"attr_001": 1}, "historical_price_wan": 13.8},
        ])
        assert len(batch) == 1 and batch[0]["price_source"] == "historical"
        assert batch[0]["predicted_price_wan"] == 13.8
        assert price.predict_calls == 0, "effectiveness-only batch must not call price service"

        # A full evaluation still calls the price service and is price_source=predicted.
        price.predict_calls = 0
        full = runtime.evaluate({"attr_001": 1})
        assert full["price_source"] == "predicted"
        assert full["predicted_price_wan"] == 99.9
        assert price.predict_calls == 1

        # Missing historical price must not crash the merge.
        merged = gateway._merge_effectiveness_only(
            {"request_id": "X", "parameters": {"attr_001": 1}},
            {"evaluation": {"effectiveness_score": 77.0, "feasibility_probability": 0.8},
             "model": {"model_version": "E"}},
            None,
        )
        assert merged["predicted_price_wan"] is None and merged["cost_effectiveness"] is None

        print(json.dumps({"status": "PASS", "message": "历史样本效能-only评价且不重算价格"}, ensure_ascii=False))
    finally:
        pserver.shutdown(); pserver.server_close(); pthread.join(timeout=3)
        eserver.shutdown(); eserver.server_close(); ethread.join(timeout=3)


if __name__ == "__main__":
    main()
