# -*- coding: utf-8 -*-
"""V21 UX configuration and Workbench boundaries."""
from __future__ import print_function

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.configuration import load_model_service_config, load_service_portal_config
from app.server import Application, Handler
from app.store import Store


def static_contracts():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")
    for token in ("railResizeHandle", "hideCoveredParams", "parameterSearch", "workflowStatus", "helpBtn"):
        assert token in html
    assert 'localStorage.setItem(key,String(Math.round(value)))' in js
    assert 'key="ipdemo-search-rail-width"' in js
    assert "tag_parameter_coverage" in js
    assert "当前显式条件仍按用户输入优先" in js
    assert 'data-source="historical"' in html and 'data-source="generated"' in html and 'data-source="both"' in html
    assert 'source_mode:q("sourceMode").value' in js
    assert "--search-rail-width:390px" in css
    assert "min(680px,55vw)" in css
    assert "@media(max-width:900px)" in css and ".rail-resize-handle{display:none}" in css
    # Presentation state must never enter either request/fingerprint contract.
    payload_body = js[js.index("function requestPayload"):js.index("function parameter(")]
    assert "search-rail-width" not in payload_body and "railWidth" not in payload_body


def portal_and_login_contracts():
    portal = load_service_portal_config(ROOT)
    models = load_model_service_config(ROOT)
    assert list(portal["services"]) == ["recommendation", "quick_price", "advanced_price", "effectiveness", "admin"]
    assert portal["services"]["advanced_price"]["url"] == "http://192.168.10.88:8080/"
    assert "advanced_price" not in models
    assert models["price_service_url"].endswith(":18101")
    assert models["effectiveness_service_url"].endswith(":18102")
    assert Handler._safe_next("/admin?tab=data") == "/admin?tab=data"
    for unsafe in ("https://evil.test/", "//evil.test/", "/\\evil.test/", "admin", "javascript:alert(1)"):
        assert Handler._safe_next(unsafe) is None
    run_app = (ROOT / "run_app.py").read_text(encoding="utf-8")
    assert '"url": "http://%s:%d/portal"' in run_app


def deterministic_history_contract():
    with tempfile.TemporaryDirectory(prefix="ipdemo_v21_") as folder:
        db = Path(folder) / "v21.db"
        conn = sqlite3.connect(str(db))
        conn.executescript("""
          CREATE TABLE products(product_code TEXT PRIMARY KEY, enabled INTEGER);
          CREATE TABLE agreements(
            agreement_id TEXT PRIMARY KEY, product_code TEXT, agreement_name TEXT,
            agreement_source TEXT, source_year INTEGER, params_json TEXT,
            tags_json TEXT, enabled INTEGER, updated_at TEXT
          );
          INSERT INTO products VALUES('P',1);
          INSERT INTO agreements VALUES('AGR-Z','P','旧方案','historical',2023,'{"x":3}','[]',1,'2026-01-01');
          INSERT INTO agreements VALUES('AGR-B','P','同年后更新','imported',2024,'{"x":2}','[]',1,'2026-02-01');
          INSERT INTO agreements VALUES('AGR-A','P','同年先更新','historical',2024,'{"x":1}','[]',1,'2026-01-01');
        """)
        conn.commit()
        conn.close()
        store = Store(db, Path(folder) / "unused.csv", None, read_only=True)
        assert store.workbench_example()["agreement_id"] == "AGR-B"
        assert store.workbench_example("AGR-A")["agreement_id"] == "AGR-A"
        assert store.workbench_example("MISSING")["agreement_id"] == "AGR-B"


class FakeStore(object):
    def parameter_map(self):
        return {
            "flag": {
                "label": "是否具备该属性", "unit": "", "value_type": "boolean",
                "allowed_values_json": "[0,1]",
                "model_value_mapping_json": '{"0":-1,"1":1}',
                "display_value_mapping_json": '{"0":"无","1":"有"}',
            },
            "weight": {"label": "重量", "unit": "kg", "value_type": "number"},
        }

    def workbench_example(self, preferred=None):
        return {"agreement_id": "AGR-ONE", "agreement_name": "统一历史方案", "source_year": 2024,
                "parameters": {"weight": 4.2}}

    def business_parameters(self, model_params, source_params=None):
        result = dict(source_params or {})
        result.update({key: (0 if value == -1 else value) for key, value in model_params.items() if key not in result})
        return result


def workbench_enrichment_contract():
    app = Application.__new__(Application)
    app.store = FakeStore()
    app.workbench_defaults = {"historical_example_agreement_id": ""}
    raw = {"fields": [
        {"field_name": "weight", "label": "model weight", "dtype": "number", "default_value": 8},
        {"field_name": "flag", "dtype": "number", "default_value": -1},
        {"field_name": "external_only", "label": "External Label", "dtype": "number", "training_mean": 9},
    ]}
    price = app._enrich_workbench_schema(raw, "price")
    effect = app._enrich_workbench_schema(raw, "effectiveness")
    assert price["example"]["agreement_id"] == effect["example"]["agreement_id"] == "AGR-ONE"
    fields = {field["field_name"]: field for field in price["fields"]}
    assert fields["weight"]["field_label"] == "重量" and fields["weight"]["example_value"] == 4.2
    assert fields["flag"]["example_value"] == 0
    assert fields["flag"]["allowed_values"] == [0, 1]
    assert fields["external_only"]["field_label"] == "External Label"
    assert fields["external_only"]["example_value"] == 9
    assert json.loads(fields["flag"]["display_value_mapping_json"])["1"] == "有"


if __name__ == "__main__":
    static_contracts()
    portal_and_login_contracts()
    deterministic_history_contract()
    workbench_enrichment_contract()
    print("PASS V21 workflow, portal, deterministic Workbench and value boundaries")
