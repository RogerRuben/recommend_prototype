# -*- coding: utf-8 -*-
import json
from contextlib import closing
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

from app.configuration import load_model_service_config, load_service_portal_config
from app.server import Application, Handler
from cost_effectiveness_analysis.app import CostEffectivenessApplication
from cost_effectiveness_analysis.tests.test_db_readonly import _database


class Repo(object):
    def __init__(self):
        self.items = dict(("S%d" % i, {"scheme_id":"S%d" % i,"scheme_name":"方案%d" % i,
            "source":"historical","parameters":{"x":i}}) for i in range(10))
    def get_scheme(self, key): return dict(self.items[key]) if key in self.items else None
    def get_scheme_parameters(self, key, model_values=False): return dict(self.items[key]["parameters"])
    def list_schemes(self, source=None, search=None): return list(self.items.values())
    def get_sources(self): return {"historical":10}


class Client(object):
    def health(self): return {"price":{"status":"ok"},"effectiveness":{"status":"ok"}}
    def evaluate_batch(self, schemes, target_protocol=None):
        rows=[]
        for i,item in enumerate(schemes):
            rows.append({"scheme_id":item["scheme_id"],"predicted_price_wan":None if i==0 else 10+i,
                         "capability_score":80+i,"price_error":"价格失败" if i==0 else None,
                         "effectiveness_error":None})
        return {"items":rows,"models":{"price_model_version":"p1","effectiveness_model_version":"e1"},
                "target_protocol":target_protocol,"analysis_time":"2026-01-01 00:00:00","service_errors":{}}


def test_partial_failure_does_not_fail_analysis(tmp_path):
    config={"host":"127.0.0.1","port":17000,"database":{"path":"missing"},
            "services":{"price":{"url":"p"},"effectiveness":{"url":"e"}},"timeout_seconds":1}
    app=CostEffectivenessApplication(tmp_path,Repo(),Client(),config)
    result=app.analyze({"scheme_ids":["S%d" % i for i in range(10)]})
    assert result["success"] and len(result["schemes"]) == 10
    assert result["summary"]["valid_scheme_count"] == 9
    assert result["schemes"][0]["pareto"] is None
    assert result["schemes"][0]["price_error"] == "价格失败"


def test_selection_limits(tmp_path):
    config={"host":"127.0.0.1","port":17000,"database":{"path":"missing"},
            "services":{"price":{"url":"p"},"effectiveness":{"url":"e"}},"timeout_seconds":1}
    app=CostEffectivenessApplication(tmp_path,Repo(),Client(),config)
    try:
        app.analyze({"scheme_ids":["S0"]})
        assert False
    except ValueError as exc:
        assert "至少两个" in str(exc)


def test_portal_workbench_uses_the_main_origin_and_session(tmp_path, monkeypatch):
    db = tmp_path / "schemes.db"
    _database(db)
    original_db = db.read_bytes()
    app = Application.__new__(Application)
    app.root = tmp_path
    app.static_dir = Path(__file__).resolve().parents[2] / "app" / "static"
    app.store = SimpleNamespace(db_path=db)
    app.portal_config = load_service_portal_config(tmp_path)
    app.model_config = load_model_service_config(tmp_path)
    app.auth_enabled = app.demo_read_only = True
    app.disable_admin = False
    app.auth_username, app.auth_secret, app.auth_ttl_seconds = "test", b"test-secret", 300
    monkeypatch.setattr("cost_effectiveness_analysis.app.CostEffectivenessModelClient", lambda *args: Client())
    handler = type("PortalTestHandler", (Handler,), {"app": app})
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with closing(HTTPConnection("127.0.0.1", server.server_port, timeout=5)) as client:
                cookie = {"Cookie": "%s=%s" % (Handler.AUTH_COOKIE, app.make_auth_token("test"))}

                def request(path, method="GET", body=None, authenticated=True):
                    client.request(method, path, body, cookie if authenticated else {})
                    response = client.getresponse()
                    return response, response.read()

                response, payload = request("/api/portal")
                assert response.status == 200
                entry = next(item for item in json.loads(payload)["services"] if item["key"] == "cost_effectiveness_analysis")
                workbench = entry["url"]
                assert workbench == "/cost-effectiveness/" and not entry["external"]

                response, _ = request("/cost-analysis")
                assert response.status == 302 and response.headers["Location"] == workbench
                response, _ = request(workbench, authenticated=False)
                assert response.status == 302 and response.headers["Location"].startswith("/login?next=")
                response, _ = request(workbench + "api/schemes", authenticated=False)
                assert response.status == 401
                response, payload = request(workbench)
                assert response.status == 200 and "效费比分析工作台" in payload.decode("utf-8")
                for asset in ("app.js", "styles.css"):
                    response, _ = request(workbench + asset)
                    assert response.status == 200
                response, payload = request(workbench + "api/schemes?source=expert_saved")
                assert response.status == 200 and [item["scheme_id"] for item in json.loads(payload)["items"]] == ["saved:1"]
                response, payload = request(workbench + "health")
                assert response.status == 200 and json.loads(payload)["recommendation_url"] == "/portal"
                body = json.dumps({"scheme_ids": ["agreement:H1", "saved:1"]})
                response, payload = request(workbench + "api/analyze", "POST", body)
                assert response.status == 200 and json.loads(payload)["success"]
        finally:
            server.shutdown()
            worker.join()
    assert db.read_bytes() == original_db
