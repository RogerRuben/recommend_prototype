# -*- coding: utf-8 -*-
"""Validate contract-4 bundles and safely install them into integrated V19.5.

The installer never copies a sidecar runtime into the application. It verifies
that the target project already contains the integrated ``app/model_runtime.py``
introduced by V19.5, stages both bundles, runs the target runtime, and only then
performs an atomic replacement. Product changes require an explicit matching
DataMaster workbook.
"""
from __future__ import print_function

import argparse
import importlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from model_contract_v4 import evaluate_joint, load_bundle, validate_bundle


def _enabled_bindings(bundle):
    return {
        row["field_name"]: row
        for row in bundle.get("model_input_bindings", [])
        if row.get("enabled", True)
    }


def validate_shared_bindings(effectiveness, price):
    errors = []
    e = _enabled_bindings(effectiveness)
    p = _enabled_bindings(price)
    shared = sorted(set(e) & set(p))
    for field_name in shared:
        for key in ("dtype", "unit", "source_type"):
            left = str(e[field_name].get(key) or "")
            right = str(p[field_name].get(key) or "")
            if left != right:
                errors.append(
                    "共享字段%s的%s不一致: effectiveness=%s, price=%s"
                    % (field_name, key, left, right)
                )
    return errors, shared


def validate_price_only_fallbacks(effectiveness, price):
    errors = []
    effect_fields = set(_enabled_bindings(effectiveness))
    for name, binding in _enabled_bindings(price).items():
        if name in effect_fields or binding.get("source_type", "product_parameter") != "product_parameter":
            continue
        policy = binding.get("missing_policy", "reject")
        if not binding.get("required", True):
            continue
        if policy == "training_mean" and binding.get("training_mean") is not None:
            continue
        if policy in ("default", "constant") and binding.get("configured_value") is not None:
            continue
        if policy == "zero":
            continue
        errors.append(
            "价格专用必填字段%s缺少可部署的默认策略；旧协议无法补全该字段" % name
        )
    return errors


def build_sample(effectiveness, price, sample_path=None):
    if sample_path:
        return json.loads(Path(sample_path).read_text(encoding="utf-8"))
    samples = effectiveness.get("historical_samples") or []
    if not samples:
        raise ValueError("效能模型没有historical_samples，必须提供--sample-json")
    sample = dict(samples[0])
    for binding in price.get("model_input_bindings", []):
        if not binding.get("enabled", True):
            continue
        name = binding["field_name"]
        if name in sample:
            continue
        policy = binding.get("missing_policy", "reject")
        if policy == "training_mean":
            sample[name] = binding.get("training_mean")
        elif policy in ("default", "constant"):
            sample[name] = binding.get("configured_value")
        elif policy == "zero":
            sample[name] = 0
    return sample


