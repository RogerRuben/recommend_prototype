# -*- coding: utf-8 -*-
import copy
import hashlib
import json
import math
import os
import tempfile
import unittest
from pathlib import Path

from services.effectiveness_service.app import (
    EffectivenessService,
    FrozenRuntimeBackend,
    OriginalRuntimeBackend,
    backend_from_package,
)
from services.effectiveness_service.lock_v17_adapter import (
    LockV17AdapterError,
    LockV17InputAdapter,
)
from services.effectiveness_service.lock_v17_backend import LockV17Backend
from services.common.http_service import JsonServiceError


def _digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _config(enabled_improve=True):
    labels = {
        "a": "钩锁力-1",
        "b": "钩锁力-2",
        "c": "钩锁刚度-1",
        "d": "钩锁刚度-2",
    }
    return {
        "enabled": True,
        "derived_feature": {
            "target_field": "e",
            "operation": "abs_diff_product",
            "x1": {"fields": ["a", "c"]},
            "x2": {"fields": ["b", "d"]},
            "absence": {
                "sentinel_values": [-1],
                "all_missing_group_is_absent": True,
                "if_any_group_absent": "zero",
                "zero_value": 0.0,
                "partial_group_policy": "reject",
            },
        },
        "public_source_fields": dict(
            (
                key,
                {
                    "field_label": label,
                    "dtype": "number",
                    "unit": "kN" if "力" in label else "kN/mm",
                    "generation_min": -1,
                    "generation_max": 20,
                    "precision": 3,
                    "preference_direction": "neutral",
                    "participates_generation": True,
                    "default_visible": True,
                },
            )
            for key, label in labels.items()
        ),
        "physical_compatibility": {
            "physical_feasibility_evaluated": False,
            "probability_placeholder": 0.65,
        },
        "improvement": {
            "enabled": enabled_improve,
            "rounds": 2,
            "max_candidates": 120,
            "round1_step_ratios": [0.05, 0.1, 0.2],
            "round2_step_ratios": [0.025, 0.05],
            "min_gain": 0.1,
            "lock_absent_derived_groups": True,
        },
    }


def _model():
    core = {
        "model_format": "lock-product-reuse-model-17.0",
        "algorithm_version": "V17-TEST",
        "profile_version": 17,
        "project": {"product_code": "LOCK-V17-TEST", "project_name": "锁V17测试"},
        "schema": {
            "attributes": [
                {
                    "key": "e",
                    "label": "钩锁差异乘积",
                    "unit": "",
                    "data_type": "continuous",
                    "generation_min": 0,
                    "generation_max": 400,
                    "participates_generation": True,
                },
                {
                    "key": "quality",
                    "label": "其它直接输入",
                    "unit": "级",
                    "data_type": "continuous",
                    "generation_min": 0,
                    "generation_max": 20,
                    "precision": 2,
                    "participates_generation": True,
                },
            ],
            "trainable_attribute_keys": ["e", "quality"],
            "dimensions": [],
        },
        "baseline": {
            "profile_id": "REQ-1",
            "profile_name": "基准一",
            "score": 100,
            "params": {"e": 0, "quality": 10},
        },
        "evaluation_baselines": [
            {
                "profile_id": "REQ-1",
                "profile_name": "基准一",
                "score": 100,
                "params": {"e": 0, "quality": 10},
            },
            {
                "profile_id": "REQ-2",
                "profile_name": "基准二",
                "score": 100,
                "params": {"e": 2, "quality": 8},
            },
        ],
        "inference": {},
        "semantics": {"physical_feasibility_included": False},
        "privacy": {"contains_source_workbook": False},
        "training_summary": {},
    }
    output = copy.deepcopy(core)
    output["model_digest"] = _digest(core)
    output["model_version"] = "lock-v17-test-%s" % output["model_digest"][:12]
    output["frozen_at"] = "2026-09-05T00:00:00+08:00"
    return output


