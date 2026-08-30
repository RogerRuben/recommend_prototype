# -*- coding: utf-8 -*-
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app.configuration import load_model_service_config, save_price_output_config
from app.expert_scheme import ExpertSchemeService
from app.model_service_client import ModelServiceGateway
from app.price_output import PriceOutputNormalizer, validate_price_output_config
from app.server import Application
from app.store import Store


def effect_response(parameters=None):
    return {
        "parameters": parameters or {"x": 1},
        "evaluation": {
            "effectiveness_score": 100,
            "conservative_capability_score": 95,
            "feasibility_probability": 0.9,
        },
        "model": {"model_version": "effect-v1"},
    }


def price_response(value=120000, interval=None):
    return {
        "prediction": {
            "predicted_price_wan": value,
            "price_interval_wan": interval or [110000, 130000],
        },
        "model": {"model_version": "price-v1"},
    }


class V2152ExpertRevisionPriceOutputTest(unittest.TestCase):
    def make_store(self, path):
        conn = sqlite3.connect(str(path))
        conn.executescript("""
            CREATE TABLE saved_schemes(
              id INTEGER PRIMARY KEY AUTOINCREMENT, scheme_name TEXT, base_agreement_id TEXT,
              product_code TEXT, source_type TEXT, params_json TEXT, evaluation_json TEXT,
              risk_confirmed INTEGER, created_at TEXT, base_params_json TEXT, delta_json TEXT,
              changed_parameter_ids_json TEXT, target_protocol TEXT, schema_signature TEXT,
              recommendation_eligible INTEGER, training_candidate INTEGER, enabled INTEGER);
            CREATE TABLE audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT,
              object_type TEXT, object_id TEXT, detail_json TEXT, created_at TEXT);
        """)
        conn.close()
        store = Store.__new__(Store)
        store.db_path = path
        store.read_only = False
        store.lock = threading.RLock()
        store.current_product_code = lambda: "P"
        return store

    def save(self, store, name=None, base="H-018", base_name="基础舱门锁K型"):
        return store.save_scheme(
            name, base, "historical_modified", {"x": 1}, {"predicted_price_wan": 12},
            base_params={"x": 0}, delta={"x": {"before": 0, "after": 1}},
            changed_parameter_ids=["x"], base_scheme_name=base_name,
        )

    def test_server_allocates_revision_and_unique_default_name(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(Path(directory) / "saved.db")
            first = self.save(store)
            second = self.save(store)
            items = list(reversed(store.list_saved()))
            self.assertEqual([x["expert_revision_no"] for x in items], [1, 2])
            self.assertEqual(items[0]["scheme_name"], "基础舱门锁K型-专家修订-01")
            self.assertEqual(items[1]["scheme_name"], "基础舱门锁K型-专家修订-02")
            third = self.save(store, "轻量化试验方案")
            custom = next(x for x in store.list_saved() if x["id"] == third)
            self.assertEqual(custom["scheme_name"], "轻量化试验方案")
            self.assertEqual(custom["expert_revision_no"], 3)
            child = self.save(store, None, "SAVED-%s" % first, "ignored")
            child_item = next(x for x in store.list_saved() if x["id"] == child)
            self.assertEqual(child_item["root_base_agreement_id"], "H-018")
            self.assertEqual(child_item["parent_saved_scheme_id"], first)
            self.assertEqual(child_item["expert_revision_no"], 4)

    def test_price_units_and_intervals_normalize_to_wan(self):
        cases = [
            ({"unit": "yuan", "scale": 1}, 120000, 12),
            ({"unit": "yuan", "scale": 1000}, 120, 12),
            ({"unit": "wan_yuan", "scale": 1}, 12.5, 12.5),
        ]
        for config, raw, expected in cases:
            normalizer = PriceOutputNormalizer(config)
            self.assertAlmostEqual(normalizer.normalize_value(raw), expected)
        normalized = PriceOutputNormalizer({"unit": "yuan", "scale": 1}).normalize_response(
            price_response(120000, [110000, 130000])
        )
        self.assertEqual(normalized["prediction"]["predicted_price_wan"], 12)
        self.assertEqual(normalized["prediction"]["price_interval_wan"], [11, 13])
        self.assertEqual(normalized["price_output_normalization"]["raw_value"], 120000)

    def test_gateway_single_batch_workbench_and_historical_are_consistent(self):
        gateway = ModelServiceGateway(price_output_config={"unit": "yuan", "scale": 1})
        single = gateway._merge({"parameters": {"x": 1}}, price_response(), effect_response())
        batch = gateway._merge({"parameters": {"x": 1}}, price_response(), effect_response())
        self.assertEqual(single["predicted_price_wan"], 12)
        self.assertEqual(single["price_interval_wan"], [11, 13])
        self.assertEqual(batch["cost_effectiveness"], single["cost_effectiveness"])
        with patch("app.model_service_client._json_request", return_value=price_response()):
            workbench = gateway.predict_price({"x": 1}, "P")
        self.assertEqual(workbench["prediction"]["predicted_price_wan"], 12)
        historical = gateway._merge_effectiveness_only(
            {"parameters": {"x": 1}}, effect_response(), historical_price_wan=12
        )
        self.assertEqual(historical["predicted_price_wan"], 12)
        self.assertIsNone(historical["price_output_normalization"])

        def fake_request(url, payload=None, timeout=15):
            if url.endswith("/api/v1/predict/batch"):
                return {"items": [dict(price_response(), candidate_id="c1")]}
            if url.endswith("/api/v1/evaluate/batch"):
                return {"items": [dict(effect_response(), candidate_id="c1")]}
            if url.endswith("/api/v1/predict"):
                return price_response()
            if url.endswith("/api/v1/evaluate"):
                return effect_response()
            raise AssertionError(url)
        gateway.product_code = "P"
        with patch("app.model_service_client._json_request", side_effect=fake_request):
            actual_single = gateway.evaluate({"x": 1})
            actual_batch = gateway.evaluate_batch([{"candidate_id": "c1", "parameters": {"x": 1}}])[0]
        self.assertEqual(actual_single["predicted_price_wan"], 12)
        self.assertEqual(actual_batch["predicted_price_wan"], 12)
        self.assertEqual(actual_single["price_interval_wan"], actual_batch["price_interval_wan"])
        self.assertEqual(actual_single["cost_effectiveness"], actual_batch["cost_effectiveness"])

    def test_configuration_validation_atomic_merge_and_environment_override(self):
        for bad in ({"unit": "RMB_UNKNOWN", "scale": 1}, {"unit": "yuan", "scale": 0},
                    {"unit": "yuan", "scale": -1}, {"unit": "yuan", "scale": float("nan")}):
            with self.assertRaises(ValueError):
                validate_price_output_config(bad)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config/model_services.json").write_text(
                json.dumps({"execution_mode": "services", "price_service_url": "http://p",
                            "effectiveness_service_url": "http://e", "custom": "preserved"}),
                encoding="utf-8",
            )
            save_price_output_config(root, {"unit": "yuan", "scale": 1})
            raw = json.loads((root / "config/model_services.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["custom"], "preserved")
            self.assertEqual(load_model_service_config(root)["price_output"], {"unit": "yuan", "scale": 1.0})
            with patch.dict("os.environ", {"IPDEMO_PRICE_OUTPUT_UNIT": "wan_yuan",
                                            "IPDEMO_PRICE_OUTPUT_SCALE": "2"}):
                effective = load_model_service_config(root)
            self.assertEqual(effective["price_output"], {"unit": "wan_yuan", "scale": 2.0})
            self.assertTrue(effective["price_output_environment_override"])

            app = Application.__new__(Application)
            app.root = root
            app.demo_read_only = False
            app.model_config = load_model_service_config(root)
            app.model_gateway = ModelServiceGateway(price_output_config=app.model_config["price_output"])
            invalidated = []
            app._invalidate_runtime_caches = lambda: invalidated.append(True)
            app.store = type("Store", (), {"audit_event": lambda self, *args, **kwargs: None})()
            result = Application.save_model_service_settings(
                app, {"price_output": {"unit": "wan_yuan", "scale": 2}}
            )
            self.assertTrue(result["caches_invalidated"])
            self.assertEqual(invalidated, [True])
            self.assertEqual(app.model_gateway.price_normalizer.normalize_value(3), 6)

    def test_schema_and_cache_identity_cover_business_and_model_contracts(self):
        base = {"x": {"enabled": 1, "value_type": "enum", "allowed_values_json": '["A"]',
                      "special_value_keys_json": '["NONE"]', "search_type": "unordered_enum"}}
        service = ExpertSchemeService(base, "P")
        signature = service.schema_signature()
        changed = {"x": dict(base["x"], allowed_values_json='["B"]')}
        self.assertNotEqual(signature, ExpertSchemeService(changed, "P").schema_signature())

        app = Application.__new__(Application)
        app.runtime = type("Runtime", (), {"manifest": lambda self: {
            "price": {"model_version": "p1"}, "effectiveness": {"model_version": "e1"}}})()
        app.model_gateway = ModelServiceGateway(price_output_config={"unit": "yuan", "scale": 1})
        with patch.object(app.model_gateway, "schemas", side_effect=RuntimeError("offline")):
            first = Application._expert_evaluation_identity(app)
            app.runtime = type("Runtime", (), {"manifest": lambda self: {
                "price": {"model_version": "p2"}, "effectiveness": {"model_version": "e1"}}})()
            self.assertNotEqual(first, Application._expert_evaluation_identity(app))
            app.runtime = type("Runtime", (), {"manifest": lambda self: {
                "price": {"model_version": "p1"}, "effectiveness": {"model_version": "e1"}}})()
            app.model_gateway.set_price_output_config({"unit": "wan_yuan", "scale": 1})
            self.assertNotEqual(first, Application._expert_evaluation_identity(app))

    def test_ui_and_api_contracts_are_wired(self):
        root = Path(__file__).resolve().parents[1]
        admin = (root / "app/static/admin.js").read_text(encoding="utf-8")
        app_js = (root / "app/static/app.js").read_text(encoding="utf-8")
        server = (root / "app/server.py").read_text(encoding="utf-8")
        self.assertIn("价格预测服务输出", admin)
        self.assertIn("/api/admin/model-service-settings", admin)
        self.assertIn("专家修订 #", app_js)
        self.assertIn("base_agreement_name", app_js)
        self.assertIn('path == "/api/admin/model-service-settings"', server)


if __name__ == "__main__":
    unittest.main()
