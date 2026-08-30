# -*- coding: utf-8 -*-
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from app.expert_scheme import ExpertSchemeService
from app.server import Application
from app.store import Store


class MappingRuntime(object):
    def __init__(self):
        self.protocols = []

    def evaluate(self, params, target_protocol=None):
        self.protocols.append(target_protocol)
        return {
            "parameters": {"lock_type": 2}, "predicted_price_wan": 10,
            "capability_score": 115 if target_protocol == "B" else 90,
            "feasibility_probability": 0.9, "cost_effectiveness": 11.5,
        }


class V2151ExpertClosureTest(unittest.TestCase):
    def test_saved_recalculation_restores_business_value_and_protocol(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.db"
            conn = sqlite3.connect(str(path))
            conn.executescript("""
                CREATE TABLE parameter_definitions(
                  parameter_id TEXT PRIMARY KEY, enabled INTEGER, value_type TEXT,
                  allowed_values_json TEXT, model_value_mapping_json TEXT);
                INSERT INTO parameter_definitions VALUES(
                  'lock_type',1,'enum','["manual","auto"]','{"manual":1,"auto":2}');
                CREATE TABLE saved_schemes(
                  id INTEGER PRIMARY KEY, scheme_name TEXT, base_agreement_id TEXT,
                  product_code TEXT, source_type TEXT, params_json TEXT, evaluation_json TEXT,
                  risk_confirmed INTEGER, created_at TEXT, base_params_json TEXT, delta_json TEXT,
                  changed_parameter_ids_json TEXT, target_protocol TEXT, schema_signature TEXT,
                  recommendation_eligible INTEGER, training_candidate INTEGER, enabled INTEGER);
                INSERT INTO saved_schemes VALUES(
                  1,'Expert','H1','P','expert_modified','{"lock_type":"auto"}','{}',0,'2026',
                  '{"lock_type":"manual"}','{}','[]',NULL,NULL,1,1,1);
            """)
            conn.close()
            runtime = MappingRuntime()
            store = Store.__new__(Store)
            store.db_path = path
            store.read_only = False
            store.lock = threading.RLock()
            store.runtime = runtime
            store.derive_tags = lambda params, evaluation=None, inherited_tags=None: []
            item = store.get_saved(1, recalculate=True, target_protocol="B")
            self.assertEqual(item["params"]["lock_type"], "auto")
            self.assertEqual(item["evaluation"]["model_parameters"]["lock_type"], 2)
            self.assertEqual(runtime.protocols, ["B"])

    def test_enum_schema_drift_disables_effective_recommendation(self):
        definitions = {
            "material": {"enabled": 1, "required": 0, "model_bound": 1,
                         "value_type": "enum", "allowed_values_json": '["B","C"]'},
        }
        service = ExpertSchemeService(definitions, "P", encode_parameters=lambda params: dict(params))
        result = service.compatibility({
            "product_code": "P", "params": {"material": "A"},
            "recommendation_eligible": 1, "enabled": 1,
        })
        self.assertFalse(result["business_value_compatible"])
        self.assertFalse(result["recommendation_eligible_effective"])
        self.assertEqual(result["business_value_issues"][0]["reason"], "not_in_current_allowed_values")

    def test_recommendation_batches_current_protocol_and_preserves_business_params(self):
        app = Application.__new__(Application)
        app.expert_evaluation_cache = {}
        app.evaluation_lock = threading.RLock()
        app.expert_schemes = ExpertSchemeService({"lock_type": {"enabled": 1, "value_type": "enum"}}, "P")
        saved = {"id": 1, "scheme_name": "E1", "product_code": "P", "params": {"lock_type": "auto"},
                 "base_params": {"lock_type": "manual"}, "evaluation": {},
                 "compatibility": {"recommendation_eligible_effective": True}}
        app.saved_schemes = lambda: [saved]
        app.generator = type("Generator", (), {"_normalized_distance": lambda self, a, b, definitions: 1.0})()
        app.store = type("Store", (), {
            "parameter_map": lambda self: {"lock_type": {"enabled": 1, "value_type": "enum"}},
            "derive_tags": lambda self, params, evaluation=None: [],
        })()
        calls = []
        def batch(items):
            calls.append(items)
            return [{"parameters": {"lock_type": "auto"}, "capability_score": 115}]
        app._evaluate_batch_with_rules = batch
        items = Application.expert_recommendation_schemes(app, target_protocol="B", recalculate=True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0]["target_protocol"], "B")
        self.assertEqual(items[0]["params"]["lock_type"], "auto")
        self.assertEqual(items[0]["capability_score"], 115)
        cached = Application.expert_recommendation_schemes(app, target_protocol="B", recalculate=True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(cached[0]["capability_score"], 115)

    def test_duplicate_expert_priors_collapse_with_count(self):
        app = Application.__new__(Application)
        app.expert_schemes = ExpertSchemeService({"x": {"enabled": 1, "value_type": "number"}}, "P")
        app.store = type("Store", (), {"parameter_map": lambda self: {"x": {"enabled": 1, "value_type": "number"}}})()
        app.generator = type("Generator", (), {"_normalized_distance": lambda self, a, b, definitions: abs(float(a["x"])-float(b["x"]))})()
        result = Application._dedupe_expert_snapshots(app, [
            {"id": 3, "params": {"x": 3.800}},
            {"id": 2, "params": {"x": 3.800}},
            {"id": 1, "params": {"x": 3.805}},
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 3)
        self.assertEqual(result[0]["expert_prior_count"], 3)

    def test_degraded_saved_detail_uses_persisted_snapshot(self):
        app = Application.__new__(Application)
        saved = {"id": 4, "scheme_name": "E4", "params": {"x": 2}, "base_params": {"x": 1},
                 "saved_evaluation": {"predicted_price_wan": 8}, "evaluation": {"predicted_price_wan": 8}}
        app.store = type("Store", (), {"get_saved": lambda self, scheme_id, recalculate=False: dict(saved)})()
        app.expert_schemes = type("Expert", (), {"compatibility": lambda self, item: {"schema_compatible": True}})()
        app.model_data_sync_error = "services unavailable"
        item = Application.saved_detail(app, 4, target_protocol="B")
        self.assertEqual(item["params"], {"x": 2})
        self.assertEqual(item["current_model_evaluation"]["predicted_price_wan"], 8)
        self.assertFalse(item["model_evaluation_available"])

    def test_outer_frozen_layout_and_long_csv_contract(self):
        root = Path(__file__).resolve().parents[1]
        css = (root / "app/static/styles.css").read_text(encoding="utf-8")
        js = (root / "app/static/app.js").read_text(encoding="utf-8")
        generator = (root / "app/local_generator.py").read_text(encoding="utf-8")
        self.assertIn(".generation-frozen .frozen-list{display:grid;grid-template-columns:minmax(0,1fr)", css)
        self.assertIn('"parameter_id","参数名称","before","after","unit"', js)
        self.assertIn("?protocol_id=", js)
        self.assertIn('"target_protocol": target_protocol', generator)
        self.assertIn("self.evaluate_batch_callback(pending)", generator)


if __name__ == "__main__":
    unittest.main()