RUNTIME_SOURCE = '''
import json
from pathlib import Path

class FrozenLockReuseRuntime(object):
    def __init__(self, model_path):
        self.model = json.loads(Path(model_path).read_text(encoding="utf-8"))

    def evaluate(self, params, profile_id=None):
        if "e" not in params or "quality" not in params:
            raise ValueError("missing model input")
        score = max(0.0, 100.0 - float(params["e"]) - abs(float(params["quality"]) - 10.0))
        status = "reusable" if score >= 80 else "not_reusable"
        return {
            "effectiveness_score": score,
            "effectiveness_interval": [max(0.0, score - 2.0), score + 1.0],
            "overall_reuse_status": status,
            "overall_reuse_label": "可复用" if status == "reusable" else "不建议复用",
            "combined_reuse_threshold": 80,
            "single_attribute_violations": ["钩锁差异乘积"] if status == "not_reusable" else [],
            "uncertain_attributes": [],
            "attributes": [],
            "loss_contributions": [{
                "attribute_key": "e", "attribute_label": "钩锁差异乘积",
                "unit": "", "attribute_weight": 0.5,
                "loss_points": float(params["e"]), "deterioration": 0.1,
            }],
            "migration": {"status": "same_baseline"},
            "conclusion": "test",
            "physical_feasibility_evaluated": False,
            "profile_id": profile_id,
            "params": dict(params),
        }
'''


