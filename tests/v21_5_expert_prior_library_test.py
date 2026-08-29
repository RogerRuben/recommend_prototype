# -*- coding: utf-8 -*-
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from app.expert_scheme import ExpertSchemeService
from app.store import Store


class ExpertPriorLibraryTest(unittest.TestCase):
    def setUp(self):
        self.definitions = {
            "weight": {"parameter_id": "weight", "label": "重量", "value_type": "number", "required": 1, "model_bound": 1, "enabled": 1, "decimal_places": 3},
            "material": {"parameter_id": "material", "label": "材料", "value_type": "enum", "required": 0, "model_bound": 1, "enabled": 1},
            "lock_type": {"parameter_id": "lock_type", "label": "锁定方式", "value_type": "enum", "required": 0, "model_bound": 1, "enabled": 1},
        }
        self.service = ExpertSchemeService(self.definitions, "CURRENT")

    def test_definition_aware_delta_only_contains_real_business_changes(self):
        delta = self.service.build_delta(
            {"weight": 4.2, "material": "A", "lock_type": "manual"},
            {"weight": "3.8", "material": "A", "lock_type": "auto"},
        )
        self.assertEqual(set(delta), {"weight", "lock_type"})
        self.assertEqual(delta["weight"], {"before": 4.2, "after": "3.8"})

    def test_product_and_schema_are_both_required(self):
        current = {"product_code": "CURRENT", "params": {"weight": 3.8}, "recommendation_eligible": 1, "enabled": 1}
        self.assertTrue(self.service.compatibility(current)["recommendation_eligible_effective"])
        other = dict(current, product_code="OTHER")
        self.assertFalse(self.service.compatibility(other)["recommendation_eligible_effective"])
        missing = dict(current, params={"material": "A"})
        result = self.service.compatibility(missing)
        self.assertFalse(result["schema_compatible"])
        self.assertEqual(result["missing_fields"], ["weight"])

    def test_store_persists_generated_base_snapshot_after_session_expiry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.db"
            conn = sqlite3.connect(str(path))
            conn.executescript("""
                CREATE TABLE saved_schemes(
                  id INTEGER PRIMARY KEY AUTOINCREMENT, scheme_name TEXT, base_agreement_id TEXT,
                  product_code TEXT, source_type TEXT, params_json TEXT, evaluation_json TEXT,
                  risk_confirmed INTEGER, created_at TEXT, base_params_json TEXT, delta_json TEXT,
                  changed_parameter_ids_json TEXT, target_protocol TEXT, schema_signature TEXT,
                  recommendation_eligible INTEGER, training_candidate INTEGER, enabled INTEGER);
                CREATE TABLE audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, object_type TEXT, object_id TEXT, detail_json TEXT, created_at TEXT);
            """)
            conn.close()
            store = Store.__new__(Store)
            store.db_path = path
            store.read_only = False
            store.lock = threading.RLock()
            store.current_product_code = lambda: "CURRENT"
            base = {"weight": 4.2, "lock_type": "manual"}
            final = {"weight": 3.8, "lock_type": "auto"}
            delta = self.service.build_delta(base, final)
            scheme_id = store.save_scheme(
                "generated expert", "GENBATCH-X-CAND-01", "live_generated_modified",
                final, {"predicted_price_wan": 12.3}, base_params=base, delta=delta,
                changed_parameter_ids=sorted(delta), schema_signature=self.service.schema_signature(),
            )
            saved = store.list_saved()[0]
            self.assertEqual(saved["id"], scheme_id)
            self.assertEqual(saved["base_params"], base)
            self.assertEqual(saved["delta"], delta)
            self.assertEqual(saved["changed_parameter_ids"], sorted(delta))

    def test_training_export_contains_required_snapshots_and_source(self):
        record = self.service.training_export_record({
            "id": 7, "scheme_name": "Expert 7", "product_code": "CURRENT",
            "base_agreement_id": "H-018", "source_type": "historical_modified",
            "base_params": {"weight": 4.2}, "params": {"weight": 3.8},
            "delta": {"weight": {"before": 4.2, "after": 3.8}},
            "changed_parameter_ids": ["weight"], "evaluation": {"capability_score": 100},
            "risk_confirmed": 0, "recommendation_eligible": 1,
            "training_candidate": 1, "created_at": "2026-08-30",
        })
        for key in ("product_code", "base_parameters", "parameters", "delta", "evaluation", "source", "risk_confirmed", "created_at"):
            self.assertIn(key, record)


class CompactControlsContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.html = (root / "app/static/index.html").read_text(encoding="utf-8")
        cls.css = (root / "app/static/styles.css").read_text(encoding="utf-8")
        cls.js = (root / "app/static/app.js").read_text(encoding="utf-8")

    def test_tags_have_no_nested_scroll(self):
        rule = self.css.split(".requirements-card #tagGroups", 1)[1].split("}", 1)[0]
        self.assertNotIn("max-height", rule)
        self.assertNotIn("overflow", rule)
        self.assertIn("flex-wrap:wrap", self.css)

    def test_filter_mode_is_outside_details(self):
        details = self.html.split('<details class="filter-options">', 1)[1].split("</details>", 1)[0]
        self.assertNotIn('id="filterMode"', details)
        self.assertIn('class="mode-row persistent-filter-mode"', self.html)

    def test_frozen_group_grid_and_empty_filter(self):
        rule = self.css.split(".frozen-group-head", 1)[1].split("}", 1)[0]
        self.assertIn("display:grid", rule)
        self.assertIn("grid-template-columns:18px 18px minmax(0,1fr) auto", rule)
        self.assertIn(".filter(function(name){return(groups[name]||[]).length>0})", self.js)


if __name__ == "__main__":
    unittest.main()
