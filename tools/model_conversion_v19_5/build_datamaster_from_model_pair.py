# -*- coding: utf-8 -*-
"""Build a minimal, valid V19.5 DataMaster from a contract-4 model pair.

The generated workbook is an initialization aid. Tags, explicit engineering
constraints and expert couplings remain empty and should be completed by the
operator before production use. Learned coupling contours remain inside the
effectiveness bundle and are still evaluated by the runtime.
"""
from __future__ import print_function

import argparse
import json
from pathlib import Path

from model_contract_v4 import load_bundle, validate_bundle
from reference_runtime.model_runtime import IntegratedModelRuntime
from reference_runtime.xlsx_utils import write_workbook_bytes
from validate_and_install_models import build_sample, validate_price_only_fallbacks, validate_shared_bindings


SHEETS = {
    "成品信息": ["成品代号", "成品名称", "成品说明", "是否启用"],
    "指标定义": ["指标编号", "指标名称", "单位", "取值类型", "搜索类型", "工程下限", "工程上限", "效能方向", "指标说明", "调整提示", "允许值", "是否必填", "允许自动调整", "显示小数位", "显示顺序", "是否启用"],
    "标签字典": ["标签编号", "标签名称", "标签分组", "匹配权重", "生成判定方式", "标签说明", "是否启用"],
    "标签规则": ["规则编号", "标签编号", "指标编号", "比较关系", "条件值1", "条件值2", "规则组", "是否启用"],
    "耦合关系": ["关系编号", "关系名称", "关系类型", "指标A", "指标B", "可行域比较", "系数", "偏置", "作用强度", "提示级别", "关系说明", "设置依据", "显示顺序", "是否启用"],
    "约束规则": ["规则编号", "规则名称", "左侧指标", "比较关系", "右侧指标", "系数", "偏置", "提示级别", "违反提示", "设置依据", "显示顺序", "是否启用"],
    "历史协议": ["协议编号", "协议名称", "方案定位", "协议来源", "来源年份", "供应方类型", "历史价格(万元)", "标签"],
    "模型字段绑定": ["模型类型", "字段编号", "字段名称", "字段来源", "数据类型", "单位", "是否必填", "缺失策略", "数据库配置值", "训练均值", "模型版本", "是否启用"],
}


def yes(value):
    return "是" if value else "否"


def value_type(spec):
    dtype = spec.get("dtype") or spec.get("type") or "number"
    return {"number": "数值", "integer": "数值", "boolean": "布尔", "ip_grade": "IP等级", "enum": "枚举", "text": "文本"}.get(dtype, dtype)


def search_type(spec):
    raw = spec.get("search_type") or "auto"
    return {"auto": "自动识别", "continuous": "连续数值", "integer": "整数数值", "ordered_discrete": "有序离散", "unordered_enum": "无序枚举", "boolean": "布尔开关"}.get(raw, raw)


def preference(spec):
    raw = spec.get("preference") or "neutral"
    return {"higher": "越大越好", "lower": "越小越好", "neutral": "中性"}.get(raw, "中性")


def fallback_value(spec):
    if spec.get("default_value") is not None:
        return spec.get("default_value")
    if spec.get("training_mean") is not None:
        return spec.get("training_mean")
    if spec.get("type") == "boolean" or spec.get("dtype") == "boolean":
        return 0
    lo, hi = spec.get("min"), spec.get("max")
    if lo is not None and hi is not None:
        return 0.5 * (float(lo) + float(hi))
    return ""