class LockV17SpecialBackendTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "model").mkdir()
        (self.root / "source").mkdir()
        model = _model()
        self.model_path = self.root / "model" / "frozen_lock_reuse_model.json"
        self.model_path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
        for name in ("lock_utility_model.py", "preference_models.py", "project_excel.py"):
            (self.root / "source" / name).write_text("# test runtime dependency\n", encoding="utf-8")
        (self.root / "source" / "frozen_lock_model.py").write_text(RUNTIME_SOURCE, encoding="utf-8")
        self.config_path = self.root / "adapter.json"
        self.config_path.write_text(json.dumps(_config(), ensure_ascii=False, indent=2), encoding="utf-8")
        paths = [self.model_path] + sorted((self.root / "source").glob("*.py"))
        files = [
            {"path": str(path.relative_to(self.root)).replace("\\", "/"), "sha256": _file_sha(path)}
            for path in paths
        ]
        self.manifest = {
            "format_version": "lock-product-reuse-runtime-package-17.0",
            "model": "model/frozen_lock_reuse_model.json",
            "source_root": "source",
            "model_digest": model["model_digest"],
            "model_version": model["model_version"],
            "files": files,
        }
        self.manifest_path = self.root / "lock_v17_runtime_manifest.json"
        self.manifest_path.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def backend(self):
        return backend_from_package(self.manifest_path, self.config_path)

    def adapter(self):
        return LockV17InputAdapter(_config(), _model()["schema"])

    def test_complete_groups_derive_absolute_difference_product(self):
        model_params, diagnostics = self.adapter().prepare({"a": 10, "b": 6, "c": 8, "d": 5, "quality": 10})
        self.assertEqual(model_params["e"], 12)
        self.assertEqual(diagnostics["derived_features"]["e"]["status"], "derived_complete")

    def test_x1_present_x2_sentinel_is_zero(self):
        params, diagnostics = self.adapter().prepare({"a": 10, "c": 8, "b": -1, "d": -1})
        self.assertEqual(params["e"], 0)
        self.assertEqual(diagnostics["derived_features"]["e"]["x2_status"], "absent")

    def test_x1_sentinel_x2_present_is_zero(self):
        params, diagnostics = self.adapter().prepare({"a": -1, "c": -1, "b": 6, "d": 5})
        self.assertEqual(params["e"], 0)
        self.assertEqual(diagnostics["derived_features"]["e"]["x1_status"], "absent")

    def test_both_sentinel_groups_are_zero(self):
        params, _ = self.adapter().prepare({"a": -1, "b": -1, "c": -1, "d": -1})
        self.assertEqual(params["e"], 0)

    def test_both_missing_groups_are_zero(self):
        params, diagnostics = self.adapter().prepare({})
        self.assertEqual(params["e"], 0)
        self.assertEqual(diagnostics["derived_features"]["e"]["x1_status"], "absent")

    def test_x1_present_x2_missing_is_zero(self):
        params, _ = self.adapter().prepare({"a": 10, "c": 8})
        self.assertEqual(params["e"], 0)

    def test_x1_missing_x2_present_is_zero(self):
        params, _ = self.adapter().prepare({"b": 6, "d": 5})
        self.assertEqual(params["e"], 0)

    def test_normal_and_sentinel_partial_group_rejects(self):
        with self.assertRaises(LockV17AdapterError):
            self.adapter().prepare({"a": 10, "c": -1})

    def test_normal_and_missing_partial_group_rejects(self):
        with self.assertRaises(LockV17AdapterError):
            self.adapter().prepare({"a": 10})

    def test_sentinel_and_missing_partial_group_rejects(self):
        with self.assertRaises(LockV17AdapterError):
            self.adapter().prepare({"a": -1})

    def test_external_e_is_always_recomputed(self):
        params, diagnostics = self.adapter().prepare({"a": 10, "b": 6, "c": 8, "d": 5, "e": 999})
        self.assertEqual(params["e"], 12)
        self.assertTrue(diagnostics["derived_features"]["e"]["external_value_ignored"])

    def test_v17_package_sha_is_verified(self):
        self.model_path.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "文件校验失败"):
            self.backend()

    def test_wrong_package_format_rejects(self):
        raw = copy.deepcopy(self.manifest)
        raw["format_version"] = "wrong"
        self.manifest_path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "格式无效"):
            self.backend()

    def test_model_digest_mismatch_rejects(self):
        raw = copy.deepcopy(self.manifest)
        raw["model_digest"] = "0" * 64
        self.manifest_path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "摘要不一致"):
            self.backend()

    def test_required_runtime_source_must_be_in_sha_manifest(self):
        raw = copy.deepcopy(self.manifest)
        raw["files"] = [
            item for item in raw["files"]
            if item["path"] != "source/project_excel.py"
        ]
        self.manifest_path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "未纳入SHA-256清单"):
            self.backend()

    def test_public_schema_has_four_business_source_fields(self):
        fields = self.backend().schema()["fields"]
        names = [item["field_name"] for item in fields]
        self.assertTrue(set(("a", "b", "c", "d")).issubset(names))
        source_fields = [item for item in fields if item["field_name"] in ("a", "b", "c", "d")]
        self.assertTrue(source_fields)
        self.assertTrue(all(item["required"] is False for item in source_fields))

    def test_public_schema_does_not_expose_derived_e(self):
        schema = self.backend().schema()
        self.assertNotIn("e", [item["field_name"] for item in schema["fields"]])
        self.assertEqual(schema["derived_features"][0]["field_name"], "e")
        self.assertFalse(schema["derived_features"][0]["editable"])

    def test_backend_score_and_interval_mapping(self):
        result = self.backend().evaluate({"a": 10, "b": 6, "c": 8, "d": 5, "quality": 10})
        self.assertEqual(result["capability_score"], 88)
        self.assertEqual(result["effectiveness_score"], 88)
        self.assertEqual(result["conservative_capability_score"], 86)
        self.assertEqual(result["protocol_score_interval"], [86, 89])
        self.assertEqual(result["score_uncertainty_width"], 3)

    def test_loss_contribution_maps_to_negative_score_delta(self):
        result = self.backend().evaluate({"a": 10, "b": 6, "c": 8, "d": 5, "quality": 10})
        self.assertEqual(result["capability_contributors"][0]["score_delta"], -12)

    def test_not_reusable_does_not_become_physical_rejection(self):
        result = self.backend().evaluate({"a": 20, "b": 0, "c": 20, "d": 0, "quality": 10})
        self.assertEqual(result["reuse_assessment"]["overall_reuse_status"], "not_reusable")
        self.assertTrue(result["physical_gate"]["passed"])
        self.assertEqual(result["hard_violations"], [])

    def test_feasibility_placeholder_is_explicitly_not_evaluated(self):
        result = self.backend().evaluate({"a": 10, "b": 6, "c": 8, "d": 5, "quality": 10})
        self.assertEqual(result["feasibility_probability"], 0.65)
        self.assertFalse(result["physical_feasibility_evaluated"])
        self.assertEqual(result["physical_gate"]["decision"], "pass_not_evaluated")
        self.assertTrue(result["experience_extrapolations"])

    def test_packaged_profile_id_is_forwarded(self):
        result = self.backend().evaluate({"a": 10, "b": 6, "c": 8, "d": 5, "quality": 10}, "REQ-2")
        self.assertEqual(result["protocol"]["profile_id"], "REQ-2")
        self.assertEqual(result["raw_evaluation"]["profile_id"], "REQ-2")

    def test_unknown_profile_id_rejects(self):
        with self.assertRaisesRegex(ValueError, "不存在评价基准"):
            self.backend().evaluate({"a": 10, "b": 6, "c": 8, "d": 5, "quality": 10}, "UNKNOWN")

    def test_public_protocol_metadata_does_not_expose_internal_reference_values(self):
        schema = self.backend().schema()
        self.assertNotIn("reference_values", schema["active_protocol"])
        self.assertTrue(all("reference_values" not in item for item in schema["protocol_profiles"]))
        result = self.backend().evaluate({"a": 10, "b": 6, "c": 8, "d": 5, "quality": 10}, "REQ-2")
        self.assertNotIn("reference_values", result["protocol"])

    def test_matching_reference_values_are_also_rejected_by_public_contract(self):
        target = {"profile_id": "REQ-2", "reference_values": {"e": 2, "quality": 8}}
        with self.assertRaisesRegex(ValueError, "只接受冻结运行包中的profile_id"):
            self.backend().evaluate({"a": 10, "b": 6, "c": 8, "d": 5, "quality": 10}, target)

    def test_mismatched_reference_values_reject(self):
        target = {"profile_id": "REQ-2", "reference_values": {"e": 3, "quality": 8}}
        with self.assertRaisesRegex(ValueError, "只接受冻结运行包中的profile_id"):
            self.backend().evaluate({"a": 10, "b": 6, "c": 8, "d": 5, "quality": 10}, target)

    def test_improve_returns_business_fields_only(self):
        result = self.backend().improve({"a": 1, "b": 1, "c": 1, "d": 1, "quality": 0})
        plan = result["improvement_plan"]
        self.assertEqual(plan["status"], "improved")
        self.assertNotIn("e", plan["recommended_parameters"])
        self.assertIn("quality", plan["recommended_parameters"])

    def test_improve_locks_all_derived_sources_when_one_group_absent(self):
        result = self.backend().improve({"a": 10, "c": 8, "b": -1, "d": -1, "quality": 0})
        changed = result["improvement_plan"]["changed_fields"]
        self.assertFalse(set(("a", "b", "c", "d")) & set(changed))

    def test_service_response_exposes_diagnostics_without_e_parameter(self):
        service = EffectivenessService(self.backend())
        response = service._one({"parameters": {"a": 10, "b": 6, "c": 8, "d": 5, "quality": 10}})
        self.assertEqual(response["derived_features"]["e"]["value"], 12)
        self.assertNotIn("e", response["parameters"])
        self.assertFalse(response["physical_feasibility_evaluated"])

    def test_service_maps_partial_group_to_http_400_contract(self):
        service = EffectivenessService(self.backend())
        with self.assertRaises(JsonServiceError) as captured:
            service._one({"parameters": {"a": 10, "c": -1, "quality": 10}})
        self.assertEqual(captured.exception.status, 400)
        self.assertEqual(captured.exception.code, "lock_v17_invalid_input")

    def test_schema_capabilities_describe_special_backend(self):
        schema = self.backend().schema()
        self.assertEqual(schema["backend"], "lock_v17_frozen_runtime")
        self.assertTrue(schema["capabilities"]["dynamic_target_protocol"])
        self.assertTrue(schema["capabilities"]["counterfactual_improvement"])
        self.assertFalse(schema["capabilities"]["physical_feasibility"])

    def test_batch_uses_the_same_adapter_for_mixed_valid_states(self):
        service = EffectivenessService(self.backend())
        response = service.handle_post("/api/v1/evaluate/batch", {"items": [
            {"candidate_id": "both", "parameters": {"a": 10, "b": 6, "c": 8, "d": 5, "quality": 10}},
            {"candidate_id": "x1", "parameters": {"a": 10, "c": 8, "b": -1, "d": -1, "quality": 10}},
            {"candidate_id": "none", "parameters": {"a": -1, "b": -1, "c": -1, "d": -1, "quality": 10}},
        ]})
        self.assertEqual(response["count"], 3)
        self.assertEqual(response["items"][0]["derived_features"]["e"]["value"], 12)
        self.assertEqual(response["items"][1]["derived_features"]["e"]["value"], 0)
        self.assertEqual(response["items"][2]["derived_features"]["e"]["value"], 0)

    def test_batch_rejects_invalid_partial_group(self):
        service = EffectivenessService(self.backend())
        with self.assertRaises(JsonServiceError) as captured:
            service.handle_post("/api/v1/evaluate/batch", {"items": [
                {"parameters": {"a": 10, "c": -1, "quality": 10}},
            ]})
        self.assertEqual(captured.exception.status, 400)

    def test_existing_backend_types_remain_separate(self):
        self.assertFalse(issubclass(LockV17Backend, OriginalRuntimeBackend))
        self.assertTrue(issubclass(FrozenRuntimeBackend, OriginalRuntimeBackend))


