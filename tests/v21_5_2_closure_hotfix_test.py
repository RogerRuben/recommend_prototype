# -*- coding: utf-8 -*-
import threading
import time
import unittest
from pathlib import Path

from app.expert_scheme import ExpertSchemeService
from app.generation_tasks import GenerationTaskManager
from app.model_service_client import ModelServiceGateway
from app.price_output import PriceOutputNormalizer
from app.server import Application


class _Runtime(object):
    schema = {"product_code": "P"}

    def manifest(self):
        return {"model_versions": {"price": "p1", "effectiveness": "e1"}}


class _Store(object):
    def generation_semantics_fingerprint(self):
        return "business-v1"


class _Sessions(object):
    def __init__(self):
        self.added = []

    def add_batch(self, session_id, candidates, fingerprint=None):
        self.added.append((session_id, candidates, fingerprint))
        return "BATCH-1", list(candidates)


class _GenerationApplication(object):
    def __init__(self):
        self.runtime = _Runtime()
        self.store = _Store()
        self.sessions = _Sessions()
        self.entered = threading.Event()
        self.release = threading.Event()

    def generation_budget_limit(self):
        return 2400

    def generation_rounds_limit(self):
        return 15

    def _generate_sync(self, request, progress_callback=None):
        self.entered.set()
        self.release.wait(3)
        if progress_callback:
            progress_callback(80, "即将完成")
        return {"candidates": [{"candidate_id": "C-1"}], "count": 1}


class V2152ClosureHotfixTest(unittest.TestCase):
    def test_legacy_saved_price_snapshot_is_stale_under_new_contract(self):
        app = Application.__new__(Application)
        app.model_gateway = ModelServiceGateway(price_output_config={"unit": "yuan", "scale": 1})
        legacy = {"evaluation": {"predicted_price_wan": 120000}}
        Application._annotate_saved_price_contract(app, legacy)
        contract = legacy["price_evaluation_contract"]
        self.assertTrue(contract["stale"])
        self.assertEqual(contract["saved"]["unit"], "wan_yuan")
        self.assertEqual(contract["current"]["unit"], "yuan")
        self.assertEqual(contract["display_source"], "saved_snapshot_stale")

        current = {
            "evaluation": {
                "predicted_price_wan": 12,
                "price_output_contract": app._current_price_output_contract(),
            }
        }
        Application._annotate_saved_price_contract(app, current)
        self.assertFalse(current["price_evaluation_contract"]["stale"])

    def test_price_normalization_metadata_carries_contract_signature(self):
        normalizer = PriceOutputNormalizer({"unit": "yuan", "scale": 1})
        metadata = normalizer.metadata(120000, 12)
        self.assertEqual(metadata["signature"], normalizer.signature())

    def test_training_export_preserves_expert_revision_lineage(self):
        record = ExpertSchemeService.training_export_record({
            "id": 9,
            "scheme_name": "专家修订",
            "base_agreement_id": "SAVED-8",
            "root_base_agreement_id": "H-018",
            "parent_saved_scheme_id": 8,
            "expert_revision_no": 3,
        })
        self.assertEqual(record["root_base_agreement_id"], "H-018")
        self.assertEqual(record["parent_saved_scheme_id"], 8)
        self.assertEqual(record["expert_revision_no"], 3)

    def test_runtime_invalidation_cancels_running_generation_without_batch(self):
        app = _GenerationApplication()
        manager = GenerationTaskManager(app)
        task = manager.start({"session_id": "S", "count": 1})
        self.assertTrue(app.entered.wait(2))
        manager.invalidate_all()
        app.release.set()

        deadline = time.time() + 3
        while time.time() < deadline:
            state = manager.get(task["task_id"])
            if state and state.get("status") == "cancelled":
                break
            time.sleep(0.02)
        state = manager.get(task["task_id"])
        self.assertEqual(state["status"], "cancelled")
        self.assertTrue(state["invalidated"])
        self.assertEqual(app.sessions.added, [])

    def test_customer_ui_hides_stale_saved_price_and_exports_lineage(self):
        app_js = (Path(__file__).resolve().parents[1] / "app/static/app.js").read_text(encoding="utf-8")
        self.assertIn("保存时价格采用旧输出尺度，当前不作为万元价格展示", app_js)
        self.assertIn("保存时评价未作为当前结果展示", app_js)
        self.assertIn('"root_base_agreement_id","expert_revision_no","parent_saved_scheme_id"', app_js)


if __name__ == "__main__":
    unittest.main()