def main():
    parser = argparse.ArgumentParser(description="从契约4.0模型对生成V19.5初始化DataMaster")
    parser.add_argument("--effectiveness", required=True)
    parser.add_argument("--price", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-history", type=int, default=200)
    args = parser.parse_args()

    e = load_bundle(args.effectiveness)
    p = load_bundle(args.price)
    errors = validate_bundle(e, "effectiveness") + validate_bundle(p, "price")
    shared_errors, _shared = validate_shared_bindings(e, p)
    errors += shared_errors + validate_price_only_fallbacks(e, p)
    if e.get("product_code") != p.get("product_code"):
        errors.append("两个模型product_code不一致")
    if errors:
        raise SystemExit(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))

    model_dir = Path(args.output).resolve().parent / (".v195_datamaster_models_%s" % e["product_code"])
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "effectiveness_bundle.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    (model_dir / "price_bundle.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
    runtime = IntegratedModelRuntime(model_dir)
    specs = runtime.all_feature_specs()
    roles = runtime.feature_roles()
    price_only = set(roles["price_only_features"])

    product_name = e.get("product_name") or (e.get("training_report") or {}).get("project_name") or e["product_code"]
    sheets = []
    sheets.append(("成品信息", [SHEETS["成品信息"], [e["product_code"], product_name, "由V19.5模型转换工具生成的初始化DataMaster，请补充标签和显式工程规则。", "是"]]))

    parameter_rows = [SHEETS["指标定义"]]
    for order, spec in enumerate(specs, 1):
        allowed = spec.get("allowed_values") or []
        parameter_rows.append([
            spec["key"], spec.get("label", spec["key"]), spec.get("unit", ""), value_type(spec), search_type(spec),
            spec.get("min"), spec.get("max"), preference(spec), spec.get("description", ""),
            spec.get("adjustment_hint") or ("价格专用属性，默认折叠显示。" if spec["key"] in price_only else ""),
            "、".join(str(x) for x in allowed), yes(spec.get("required", True)), yes(spec.get("auto_adjustable", True)),
            int(spec.get("decimal_places", 3)), order, "是",
        ])
    sheets.append(("指标定义", parameter_rows))
    for name in ("标签字典", "标签规则", "耦合关系", "约束规则"):
        sheets.append((name, [SHEETS[name]]))

    history_headers = list(SHEETS["历史协议"]) + [spec.get("label", spec["key"]) + (("(%s)" % spec.get("unit")) if spec.get("unit") else "") for spec in specs]
    history_rows = [history_headers]
    samples = list(e.get("historical_samples") or [])[:max(0, args.max_history)]
    price_bindings = {x["field_name"]: x for x in p.get("model_input_bindings") or [] if x.get("enabled", True)}
    for index, raw in enumerate(samples, 1):
        values = dict(raw)
        for spec in specs:
            key = spec["key"]
            if key not in values:
                binding = price_bindings.get(key, {})
                policy = binding.get("missing_policy")
                if policy == "training_mean": values[key] = binding.get("training_mean")
                elif policy in ("default", "constant"): values[key] = binding.get("configured_value")
                elif policy == "zero": values[key] = 0
                else: values[key] = fallback_value(spec)
        history_rows.append([
            "MODEL-HIST-%04d" % index, "模型历史样本%04d" % index, "模型转换初始化样本", "historical", "", "", "", "",
        ] + [values.get(spec["key"], "") for spec in specs])
    sheets.append(("历史协议", history_rows))

    binding_rows = [SHEETS["模型字段绑定"]]
    for bundle in (e, p):
        for b in bundle.get("model_input_bindings") or []:
            if not b.get("enabled", True):
                continue
            binding_rows.append([
                b.get("model_kind"), b.get("field_name"), b.get("field_label", b.get("field_name")),
                b.get("source_type", "product_parameter"), b.get("dtype", "number"), b.get("unit", ""),
                yes(b.get("required", True)), b.get("missing_policy", "reject"), b.get("configured_value"),
                b.get("training_mean"), b.get("model_version"), "是",
            ])
    sheets.append(("模型字段绑定", binding_rows))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(write_workbook_bytes(sheets))
    try:
        for child in model_dir.iterdir(): child.unlink()
        model_dir.rmdir()
    except Exception:
        pass
    print(json.dumps({
        "status": "PASS", "output": str(output), "product_code": e["product_code"],
        "parameter_count": len(specs), "historical_count": len(samples), "roles": roles,
        "warning": "该工作簿是初始化模板，正式使用前应补充标签、显式耦合和工程约束。",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