class LockV17RealFrozenPackageSmokeTest(unittest.TestCase):
    """Opt-in E2E smoke against the final, non-stub V17 frozen package."""

    def test_real_frozen_package_schema_evaluate_batch_and_improve(self):
        manifest = os.environ.get("LOCK_V17_REAL_PACKAGE_MANIFEST")
        config = os.environ.get("LOCK_V17_REAL_ADAPTER_CONFIG")
        params_json = os.environ.get("LOCK_V17_REAL_BUSINESS_PARAMS_JSON")
        if not manifest or not config or not params_json:
            self.skipTest(
                "最终含派生字段的V17冻结包尚未提供；设置LOCK_V17_REAL_PACKAGE_MANIFEST、"
                "LOCK_V17_REAL_ADAPTER_CONFIG和LOCK_V17_REAL_BUSINESS_PARAMS_JSON后执行真实smoke"
            )
        params = json.loads(params_json)
        backend = backend_from_package(manifest, config)
        self.assertIsInstance(backend, LockV17Backend)
        schema = backend.schema()
        derived_names = [item["field_name"] for item in schema["derived_features"]]
        public_names = [item["field_name"] for item in schema["fields"]]
        self.assertTrue(derived_names)
        self.assertFalse(set(derived_names) & set(public_names))
        self.assertTrue(all("reference_values" not in item for item in schema["protocol_profiles"]))
        evaluation = backend.evaluate(params)
        self.assertTrue(math.isfinite(float(evaluation["capability_score"])))
        self.assertFalse(evaluation["physical_feasibility_evaluated"])
        service = EffectivenessService(backend)
        batch = service.handle_post("/api/v1/evaluate/batch", {"items": [{"parameters": params}]})
        self.assertEqual(batch["count"], 1)
        if schema["capabilities"]["counterfactual_improvement"]:
            improved = backend.improve(params)
            recommended = improved["improvement_plan"].get("recommended_parameters") or {}
            self.assertFalse(set(derived_names) & set(recommended))


if __name__ == "__main__":
    unittest.main()
