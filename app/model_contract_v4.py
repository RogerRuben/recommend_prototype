# -*- coding: utf-8 -*-
"""Recommendation contract 4.0 validator and pure-JSON inference runtime."""
import json, math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Union, Optional

CONTRACT_VERSION = "4.0"

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v)))

def sigmoid(v: float) -> float:
    if v >= 35: return 1.0
    if v <= -35: return 0.0
    return 1.0 / (1.0 + math.exp(-v))

def load_bundle(path: Union[str, Path]) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def validate_bundle(bundle: Dict[str, Any], expected_kind: Optional[str] = None) -> List[str]:
    errors: List[str] = []
    for key in ("recommendation_contract_version", "model_kind", "product_code", "model_version", "feature_schema", "model_input_bindings"):
        if key not in bundle:
            errors.append("缺少字段: %s" % key)
    if bundle.get("recommendation_contract_version") != CONTRACT_VERSION:
        errors.append("契约版本应为%s" % CONTRACT_VERSION)
    kind = bundle.get("model_kind")
    if kind not in {"effectiveness", "price"}:
        errors.append("model_kind必须为effectiveness或price")
    if expected_kind and kind != expected_kind:
        errors.append("模型类型应为%s" % expected_kind)
    if not str(bundle.get("product_code") or "").strip():
        errors.append("product_code不能为空")
    if not str(bundle.get("model_version") or "").strip():
        errors.append("model_version不能为空")

    schema = bundle.get("feature_schema") or []
    bindings = bundle.get("model_input_bindings") or []
    if not isinstance(schema, list) or not schema:
        errors.append("feature_schema不能为空")
        schema = []
    if not isinstance(bindings, list) or not bindings:
        errors.append("model_input_bindings不能为空")
        bindings = []
    names = [str(x.get("field_name") or "") for x in schema]
    if any(not n for n in names):
        errors.append("feature_schema存在空field_name")
    if len(names) != len(set(names)):
        errors.append("feature_schema字段重复")
    schema_map = {str(x.get("field_name") or ""): x for x in schema if x.get("field_name")}
    valid_dtypes = {"number", "integer", "ip_grade", "boolean", "enum", "text"}
    for item in schema:
        name = str(item.get("field_name") or "")
        dtype = str(item.get("dtype") or "")
        if dtype not in valid_dtypes:
            errors.append("字段%s的dtype无效: %s" % (name, dtype))
        if kind == "price" and dtype not in {"number", "integer", "ip_grade"}:
            errors.append("当前价格契约只支持数值型特征: %s" % name)
        if kind == "price":
            for key in ("training_min", "training_max", "training_mean"):
                if item.get(key) is None:
                    errors.append("价格字段%s缺少%s" % (name, key))
            try:
                if float(item.get("training_max")) < float(item.get("training_min")):
                    errors.append("价格字段%s训练范围上下限颠倒" % name)
            except (TypeError, ValueError):
                errors.append("价格字段%s训练范围不是数值" % name)
        elif dtype in {"number", "integer", "ip_grade"}:
            for key in ("generation_min", "generation_max"):
                if item.get(key) is None:
                    errors.append("效能字段%s缺少%s" % (name, key))
            try:
                if float(item.get("generation_max")) < float(item.get("generation_min")):
                    errors.append("效能字段%s生成范围上下限颠倒" % name)
            except (TypeError, ValueError):
                errors.append("效能字段%s生成范围不是数值" % name)

    enabled_bindings = [x for x in bindings if x.get("enabled", True)]
    binding_names = [str(x.get("field_name") or "") for x in enabled_bindings]
    if any(not x for x in binding_names):
        errors.append("model_input_bindings存在空field_name")
    if len(binding_names) != len(set(binding_names)):
        errors.append("同一模型内启用的绑定字段重复")
    missing = sorted(set(binding_names) - set(names))
    if missing:
        errors.append("绑定字段未出现在feature_schema: " + ",".join(missing))
    for item in enabled_bindings:
        field_name = str(item.get("field_name") or "")
        if item.get("model_kind") != kind:
            errors.append("绑定%s的model_kind不一致" % field_name)
        if item.get("source_type") not in {"product_parameter", "context", "derived", "constant"}:
            errors.append("绑定%s的source_type无效" % field_name)
        if item.get("missing_policy") not in {"reject", "training_mean", "default", "constant", "zero"}:
            errors.append("绑定%s的missing_policy无效" % field_name)
        schema_item = schema_map.get(field_name) or {}
        if schema_item and str(item.get("dtype") or "") != str(schema_item.get("dtype") or ""):
            errors.append("字段%s的schema与binding dtype不一致" % field_name)
        if schema_item and str(item.get("unit") or "") != str(schema_item.get("unit") or ""):
            errors.append("字段%s的schema与binding unit不一致" % field_name)
        policy = item.get("missing_policy")
        if policy == "training_mean" and item.get("training_mean") is None:
            errors.append("字段%s声明training_mean但未保存训练均值" % field_name)
        if policy in {"default", "constant"} and item.get("configured_value") is None:
            errors.append("字段%s声明%s但未保存configured_value" % (field_name, policy))

    if kind == "price":
        preprocessing = bundle.get("preprocessing") or {}
        ensemble = bundle.get("ensemble") or {}
        if preprocessing.get("type") != "minmax":
            errors.append("价格模型缺少minmax预处理")
        order = list(preprocessing.get("feature_order") or [])
        lo = list(preprocessing.get("min") or [])
        hi = list(preprocessing.get("max") or [])
        if len(order) != len(names) or set(order) != set(names):
            errors.append("价格模型feature_order必须与feature_schema完全一致")
        if len(lo) != len(order) or len(hi) != len(order):
            errors.append("价格模型min/max长度与feature_order不一致")
        for i, field_name in enumerate(order):
            if i >= len(lo) or i >= len(hi):
                break
            try:
                if float(hi[i]) < float(lo[i]):
                    errors.append("价格字段%s的预处理上下限颠倒" % field_name)
            except (TypeError, ValueError):
                errors.append("价格字段%s的预处理范围不是数值" % field_name)
        members = ensemble.get("members") or []
        if not members:
            errors.append("价格模型缺少ensemble.members")
        total_weight = 0.0
        for member in members:
            coefficients = member.get("coefficients") or []
            if len(coefficients) != len(order):
                errors.append("价格模型成员%s的系数数量错误" % (member.get("name") or "未命名"))
            try:
                weight = float(member.get("weight", 1.0))
                if weight < 0:
                    errors.append("价格模型成员权重不能为负")
                total_weight += weight
                float(member.get("intercept"))
                [float(x) for x in coefficients]
            except (TypeError, ValueError):
                errors.append("价格模型成员包含非数值参数")
        if members and total_weight <= 0:
            errors.append("价格模型集成权重之和必须大于0")
        if bundle.get("target_transform") != "log":
            errors.append("价格模型target_transform应为log")
        calibration = bundle.get("residual_calibration") or {}
        if calibration.get("log_residual_lower") is None or calibration.get("log_residual_upper") is None:
            errors.append("价格模型缺少残差区间校准")
    elif kind == "effectiveness":
        if "coupling_models" not in bundle:
            errors.append("效能模型缺少coupling_models")
        if "feasibility_model" not in bundle:
            errors.append("效能模型缺少feasibility_model")
        if "preference_uta" not in bundle and "preference_bt" not in bundle:
            errors.append("效能模型缺少UTA或BT模型")
        for model in bundle.get("coupling_models") or []:
            target = str(model.get("target_key") or "")
            if target not in schema_map:
                errors.append("耦合模型目标字段不存在: %s" % target)
            source_ranges = model.get("source_ranges") or {}
            for effect in model.get("source_effects") or []:
                key = str(effect.get("key") or "")
                if key not in schema_map:
                    errors.append("耦合模型来源字段不存在: %s" % key)
                if key not in source_ranges:
                    errors.append("耦合模型%s缺少来源范围%s" % (target, key))
            for key in ("intercept", "lower_offset", "upper_offset", "target_min", "target_max"):
                if model.get(key) is None:
                    errors.append("耦合模型%s缺少%s" % (target, key))
        samples = bundle.get("historical_samples") or []
        if not samples:
            errors.append("效能模型缺少historical_samples，无法进行经验距离和安装冒烟测试")
        elif enabled_bindings:
            required_fields = {x["field_name"] for x in enabled_bindings if x.get("required", True) and x.get("missing_policy") == "reject"}
            absent = sorted(required_fields - set(samples[0]))
            if absent:
                errors.append("效能历史样本缺少必填字段: " + ",".join(absent))
    return errors

