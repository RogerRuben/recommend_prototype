# -*- coding: utf-8 -*-
"""Exceptional Lock V17 backend, contained entirely inside service :18102."""
from __future__ import print_function

import copy
import hashlib
import json
import math
import sys
from pathlib import Path

from services.effectiveness_service.lock_v17_adapter import LockV17InputAdapter


PACKAGE_FORMAT = "lock-product-reuse-runtime-package-17.0"
MODEL_FORMAT = "lock-product-reuse-model-17.0"


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_digest(value):
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _number(value, default=None):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _activate_source(source_root):
    source_root = Path(source_root).resolve()
    source_text = str(source_root).lower()
    if str(source_root) in sys.path:
        sys.path.remove(str(source_root))
    sys.path.insert(0, str(source_root))
    names = (
        "frozen_lock_model",
        "lock_utility_model",
        "preference_models",
        "project_excel",
    )
    for name in names:
        loaded = sys.modules.get(name)
        loaded_path = str(getattr(loaded, "__file__", "") or "").lower()
        if loaded is not None and not loaded_path.startswith(source_text):
            sys.modules.pop(name, None)


class LockV17Backend(object):
    """Read a frozen Lock V17 package and expose the standard service contract."""

    name = "lock_v17_frozen_runtime"

    def __init__(self, package_root, manifest, adapter_config):
        self.package_root = Path(package_root).resolve()
        self.manifest = copy.deepcopy(manifest or {})
        if self.manifest.get("format_version") != PACKAGE_FORMAT:
            raise RuntimeError("Lock V17运行包格式无效")
        self.source_root = self.package_root / self.manifest.get("source_root", "source")
        model_rel = self.manifest.get("model")
        if not model_rel:
            raise RuntimeError("Lock V17运行包未声明模型文件")
        self.model_path = self.package_root / model_rel
        if not self.model_path.is_file():
            raise RuntimeError("Lock V17冻结模型不存在: %s" % self.model_path)
        self._verify_files()
        try:
            self.model = json.loads(self.model_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError("Lock V17冻结模型不是有效JSON: %s" % exc)
        self._verify_model()
        required = (
            "frozen_lock_model.py",
            "lock_utility_model.py",
            "preference_models.py",
            "project_excel.py",
        )
        declared_files = set(
            str(item.get("path") or "").replace("\\", "/")
            for item in self.manifest.get("files") or []
        )
        required_manifest_paths = set(
            [str(model_rel).replace("\\", "/")]
            + [
                "%s/%s" % (
                    str(self.manifest.get("source_root", "source")).strip("/\\"),
                    name,
                )
                for name in required
            ]
        )
        undeclared = sorted(required_manifest_paths - declared_files)
        if undeclared:
            raise RuntimeError(
                "Lock V17运行包关键文件未纳入SHA-256清单: %s" % "、".join(undeclared)
            )
        missing = [name for name in required if not (self.source_root / name).is_file()]
        if missing:
            raise RuntimeError("Lock V17冻结运行源码不完整: %s" % "、".join(missing))
        _activate_source(self.source_root)
        try:
            from frozen_lock_model import FrozenLockReuseRuntime
            self.runtime = FrozenLockReuseRuntime(self.model_path)
        except Exception as exc:
            raise RuntimeError("Lock V17冻结运行时加载失败: %s" % exc)
        self.adapter = LockV17InputAdapter.from_file(adapter_config, self.model.get("schema") or {})
        project = self.model.get("project") or {}
        self.product_code = str(project.get("product_code") or "LOCK_V17")
        self.product_name = str(project.get("project_name") or "锁成品V17")
        self.model_version = str(self.model.get("model_version") or self.manifest.get("model_version") or "")
        self.algorithm_version = str(self.model.get("algorithm_version") or "V17")
        self.profile_version = int(self.model.get("profile_version") or 17)
        self.state_sha256 = str(self.model.get("model_digest"))
        self.protocols = {}
        for item in self.model.get("evaluation_baselines") or []:
            profile_id = str(item.get("profile_id") or "")
            if profile_id:
                self.protocols[profile_id] = copy.deepcopy(item)
        baseline = self.model.get("baseline") or {}
        baseline_id = str(baseline.get("profile_id") or "")
        if baseline_id and baseline_id not in self.protocols:
            self.protocols[baseline_id] = copy.deepcopy(baseline)
        if not self.protocols:
            raise RuntimeError("Lock V17冻结模型没有可用评价基准")
        self.default_profile_id = baseline_id or next(iter(self.protocols))
        self.improvement_config = copy.deepcopy(
            (self.adapter.config.get("improvement") or {})
        )
        physical = self.adapter.config.get("physical_compatibility") or {}
        self.feasibility_placeholder = float(physical.get("probability_placeholder", 0.65))
        if not math.isclose(self.feasibility_placeholder, 0.65, abs_tol=1e-12):
            raise RuntimeError("Lock V17物理可行性兼容占位必须为0.65")

    def _verify_files(self):
        for item in self.manifest.get("files") or []:
            relative = item.get("path")
            expected = item.get("sha256")
            if not relative or not expected:
                raise RuntimeError("Lock V17运行包文件清单不完整")
            path = (self.package_root / relative).resolve()
            try:
                path.relative_to(self.package_root)
            except ValueError:
                raise RuntimeError("Lock V17运行包包含越界文件路径: %s" % relative)
            if not path.is_file() or _sha(path) != str(expected):
                raise RuntimeError("Lock V17运行包文件校验失败: %s" % relative)

    def _verify_model(self):
        if self.model.get("model_format") != MODEL_FORMAT:
            raise RuntimeError("Lock V17冻结模型格式无效")
        declared = str(self.model.get("model_digest") or "")
        if not declared:
            raise RuntimeError("Lock V17冻结模型缺少内容摘要")
        core = copy.deepcopy(self.model)
        core.pop("model_digest", None)
        core.pop("model_version", None)
        core.pop("frozen_at", None)
        if _canonical_digest(core) != declared:
            raise RuntimeError("Lock V17冻结模型内容摘要校验失败")
        if str(self.manifest.get("model_digest") or "") != declared:
            raise RuntimeError("Lock V17运行包与冻结模型摘要不一致")
        manifest_version = str(self.manifest.get("model_version") or "")
        model_version = str(self.model.get("model_version") or "")
        if not manifest_version or manifest_version != model_version:
            raise RuntimeError("Lock V17运行包与冻结模型版本不一致")

    def _protocol_metadata(self, item):
        params = copy.deepcopy(item.get("params") or {})
        payload = {
            "profile_id": item.get("profile_id"),
            "profile_name": item.get("profile_name"),
            "reference_values": params,
        }
        return {
            "profile_id": str(item.get("profile_id") or ""),
            "profile_name": str(item.get("profile_name") or item.get("profile_id") or ""),
            "reference_score": float(item.get("score", 100.0)),
            "reference_digest": _canonical_digest(payload),
            "mode": "packaged_profile_selected_per_request",
        }

    def _resolve_protocol(self, target_protocol):
        if target_protocol in (None, ""):
            item = self.protocols[self.default_profile_id]
            return self.default_profile_id, self._protocol_metadata(item)
        if isinstance(target_protocol, str):
            profile_id = target_protocol
            supplied = None
        elif isinstance(target_protocol, dict):
            profile_id = str(target_protocol.get("profile_id") or target_protocol.get("id") or "")
            supplied = target_protocol.get("reference_values")
            if supplied is None:
                supplied = target_protocol.get("values")
        else:
            raise ValueError("Lock V17 target_protocol必须是冻结基准编号或对象")
        if profile_id not in self.protocols:
            raise ValueError("Lock V17冻结模型中不存在评价基准: %s" % profile_id)
        item = self.protocols[profile_id]
        if supplied is not None:
            raise ValueError(
                "Lock V17公共协议只接受冻结运行包中的profile_id，"
                "不接受或公开内部reference_values"
            )
        return profile_id, self._protocol_metadata(item)

    def schema(self):
        profiles = [self._protocol_metadata(item) for item in self.protocols.values()]
        return {
            "product_code": self.product_code,
            "product_name": self.product_name,
            "model_version": self.model_version,
            "backend": self.name,
            "fields": self.adapter.public_fields(),
            "derived_features": [self.adapter.derived_feature_schema()],
            "model_digest": self.state_sha256,
            "state_sha256": self.state_sha256,
            "profile_version": self.profile_version,
            "algorithm_version": self.algorithm_version,
            "active_protocol": self._protocol_metadata(self.protocols[self.default_profile_id]),
            "protocol_profiles": profiles,
            "target_protocol_contract": {
                "supported": True,
                "accepted": ["profile_id"],
                "dynamic_reference_values": False,
                "changes_learning_state": False,
            },
            "capabilities": {
                "dynamic_target_protocol": True,
                "counterfactual_improvement": bool(self.improvement_config.get("enabled", True)),
                "physical_feasibility": False,
            },
            "evaluation_level": "lock_v17_reuse_effectiveness_without_physical_feasibility",
            "physical_feasibility_evaluated": False,
            "privacy": copy.deepcopy(self.model.get("privacy") or {}),
            "training_summary": copy.deepcopy(self.model.get("training_summary") or {}),
        }

    def _contributors(self, raw):
        output = []
        for item in raw.get("loss_contributions") or []:
            loss = _number(item.get("loss_points"), 0.0)
            output.append({
                "parameter_id": item.get("attribute_key"),
                "parameter_label": item.get("attribute_label"),
                "unit": item.get("unit"),
                "weight": item.get("attribute_weight"),
                "score_delta": -abs(loss),
                "loss_points": abs(loss),
                "deterioration": item.get("deterioration"),
                "explanation": "相对当前评价基准扣减%.3f分" % abs(loss),
            })
        output.sort(key=lambda item: item["loss_points"], reverse=True)
        return output

    def evaluate(self, params, target_protocol=None):
        profile_id, protocol = self._resolve_protocol(target_protocol)
        model_params, diagnostics = self.adapter.prepare(params)
        raw = self.runtime.evaluate(model_params, profile_id=profile_id)
        score = _number(raw.get("effectiveness_score"))
        if score is None:
            raise RuntimeError("Lock V17运行时没有返回有效effectiveness_score")
        interval = raw.get("effectiveness_interval")
        values = [_number(value) for value in (interval or [])]
        if len(values) >= 2 and values[0] is not None and values[1] is not None:
            protocol_interval = [values[0], values[1]]
            conservative = values[0]
        else:
            protocol_interval = [score, score]
            conservative = score
        width = abs(protocol_interval[1] - protocol_interval[0])
        warning = {
            "code": "lock_v17_physical_feasibility_not_evaluated",
            "message": "Lock V17不评价物理可行性；0.65仅为当前推荐接口兼容占位，不得解释为模型物理可行概率。",
            "advisory": True,
            "source": "lock_v17_backend",
        }
        public_names = set(field["field_name"] for field in self.adapter.public_fields())
        canonical_business = {
            key: copy.deepcopy(value) for key, value in params.items()
            if key in public_names
        }
        return {
            "parameters": canonical_business,
            "effectiveness_score": round(score, 3),
            "capability_score": round(score, 3),
            "conservative_capability_score": round(conservative, 3),
            "protocol_score_interval": [round(value, 3) for value in protocol_interval],
            "support_at_80": None,
            "support_at_100": None,
            "robust_model_count": int(raw.get("robust_model_count") or 1),
            "robust_unique_model_count": int(raw.get("robust_model_count") or 1),
            "robust_conclusion": "lock_v17_frozen_reuse_assessment",
            "robust_conclusion_label": raw.get("overall_reuse_label"),
            "score_uncertainty_width": round(width, 3),
            "feasibility_probability": self.feasibility_placeholder,
            "feasibility_status": "not_evaluated_lock_v17",
            "physical_feasibility_evaluated": False,
            "physical_gate": {
                "passed": True,
                "decision": "pass_not_evaluated",
                "probability": self.feasibility_placeholder,
                "probability_threshold": 0.65,
                "feasibility_status": "not_evaluated_lock_v17",
                "gate_policy": "lock_v17_not_evaluated_compatibility",
                "not_evaluated": True,
                "hard_violations": [],
                "mature_boundary_violations": [],
                "severe_coupling_mismatches": [],
            },
            "effectiveness_source": raw.get("score_source") or "lock_v17_frozen_runtime",
            "effectiveness_confidence": "frozen_v17_model",
            "feasibility_confidence": "not_evaluated",
            "requirement_assessment": None,
            "uta_score": score,
            "bt_score": None,
            "contours": {},
            "coupling_assessments": [],
            "risk_contributors": [],
            "hard_violations": [],
            "learned_boundary_violations": [],
            "experience_extrapolations": [warning],
            "capability_contributors": self._contributors(raw),
            "protocol": protocol,
            "derived_features": diagnostics["derived_features"],
            "reuse_assessment": {
                "overall_reuse_status": raw.get("overall_reuse_status"),
                "overall_reuse_label": raw.get("overall_reuse_label"),
                "combined_reuse_threshold": raw.get("combined_reuse_threshold"),
                "single_attribute_violations": copy.deepcopy(raw.get("single_attribute_violations") or []),
                "uncertain_attributes": copy.deepcopy(raw.get("uncertain_attributes") or []),
                "attributes": copy.deepcopy(raw.get("attributes") or []),
                "loss_contributions": copy.deepcopy(raw.get("loss_contributions") or []),
                "migration": copy.deepcopy(raw.get("migration") or {}),
                "conclusion": raw.get("conclusion"),
            },
            "raw_evaluation": raw,
        }

    def _candidate_values(self, field, current, ratios):
        dtype = str(field.get("dtype") or "number").lower()
        allowed = list(field.get("allowed_values") or [])
        if dtype in ("enum", "categorical", "category"):
            return [value for value in allowed if value != current]
        if dtype in ("boolean", "bool"):
            return [value for value in (allowed or [0, 1]) if value != current]
        value = _number(current)
        lo = _number(field.get("generation_min"))
        hi = _number(field.get("generation_max"))
        if value is None or lo is None or hi is None or hi < lo:
            return []
        span = hi - lo
        values = [lo, hi]
        for ratio in ratios:
            step = span * float(ratio)
            values.extend([value - step, value + step])
        result = []
        for candidate in values:
            candidate = min(hi, max(lo, candidate))
            if dtype in ("integer", "int", "ip_grade"):
                candidate = int(round(candidate))
            else:
                precision = int(field.get("precision", 6) or 6)
                candidate = round(candidate, precision)
            if candidate != current and candidate not in result:
                result.append(candidate)
        return result

    def improve(self, params, target_protocol=None):
        if not bool(self.improvement_config.get("enabled", True)):
            raise ValueError("Lock V17局部改进功能未启用")
        current = self.evaluate(params, target_protocol=target_protocol)
        diagnostics = current.get("derived_features") or {}
        derived = diagnostics.get(self.adapter.target_field) or {}
        locked = set()
        if bool(self.improvement_config.get("lock_absent_derived_groups", True)) and (
            derived.get("x1_status") == "absent" or derived.get("x2_status") == "absent"
        ):
            locked.update(self.adapter.source_fields)
        fields = [
            field for field in self.adapter.public_fields()
            if field.get("participates_generation", True)
            and field.get("source", "product_parameter") == "product_parameter"
            and field.get("field_name") not in locked
        ]
        maximum = min(300, int(self.improvement_config.get("max_candidates", 120)))
        rounds = min(2, max(1, int(self.improvement_config.get("rounds", 2))))
        ratio_sets = [
            self.improvement_config.get("round1_step_ratios") or [0.05, 0.10, 0.20],
            self.improvement_config.get("round2_step_ratios") or [0.025, 0.05],
        ]
        original = copy.deepcopy(params)
        best_params = copy.deepcopy(params)
        best_evaluation = current
        attempted = 0

        def quality(evaluation, candidate):
            score = _number(evaluation.get("conservative_capability_score"), -math.inf)
            changed = [key for key in candidate if candidate.get(key) != original.get(key)]
            movement = 0.0
            by_name = dict((item["field_name"], item) for item in fields)
            for key in changed:
                field = by_name.get(key) or {}
                lo = _number(field.get("generation_min"))
                hi = _number(field.get("generation_max"))
                before = _number(original.get(key))
                after = _number(candidate.get(key))
                if None not in (lo, hi, before, after) and hi > lo:
                    movement += abs(after - before) / (hi - lo)
                else:
                    movement += 1.0
            return (score, -len(changed), -movement)

        for round_index in range(rounds):
            center = copy.deepcopy(best_params)
            round_best = None
            round_best_eval = None
            for field in fields:
                key = field.get("field_name")
                if key not in center or attempted >= maximum:
                    continue
                for value in self._candidate_values(field, center.get(key), ratio_sets[round_index]):
                    if attempted >= maximum:
                        break
                    candidate = copy.deepcopy(center)
                    candidate[key] = value
                    attempted += 1
                    try:
                        evaluated = self.evaluate(candidate, target_protocol=target_protocol)
                    except (ValueError, RuntimeError):
                        continue
                    if round_best is None or quality(evaluated, candidate) > quality(round_best_eval, round_best):
                        round_best, round_best_eval = candidate, evaluated
            if round_best is not None and quality(round_best_eval, round_best) > quality(best_evaluation, best_params):
                best_params, best_evaluation = round_best, round_best_eval

        current_score = _number(current.get("conservative_capability_score"), -math.inf)
        best_score = _number(best_evaluation.get("conservative_capability_score"), -math.inf)
        min_gain = float(self.improvement_config.get("min_gain", 0.1))
        changed = [
            key for key in best_params
            if key != self.adapter.target_field and best_params.get(key) != original.get(key)
        ]
        if best_score < current_score + min_gain or not changed:
            plan = {
                "status": "no_better_local_candidate",
                "method": "lock_v17_service_local_neighborhood",
                "recommended_parameters": {},
                "changed_fields": [],
                "estimated_capability_gain": 0.0,
                "evaluated_candidate_count": attempted,
            }
        else:
            plan = {
                "status": "improved",
                "method": "lock_v17_service_local_neighborhood",
                "recommended_parameters": dict((key, best_params[key]) for key in changed),
                "changed_fields": changed,
                "estimated_capability_gain": round(best_score - current_score, 3),
                "evaluated_candidate_count": attempted,
            }
        return {
            "parameters": current.get("parameters") or {},
            "protocol": current.get("protocol"),
            "current_evaluation": current,
            "improvement_plan": plan,
        }


__all__ = ["LockV17Backend", "MODEL_FORMAT", "PACKAGE_FORMAT"]
