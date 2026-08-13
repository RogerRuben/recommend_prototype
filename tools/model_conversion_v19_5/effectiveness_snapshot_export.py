# -*- coding: utf-8 -*-
"""Convert the delivered effectiveness Workbook + state JSON into recommendation contract 4.0."""
import argparse, hashlib, json, sys, tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Union, Optional


def _sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def _load_field_map(field_map):
    if field_map is None:
        return {}
    if isinstance(field_map, (str, Path)):
        raw = json.loads(Path(field_map).read_text(encoding="utf-8"))
    else:
        raw = dict(field_map)
    result = {}
    for old, value in raw.items():
        result[str(old)] = str(value.get("parameter_id") if isinstance(value, dict) else value)
    if len(set(result.values())) != len(result.values()):
        raise ValueError("字段映射后parameter_id重复")
    return result


def _remap_feature_name(name, mapping):
    value = str(name)
    for old, new in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        if value == old:
            return new
        value = value.replace("coupling_%s_" % old, "coupling_%s_" % new)
        value = value.replace("expert_boundary_%s_" % old, "expert_boundary_%s_" % new)
    return value


def _remap_bundle(bundle, mapping):
    if not mapping:
        return bundle
    known = {x["field_name"] for x in bundle.get("feature_schema", [])}
    unknown = sorted(set(mapping) - known)
    if unknown:
        raise ValueError("效能字段映射包含Workbook中不存在的字段: " + ",".join(unknown))
    for item in bundle.get("feature_schema", []):
        item["source_field_name"] = item["field_name"]
        item["field_name"] = mapping.get(item["field_name"], item["field_name"])
    for item in bundle.get("model_input_bindings", []):
        item["source_field_name"] = item["field_name"]
        item["field_name"] = mapping.get(item["field_name"], item["field_name"])
    for model in list(bundle.get("coupling_models", [])) + list(bundle.get("direction_only_couplings", [])):
        model["target_key"] = mapping.get(model.get("target_key"), model.get("target_key"))
        for effect in model.get("source_effects", []):
            effect["key"] = mapping.get(effect.get("key"), effect.get("key"))
        model["source_ranges"] = {mapping.get(k, k): v for k, v in (model.get("source_ranges") or {}).items()}
    feasibility = bundle.get("feasibility_model") or {}
    feasibility["weights"] = {_remap_feature_name(k, mapping): v for k, v in (feasibility.get("weights") or {}).items()}
    feasibility["feature_labels"] = {_remap_feature_name(k, mapping): v for k, v in (feasibility.get("feature_labels") or {}).items()}
    for boundary in feasibility.get("learned_boundaries", []):
        boundary["attribute_key"] = mapping.get(boundary.get("attribute_key"), boundary.get("attribute_key"))
    for name in ("preference_bt", "preference_uta"):
        model = bundle.get(name) or {}
        for key in ("attribute_weights", "stage_prior_weights"):
            model[key] = {mapping.get(k, k): v for k, v in (model.get(key) or {}).items()}
        for curve_key in ("marginal_curves", "curves"):
            for curve in model.get(curve_key, []) or []:
                curve["key"] = mapping.get(curve.get("key"), curve.get("key"))
    for profile in bundle.get("requirement_profiles", []):
        for requirement in profile.get("requirements", []):
            requirement["attribute_key"] = mapping.get(requirement.get("attribute_key"), requirement.get("attribute_key"))
    bundle["historical_samples"] = [
        {mapping.get(k, k): v for k, v in sample.items()}
        for sample in bundle.get("historical_samples", [])
    ]
    policy = bundle.get("generator_policy") or {}
    policy["generation_attributes"] = [mapping.get(k, k) for k in policy.get("generation_attributes", [])]
    bundle.setdefault("training_report", {})["field_mapping"] = mapping
    return bundle