def _resolve_inputs(bundle: Dict[str, Any], params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], List[str]]:
    context = context or {}
    values: Dict[str, Any] = {}
    warnings: List[str] = []
    for b in bundle.get("model_input_bindings", []):
        if not b.get("enabled", True): continue
        name = b["field_name"]
        source = b.get("source_type", "product_parameter")
        if source == "product_parameter": value = params.get(name)
        elif source == "context": value = context.get(name)
        elif source == "constant": value = b.get("configured_value")
        else: value = None
        if value is None or value == "":
            policy = b.get("missing_policy", "reject")
            if policy == "reject" and b.get("required", True): raise ValueError(f"模型必填字段缺失: {name}")
            if policy == "training_mean": value = b.get("training_mean")
            elif policy in {"default", "constant"}: value = b.get("configured_value")
            elif policy == "zero": value = 0
            if value is None and b.get("required", True): raise ValueError(f"字段{name}缺失且无可用补全值")
            warnings.append(f"{name}使用{policy}补全")
        values[name] = value
    return values, warnings

def evaluate_price(bundle: Dict[str, Any], params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    errors = validate_bundle(bundle, "price")
    if errors: raise ValueError("; ".join(errors))
    values, warnings = _resolve_inputs(bundle, params, context)
    order = bundle["preprocessing"]["feature_order"]
    lo = bundle["preprocessing"]["min"]
    hi = bundle["preprocessing"]["max"]
    x, domain = [], []
    for i, name in enumerate(order):
        v = float(values[name]); span = max(float(hi[i]) - float(lo[i]), 1e-12)
        x.append((v - float(lo[i])) / span)
        if v < float(lo[i]) or v > float(hi[i]): domain.append(name)
    preds = []
    for member in bundle["ensemble"]["members"]:
        pred = float(member["intercept"]) + sum(float(c) * z for c, z in zip(member["coefficients"], x))
        preds.append(pred)
    weights = [float(m.get("weight", 1.0)) for m in bundle["ensemble"]["members"]]
    total = sum(weights) or 1.0
    log_pred = sum(w*p for w,p in zip(weights,preds))/total
    price = math.exp(log_pred)
    cal = bundle.get("residual_calibration") or {}
    qlo = float(cal.get("log_residual_lower", 0.0)); qhi = float(cal.get("log_residual_upper", 0.0))
    inflation = 1.0 + 0.12 * len(domain)
    center = log_pred
    lower = math.exp(center + qlo * inflation); upper = math.exp(center + qhi * inflation)
    return {
        "predicted_price_wan": round(price, 6),
        "price_interval_wan": [round(lower, 6), round(upper, 6)],
        "price_model_version": bundle["model_version"],
        "price_domain_warnings": domain,
        "price_input_warnings": warnings,
        "price_confidence": "低" if domain else "中" if (upper-lower)/max(price,1e-9) > 0.35 else "高",
    }

def _band(model: Dict[str, Any], params: Dict[str, Any]) -> Tuple[float,float,float]:
    pred_n = float(model["intercept"])
    for e in model.get("source_effects", []):
        lo, hi = model["source_ranges"][e["key"]]
        z = clamp((float(params[e["key"]])-lo)/max(hi-lo,1e-12),0,1)
        pred_n += float(e["normalized_coefficient"]) * z
    tmin,tmax=float(model["target_min"]),float(model["target_max"])
    den=lambda z:tmin+z*(tmax-tmin)
    pred=den(pred_n); lower=clamp(den(pred_n+float(model["lower_offset"])),tmin,tmax); upper=clamp(den(pred_n+float(model["upper_offset"])),tmin,tmax)
    lower,upper=min(lower,upper),max(lower,upper)
    if upper-lower<1e-9:
        pad=0.02*(tmax-tmin); lower=clamp(lower-pad,tmin,tmax); upper=clamp(upper+pad,tmin,tmax)
    return pred,lower,upper

def _nearest_distance(bundle: Dict[str, Any], params: Dict[str, Any]) -> float:
    schemas={x["field_name"]:x for x in bundle["feature_schema"]}
    dists=[]
    for sample in bundle.get("historical_samples", []):
        vals=[]
        for k,s in schemas.items():
            if s.get("dtype") not in {"number","integer","ip_grade"} or k not in params or k not in sample: continue
            span=max(float(s.get("generation_max",1))-float(s.get("generation_min",0)),1e-12)
            vals.append((float(params[k])-float(sample[k]))/span)
        if vals: dists.append(math.sqrt(sum(v*v for v in vals)/len(vals)))
    return min(dists) if dists else 0.0

def _uta_score(bundle: Dict[str, Any], params: Dict[str, Any]) -> float:
    uta=bundle.get("preference_uta") or {}
    curves=uta.get("curves") or []
    if curves:
        score=0.0
        for c in curves:
            k=c["key"]; value=float(params[k])
            points=c.get("points") or []
            if points:
                knots=[float(p["raw_value"]) for p in points]
                utilities=[float(p["utility"]) for p in points]
            else:
                knots=[float(x) for x in (c.get("knots") or [])]
                utilities=[float(x) for x in (c.get("cumulative_utility") or [])]
            if not knots or not utilities: continue
            pairs=sorted(zip(knots,utilities),key=lambda x:x[0]); knots=[x[0] for x in pairs]; utilities=[x[1] for x in pairs]
            if value<=knots[0]: u=utilities[0]
            elif value>=knots[-1]: u=utilities[-1]
            else:
                u=utilities[-1]
                for a,b,ua,ub in zip(knots,knots[1:],utilities,utilities[1:]):
                    if a<=value<=b:
                        u=ua+(ub-ua)*(value-a)/max(b-a,1e-12); break
            score+=float(u)
        return 100.0*score
    bt=bundle.get("preference_bt") or {}
    weights=bt.get("attribute_weights") or {}
    schemas={x["field_name"]:x for x in bundle["feature_schema"]}
    total=0.0
    for k,w in weights.items():
        s=schemas[k]; lo=float(s.get("generation_min",0)); hi=float(s.get("generation_max",1)); z=clamp((float(params[k])-lo)/max(hi-lo,1e-12),0,1)
        if s.get("preference_direction")=="lower_better": z=1-z
        total+=float(w)*z
    return 100.0*total


def _active_requirement_profile(bundle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    profiles = list(bundle.get("requirement_profiles") or [])
    if not profiles:
        return None
    active = bundle.get("active_requirement_profile_id")
    if active:
        for profile in profiles:
            if str(profile.get("profile_id")) == str(active):
                return profile
    return profiles[0]


def _requirement_reference(req: Dict[str, Any]) -> Optional[float]:
    if req.get("target_value") is not None:
        return float(req["target_value"])
    kind = req.get("requirement_type")
    if kind == "at_least" and req.get("minimum") is not None:
        return float(req["minimum"])
    if kind == "at_most" and req.get("maximum") is not None:
        return float(req["maximum"])
    if req.get("minimum") is not None and req.get("maximum") is not None:
        return 0.5 * (float(req["minimum"]) + float(req["maximum"]))
    return None


def _requirement_score(bundle: Dict[str, Any], values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    profile = _active_requirement_profile(bundle)
    if profile is None:
        return None
    schemas = {x["field_name"]: x for x in bundle.get("feature_schema") or []}
    requirements = [r for r in profile.get("requirements") or [] if r.get("attribute_key") in schemas]
    if not requirements:
        return None
    # Preserve the source application's design-stage prior: stage 1/2/3 = 50/30/20.
    default_shares = {1: 0.50, 2: 0.30, 3: 0.20}
    stage_members: Dict[int, List[str]] = {}
    for req in requirements:
        key = req["attribute_key"]
        stage = int(schemas[key].get("design_stage") or 1)
        stage_members.setdefault(stage, []).append(key)
    active_total = sum(default_shares.get(stage, 0.0) for stage in stage_members)
    if active_total <= 1e-12:
        weights = {req["attribute_key"]: 1.0 / len(requirements) for req in requirements}
        stage_shares = {}
    else:
        stage_shares = {stage: default_shares.get(stage, 0.0) / active_total for stage in stage_members}
        weights = {}
        for stage, members in stage_members.items():
            for key in members:
                weights[key] = stage_shares[stage] / len(members)
    # If generic learned attribute weights were exported, reproduce the original
    # RequirementEvaluator behavior: use them as non-negative weights and renormalize.
    learned = ((bundle.get("preference_uta") or {}).get("attribute_weights") or
               (bundle.get("preference_bt") or {}).get("attribute_weights") or {})
    if learned:
        combined = {key: max(0.0, float(learned.get(key, weights.get(key, 0.0)))) for key in weights}
        total = sum(combined.values())
        if total > 1e-12:
            weights = {key: value / total for key, value in combined.items()}
    assessments = []
    total_score = 0.0
    hard_gaps = []
    for req in requirements:
        key = req["attribute_key"]
        schema = schemas[key]
        reference = _requirement_reference(req)
        try:
            value = float(values.get(key))
        except (TypeError, ValueError):
            value = None
        relative = 0.0
        met = False
        gap = None
        better = False
        if value is not None and reference is not None:
            lo = float(schema.get("generation_min", 0.0))
            hi = float(schema.get("generation_max", 1.0))
            span = max(hi - lo, 1e-12)
            kind = req.get("requirement_type")
            if kind in {"higher_better", "at_least"}:
                relative = clamp(1.0 + (value - reference) / span, 0.0, 2.0)
                met = value >= reference
                gap = max(0.0, reference - value)
                better = value > reference
            elif kind in {"lower_better", "at_most"}:
                relative = clamp(1.0 + (reference - value) / span, 0.0, 2.0)
                met = value <= reference
                gap = max(0.0, value - reference)
                better = value < reference
            else:
                def linear(v: float, zero: float, one: float) -> float:
                    width = one - zero
                    return 1.0 if abs(width) <= 1e-12 and v == one else 0.0 if abs(width) <= 1e-12 else clamp((v-zero)/width,0.0,1.0)
                relative = linear(value, lo, reference) if value <= reference else linear(value, hi, reference)
                tolerance = max(float(req.get("tolerance") or 0.0), 0.5 * (10.0 ** (-int(schema.get("precision") or 3))))
                gap = max(0.0, abs(value - reference) - tolerance)
                met = gap <= 0.0
        weight = float(weights.get(key, 0.0))
        weighted = relative * weight
        total_score += weighted
        hard_gap = bool(req.get("hard_requirement") and not met)
        if hard_gap:
            hard_gaps.append(schema.get("field_label") or key)
        assessments.append({
            "attribute_key": key,
            "attribute_label": schema.get("field_label") or key,
            "unit": schema.get("unit") or "",
            "value": value,
            "reference_value": reference,
            "requirement_type": req.get("requirement_type"),
            "relative_score_percent": round(relative * 100.0, 6),
            "weight": round(weight, 8),
            "weighted_score": round(weighted, 8),
            "met": met,
            "hard_requirement": bool(req.get("hard_requirement")),
            "hard_gap": hard_gap,
            "gap": gap,
            "better_than_reference": better,
            "design_stage": int(schema.get("design_stage") or 1),
        })
    coverage = clamp(total_score, 0.0, 2.0)
    direct = float(profile.get("direct_reuse_threshold", 0.95))
    improve = float(profile.get("improvement_threshold", 0.75))
    redesign = float(profile.get("redesign_threshold", 0.50))
    if coverage >= direct and not hard_gaps:
        decision = "direct_reuse"
    elif coverage >= improve:
        decision = "local_improvement"
    elif coverage >= redesign:
        decision = "major_improvement"
    else:
        decision = "redesign"
    return {
        "profile_id": profile.get("profile_id"),
        "profile_name": profile.get("profile_name"),
        "coverage": round(coverage, 8),
        "coverage_percent": round(coverage * 100.0, 6),
        "decision": decision,
        "hard_gap_count": len(hard_gaps),
        "hard_gaps": hard_gaps,
        "attributes": assessments,
        "stage_weight_share": stage_shares,
        "reference_score": 100.0,
        "weight_source": "learned_generic_preference_weights" if learned else "design_stage_prior_50_30_20",
    }

def evaluate_effectiveness(bundle: Dict[str, Any], params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    errors=validate_bundle(bundle,"effectiveness")
    if errors: raise ValueError("; ".join(errors))
    values,warnings=_resolve_inputs(bundle,params,context)
    schemas={x["field_name"]:x for x in bundle["feature_schema"]}
    features={"bias":1.0,"range_violation":0.0,"range_edge":0.0,"experience_distance":clamp(_nearest_distance(bundle,values)/0.45,0,1.5)}
    domain=[]
    for k,s in schemas.items():
        if s.get("dtype") not in {"number","integer","ip_grade"}: continue
        v=float(values[k]); gmin=float(s["generation_min"]); gmax=float(s["generation_max"]); fmin=float(s.get("feasible_min",gmin)); fmax=float(s.get("feasible_max",gmax)); span=max(gmax-gmin,1e-12)
        if v<gmin: features["range_violation"]=max(features["range_violation"],(gmin-v)/span); domain.append(k)
        elif v>gmax: features["range_violation"]=max(features["range_violation"],(v-gmax)/span); domain.append(k)
        if v<fmin: features["range_edge"]=max(features["range_edge"],clamp((fmin-v)/max(fmin-gmin,.08*span,1e-12),0,1.5))
        elif v>fmax: features["range_edge"]=max(features["range_edge"],clamp((v-fmax)/max(gmax-fmax,.08*span,1e-12),0,1.5))
        features[f"expert_boundary_{k}_low"]=0.0; features[f"expert_boundary_{k}_high"]=0.0
    contour=[]
    for m in bundle.get("coupling_models",[]):
        pred,lower,upper=_band(m,values); actual=float(values[m["target_key"]]); span=float(m["target_max"])-float(m["target_min"]); width=max(upper-lower,0.04*span,1e-9)
        features[f"coupling_{m['target_key']}_below"]=clamp((pred-actual)/width,0,1.5)
        features[f"coupling_{m['target_key']}_above"]=clamp((actual-pred)/width,0,1.5)
        inside=lower<=actual<=upper
        relative=min(actual-lower,upper-actual)/width if inside else -1.0
        features[f"coupling_{m['target_key']}_boundary"]=1.0 if inside and relative<0.12 else 0.0
        contour.append({"parameter_id":m["target_key"],"predicted":pred,"lower":lower,"upper":upper,"actual":actual,"outside":not inside})
    for target in {m.get("target_key") for m in bundle.get("coupling_models",[]) if m.get("target_key")}:
        features[f"frontier_{target}_low"]=0.0
        features[f"frontier_{target}_high"]=0.0
    for b in (bundle.get("feasibility_model") or {}).get("learned_boundaries",[]):
        k=b["attribute_key"]; v=float(values[k]); limit=float(b["boundary"]); s=schemas[k]; span=max(float(s["generation_max"])-float(s["generation_min"]),1e-12)
        dist=limit-v if b["side"]=="low" else v-limit
        if dist>0: features[f"expert_boundary_{k}_{b['side']}"]=clamp(.45+3*dist/span,0,1.5)*float(b.get("confidence",.5))*(1 if b.get("mature") else .55)
    weights=(bundle.get("feasibility_model") or {}).get("weights") or {}
    raw=sum(float(weights.get(k,0))*float(v) for k,v in features.items())
    feasibility=sigmoid(raw)
    generic_score=_uta_score(bundle,values)
    requirement_assessment=_requirement_score(bundle,values)
    if requirement_assessment is not None:
        score=float(requirement_assessment["coverage_percent"])
        effectiveness_source="protocol_relative_score"
    elif (bundle.get("preference_uta") or {}).get("curves"):
        score=generic_score
        effectiveness_source="uta"
    else:
        score=generic_score
        effectiveness_source="bt"
    return {
        "capability_score": round(score,6),
        "feasibility_probability": round(feasibility,8),
        "effectiveness_model_version": bundle["model_version"],
        "feasible_contours": contour,
        "effectiveness_domain_warnings": sorted(set(domain)),
        "effectiveness_input_warnings": warnings,
        "effectiveness_confidence": "低" if domain or feasibility<.4 else "中" if any(x["outside"] for x in contour) else "高",
        "effectiveness_source": effectiveness_source,
        "generic_preference_score": round(generic_score,6),
        "requirement_assessment": requirement_assessment,
        "capability_contributors": sorted(
            (requirement_assessment or {}).get("attributes", []),
            key=lambda item: float(item.get("weighted_score", 0.0)),
            reverse=True,
        )[:8],
        "risk_contributors": [],
        "hard_risk_reasons": list((requirement_assessment or {}).get("hard_gaps", [])),
    }

def evaluate_joint(effectiveness_bundle: Dict[str, Any], price_bundle: Dict[str, Any], params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if effectiveness_bundle.get("product_code") != price_bundle.get("product_code"):
        raise ValueError("价格与效能模型product_code不一致")
    e=evaluate_effectiveness(effectiveness_bundle,params,context); p=evaluate_price(price_bundle,params,context)
    price=max(float(p["predicted_price_wan"]),1e-12)
    return {**e,**p,"cost_effectiveness":round(float(e["capability_score"])/price,6)}