def _current_product_code(project_root):
    db = Path(project_root) / "data" / "protocol_demo.db"
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute(
                "SELECT product_code FROM products WHERE enabled=1 ORDER BY product_code LIMIT 1"
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except Exception:
        return None


def _load_target_runtime(project_root, staged_model_dir):
    root = Path(project_root).resolve()
    runtime_file = root / "app" / "model_runtime.py"
    contract_file = root / "app" / "model_contract_v4.py"
    if not runtime_file.is_file() or not contract_file.is_file():
        raise ValueError("目标项目不是完整V19.5：缺少app/model_runtime.py或app/model_contract_v4.py")
    source = runtime_file.read_text(encoding="utf-8", errors="replace")
    if "class IntegratedModelRuntime" not in source or "EffectivenessBundleV4" not in source:
        raise ValueError("目标项目尚未集成契约4.0运行时；请先安装V19.4→V19.5程序升级补丁")

    sys.path.insert(0, str(root))
    try:
        # Avoid accidentally reusing a different project's ``app`` package.
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        module = importlib.import_module("app.model_runtime")
        runtime = module.IntegratedModelRuntime(staged_model_dir)
        return runtime
    finally:
        try:
            sys.path.remove(str(root))
        except ValueError:
            pass


def _fake_store_for_runtime(runtime):
    class FakeStore(object):
        def admin_snapshot(self):
            rows = []
            manifest = runtime.manifest()
            for spec in runtime.effectiveness.features:
                rows.append({
                    "binding_id": "effectiveness:%s" % spec["key"],
                    "model_kind": "effectiveness", "parameter_id": spec["key"],
                    "label": spec.get("label", spec["key"]), "source_type": "product_parameter",
                    "data_type": "ip_grade" if spec.get("parser") == "ip_grade" else spec.get("dtype") or spec.get("type", "number"),
                    "unit": spec.get("unit", ""), "required": 1 if spec.get("required", True) else 0,
                    "missing_policy": spec.get("missing_policy", "reject"), "configured_value": None,
                    "training_mean": spec.get("training_mean"),
                    "model_version": manifest["effectiveness"]["model_version"], "enabled": 1,
                })
            for spec in runtime.price.raw_contract:
                rows.append({
                    "binding_id": "price:%s" % spec["key"],
                    "model_kind": "price", "parameter_id": spec["key"],
                    "label": spec.get("label", spec["key"]), "source_type": spec.get("source", "product_parameter"),
                    "data_type": spec.get("dtype") or spec.get("type", "number"), "unit": spec.get("unit", ""),
                    "required": 1 if spec.get("required", True) else 0,
                    "missing_policy": spec.get("missing_policy", "reject"),
                    "configured_value": spec.get("default_value"), "training_mean": spec.get("training_mean"),
                    "model_version": manifest["price"]["model_version"], "enabled": 1,
                })
            return {"model_inputs": rows}
    return FakeStore()


def validate_datamaster(project_root, runtime, data_master_path):
    root = Path(project_root).resolve()
    sys.path.insert(0, str(root))
    try:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        module = importlib.import_module("app.data_master")
        service = module.DataMasterService(_fake_store_for_runtime(runtime), runtime)
        path = Path(data_master_path)
        report = service.parse(path.name, path.read_bytes())
        if not report.get("valid"):
            raise ValueError("新DataMaster与模型不兼容：%s" % "；".join(report.get("errors") or []))
        return report
    finally:
        try:
            sys.path.remove(str(root))
        except ValueError:
            pass


def _backup_file(path, backup_root):
    path = Path(path)
    if not path.exists():
        return None
    target = Path(backup_root) / path.name
    if path.is_dir():
        shutil.copytree(str(path), str(target))
    else:
        shutil.copy2(str(path), str(target))
    return target


def _atomic_copy(src, target):
    src, target = Path(src), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".v195tmp")
    if temp.exists():
        temp.unlink()
    shutil.copy2(str(src), str(temp))
    os.replace(str(temp), str(target))


def _full_app_smoke(project_root):
    script = r'''
import json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from app.server import Application
app = Application(root)
bootstrap = app.bootstrap()
rows = app.store.historical_agreements()
result = app.runtime.evaluate(rows[0]["params"]) if rows else None
# Keep the operator-visible workbook synchronized with any auto-created price-only fields.
(root / "data_master" / "DataMaster_Current.xlsx").write_bytes(app.data_master.export_current())
print(json.dumps({
  "status":"PASS", "product_code":app.runtime.schema["product_code"],
  "parameter_count":len(bootstrap.get("parameters") or []),
  "historical_count":bootstrap.get("counts",{}).get("historical",0),
  "smoke_result":result,
}, ensure_ascii=False))
'''
    proc = subprocess.run(
        [sys.executable, "-c", script, str(Path(project_root).resolve())],
        cwd=str(Path(project_root).resolve()), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True, timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError("完整项目启动冒烟测试失败：%s" % (proc.stderr.strip() or proc.stdout.strip()))
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    try:
        return json.loads(lines[-1])
    except Exception:
        raise RuntimeError("完整项目冒烟测试没有返回有效JSON：%s" % proc.stdout)


def install(effectiveness_path, price_path, project_root, sample, data_master=None, allow_product_change=False):
    root = Path(project_root).resolve()
    if not (root / "app").is_dir() or not (root / "models").is_dir():
        raise ValueError("项目目录缺少app/或models/")

    with tempfile.TemporaryDirectory(prefix="ipdemo_v195_stage_") as temp_name:
        stage = Path(temp_name)
        _atomic_copy(effectiveness_path, stage / "effectiveness_bundle.json")
        _atomic_copy(price_path, stage / "price_bundle.json")
        runtime = _load_target_runtime(root, stage)
        runtime_result = runtime.evaluate(sample)
        new_product = runtime.schema["product_code"]
        current_product = _current_product_code(root)
        product_change = bool(current_product and current_product != new_product)

        datamaster_report = None
        if product_change:
            if not allow_product_change:
                raise ValueError(
                    "模型成品%s与当前项目成品%s不同。切换成品必须同时提供--allow-product-change和--data-master。"
                    % (new_product, current_product)
                )
            if not data_master:
                raise ValueError("切换成品必须提供与新模型匹配的--data-master")
        if data_master:
            datamaster_report = validate_datamaster(root, runtime, data_master)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup = root / "backups" / ("model_v19_5_%s" % timestamp)
        backup.mkdir(parents=True, exist_ok=True)
        tracked = [
            root / "models" / "effectiveness_bundle.json",
            root / "models" / "price_bundle.json",
            root / "models" / "model_manifest_v19_5.json",
            root / "data_master" / "DataMaster_Current.xlsx",
            root / "data" / "protocol_demo.db",
            root / "data" / "protocol_demo.db-wal",
            root / "data" / "protocol_demo.db-shm",
        ]
        for path in tracked:
            _backup_file(path, backup)

        try:
            _atomic_copy(effectiveness_path, root / "models" / "effectiveness_bundle.json")
            _atomic_copy(price_path, root / "models" / "price_bundle.json")
            if data_master:
                _atomic_copy(data_master, root / "data_master" / "DataMaster_Current.xlsx")
            if product_change:
                # Preserve the old database in the backup and let Application rebuild
                # a clean database from the validated DataMaster.
                for suffix in ("", "-wal", "-shm"):
                    path = root / "data" / ("protocol_demo.db" + suffix)
                    if path.exists():
                        path.unlink()
            app_smoke = _full_app_smoke(root)
            installed_runtime = _load_target_runtime(root, root / "models")
            manifest = installed_runtime.manifest()
            manifest_path = root / "models" / "model_manifest_v19_5.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            return {
                "installed": [
                    str(root / "models" / "effectiveness_bundle.json"),
                    str(root / "models" / "price_bundle.json"),
                    str(manifest_path),
                ],
                "backup": str(backup), "runtime_smoke": runtime_result,
                "full_app_smoke": app_smoke, "product_changed": product_change,
                "datamaster_validation": datamaster_report,
            }
        except Exception:
            # Roll back every tracked file. Files absent before installation are removed.
            for path in tracked:
                backup_path = backup / path.name
                if path.exists():
                    if path.is_dir(): shutil.rmtree(str(path))
                    else: path.unlink()
                if backup_path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if backup_path.is_dir(): shutil.copytree(str(backup_path), str(path))
                    else: shutil.copy2(str(backup_path), str(path))
            raise