def export_effectiveness_bundle(source_root: Union[str, Path], workbook: Union[str, Path], output: Union[str, Path], product_code: str, state_path: Optional[Union[str, Path]]=None, model_version: str="effectiveness-v19.5", field_map=None) -> Dict[str,Any]:
    source_root=Path(source_root).resolve(); workbook=Path(workbook).resolve(); output=Path(output).resolve()
    required=["project_excel.py","coupling_model.py","feasibility_model.py","preference_models.py","requirement_model.py","interactive_project_app.py"]
    missing=[x for x in required if not (source_root/x).exists()]
    if missing: raise FileNotFoundError("效能源码目录缺少: "+",".join(missing))
    if str(source_root) not in sys.path: sys.path.insert(0,str(source_root))
    from interactive_project_app import ProjectApp
    from preference_models import OnlineBTModel, LPUTAModel
    app=ProjectApp(workbook,state_dir=Path(tempfile.mkdtemp(prefix="eff_export_state_")))
    if state_path:
        state_file=Path(state_path).resolve(); state=json.loads(state_file.read_text(encoding="utf-8")); state_mode="provided_state"
        if state.get("learning_fingerprint") and state["learning_fingerprint"]!=app.project.learning_fingerprint:
            raise ValueError("state learning_fingerprint与Workbook不一致")
        # Rebuild summaries from the supplied state to ensure it is executable, not merely copied.
        app.retrain_feasibility_model(state); app.retrain_preference_models(state)
    else:
        state=app.load_state(reset=True); state_file=None; state_mode="generated_baseline_no_expert_feedback"
    feasibility=app.feasibility_model_from_state(state)
    # Force reconstructability checks.
    bt=OnlineBTModel(app.project,weights=state.get("bt_weights"),requirement_profile=None)
    uta=LPUTAModel(app.project,segments=int(state.get("uta_segments",4)),increments=state.get("uta_increments"),requirement_profile=None)
    attrs=[]; bindings=[]
    for spec in app.project.attributes:
        dtype={"continuous":"number","integer":"integer","categorical":"enum"}.get(spec.data_type,"number")
        attrs.append({
            "field_name":spec.key,"field_label":spec.label,"dtype":dtype,"unit":spec.unit,"required":True,
            "generation_min":spec.generation_min,"generation_max":spec.generation_max,"feasible_min":spec.feasible_min,"feasible_max":spec.feasible_max,
            "precision":spec.precision,"design_stage":spec.design_stage,"preference_direction":spec.preference_direction,"marginal_trend":spec.marginal_trend,
            "participates_utility":spec.participates_utility,"participates_generation":spec.participates_generation,"description":spec.description,
        })
        bindings.append({"model_kind":"effectiveness","field_name":spec.key,"field_label":spec.label,"source_type":"product_parameter","dtype":dtype,"unit":spec.unit,"required":True,"missing_policy":"reject","model_version":model_version,"enabled":True})
    profiles=[]
    for profile in app.project.requirement_profiles:
        profiles.append({"profile_id":profile.id,"profile_name":profile.name,"direct_reuse_threshold":profile.direct_reuse_threshold,"improvement_threshold":profile.improvement_threshold,"redesign_threshold":profile.redesign_threshold,"requirements":[asdict(x) for x in profile.requirements]})
    coupling_models=[]; direction=[]
    for item in app.coupling_system.summaries():
        if item.get("model_status")=="direction_only" or item.get("intercept") is None: direction.append(item)
        else: coupling_models.append(item)
    feasibility_summary=dict(state.get("feasibility_model") or {})
    feasibility_payload={
        **feasibility_summary,
        "weights":{k:float(v) for k,v in feasibility.weights.items()},
        "feature_labels":dict(feasibility.labels),
        "learned_boundaries":feasibility.boundary_summaries(),
        "expert_evidence_count":len(state.get("feasibility_evidence") or []),
        "expert_evidence":state.get("feasibility_evidence") or [],
    }
    preference_bt=dict(state.get("bt_model") or bt.summary([])); preference_bt["weights"]=[float(x) for x in bt.weights]
    preference_uta=dict(state.get("uta_model") or {}); preference_uta.setdefault("segments",uta.segments); preference_uta["increments"]=[float(x) for x in uta.increments]
    if not preference_uta.get("curves"):
        try: preference_uta["curves"]=uta.marginal_curves()
        except Exception: preference_uta["curves"]=[]
    bundle={
        "recommendation_contract_version":"4.0","model_kind":"effectiveness","product_code":product_code,
        "product_name":getattr(app.project, "project_name", None) or getattr(app.project, "product_name", None) or product_code,
        "model_version":model_version,
        "feature_schema":attrs,"model_input_bindings":bindings,
        "coupling_models":coupling_models,"direction_only_couplings":direction,"feasibility_model":feasibility_payload,
        "preference_bt":preference_bt,"preference_uta":preference_uta,"requirement_profiles":profiles,
        "active_requirement_profile_id":state.get("active_protocol_profile_id") or state.get("active_requirement_profile_id") or (app.project.default_requirement_profile().id if app.project.default_requirement_profile() is not None else None),
        "historical_samples":[dict(x.params) for x in app.project.schemes],
        "generator_policy":{"source":"original_effectiveness_project","generation_attributes":[x.key for x in app.project.attributes if x.participates_generation],"coupling_target_count":len(app.coupling_system.target_keys())},
        "training_report":{"state_mode":state_mode,"workbook_path":str(workbook),"workbook_sha256":_sha(workbook),"workbook_fingerprint":app.project.workbook_fingerprint,"learning_fingerprint":app.project.learning_fingerprint,"state_path":str(state_file) if state_file else None,"state_sha256":_sha(state_file) if state_file else None,"sample_count":len(app.project.schemes),"attribute_count":len(app.project.attributes),"coupling_model_count":len(coupling_models),"direction_only_count":len(direction),"warnings":app.project.warnings},
    }
    bundle = _remap_bundle(bundle, _load_field_map(field_map))
    from model_contract_v4 import validate_bundle, evaluate_effectiveness
    errors=validate_bundle(bundle,"effectiveness")
    if errors: raise ValueError("导出模型未通过契约校验: "+";".join(errors))
    # Full parity check against the original ProjectApp. This is the acceptance
    # gate that prevents a syntactically valid but semantically different snapshot.
    if not app.project.schemes: raise ValueError("Workbook没有方案数据")
    score_diffs=[]; probability_diffs=[]; parity_rows=[]
    mapped_samples=bundle["historical_samples"]
    for source_scheme, mapped_params in zip(app.project.schemes, mapped_samples):
        original=app.evaluate(dict(source_scheme.params), state)
        converted=evaluate_effectiveness(bundle, dict(mapped_params))
        score_diff=abs(float(original["effectiveness_score"])-float(converted["capability_score"]))
        probability_diff=abs(float(original["learned_feasibility_probability"])-float(converted["feasibility_probability"]))
        score_diffs.append(score_diff); probability_diffs.append(probability_diff)
        parity_rows.append({"scheme_id":source_scheme.id,"original_score":original["effectiveness_score"],"converted_score":converted["capability_score"],"score_abs_diff":score_diff,"original_feasibility":original["learned_feasibility_probability"],"converted_feasibility":converted["feasibility_probability"],"feasibility_abs_diff":probability_diff})
    max_score=max(score_diffs); max_probability=max(probability_diffs)
    if max_score>0.021:
        raise ValueError("效能快照与原程序评分不一致，最大绝对差%.6f" % max_score)
    if max_probability>0.0051:
        raise ValueError("效能快照与原程序可行概率不一致，最大绝对差%.6f" % max_probability)
    smoke=evaluate_effectiveness(bundle,dict(mapped_samples[0]))
    bundle["training_report"]["smoke_test"]={"status":"PASS","capability_score":smoke["capability_score"],"feasibility_probability":smoke["feasibility_probability"]}
    bundle["training_report"]["original_runtime_parity"]={"status":"PASS","sample_count":len(parity_rows),"max_capability_abs_diff":max_score,"max_feasibility_abs_diff":max_probability,"rows":parity_rows}
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding="utf-8")
    return bundle

def main():
    p=argparse.ArgumentParser(); p.add_argument("--source-root",required=True); p.add_argument("--workbook",required=True); p.add_argument("--state"); p.add_argument("--output",required=True); p.add_argument("--product-code",required=True); p.add_argument("--model-version",default="effectiveness-v19.5"); p.add_argument("--field-map")
    a=p.parse_args(); b=export_effectiveness_bundle(a.source_root,a.workbook,a.output,a.product_code,a.state,a.model_version,a.field_map); print(json.dumps({"status":"PASS","output":a.output,"features":len(b["feature_schema"]),"couplings":len(b["coupling_models"])},ensure_ascii=False))
if __name__=="__main__": main()