def main():
    parser = argparse.ArgumentParser(description="验证并安全安装V19.5契约4.0价格/效能模型")
    parser.add_argument("--effectiveness", required=True)
    parser.add_argument("--price", required=True)
    parser.add_argument("--project-root")
    parser.add_argument("--sample-json")
    parser.add_argument("--data-master", help="切换成品时必须提供的匹配DataMaster")
    parser.add_argument("--allow-product-change", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    effectiveness = load_bundle(args.effectiveness)
    price = load_bundle(args.price)
    errors = validate_bundle(effectiveness, "effectiveness")
    errors += validate_bundle(price, "price")
    shared_errors, shared = validate_shared_bindings(effectiveness, price)
    errors += shared_errors
    errors += validate_price_only_fallbacks(effectiveness, price)
    if effectiveness.get("product_code") != price.get("product_code"):
        errors.append("两个模型product_code不一致")
    if errors:
        raise SystemExit(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))

    sample = build_sample(effectiveness, price, args.sample_json)
    result = evaluate_joint(effectiveness, price, sample)
    output = {
        "status": "PASS", "product_code": effectiveness["product_code"],
        "shared_fields": shared, "shared_field_count": len(shared),
        "joint_smoke_test": result, "installed": [], "backup": None,
    }
    if args.project_root:
        root = Path(args.project_root).resolve()
        with tempfile.TemporaryDirectory(prefix="ipdemo_v195_preflight_") as temp_name:
            stage = Path(temp_name)
            _atomic_copy(args.effectiveness, stage / "effectiveness_bundle.json")
            _atomic_copy(args.price, stage / "price_bundle.json")
            target_runtime = _load_target_runtime(root, stage)
            output["target_runtime_manifest"] = target_runtime.manifest()
            output["target_runtime_smoke"] = target_runtime.evaluate(sample)
            if args.data_master:
                output["datamaster_preflight"] = validate_datamaster(root, target_runtime, args.data_master)
        if not args.validate_only:
            output.update(install(
                args.effectiveness, args.price, root, sample,
                data_master=args.data_master, allow_product_change=args.allow_product_change,
            ))
    elif not args.validate_only:
        output["note"] = "未提供--project-root，仅完成模型契约与联合推理校验。"
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
