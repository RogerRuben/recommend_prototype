# -*- coding: utf-8 -*-
"""Package the original effectiveness runtime without changing its model logic.

The output contains the exact source modules, project Workbook, optional learned
State and a manifest with fingerprints/hashes.  The prediction service loads
this package and reconstructs ProjectApp exactly as the original program does.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED_SOURCE = [
    "interactive_project_app.py", "project_excel.py", "coupling_model.py",
    "feasibility_model.py", "preference_models.py", "requirement_model.py",
]


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def _is_within(path, directory):
    try:
        Path(path).relative_to(Path(directory))
        return True
    except ValueError:
        return False


def package_runtime(source_root, workbook, output_dir, state=None, expected_product_code=None):
    source_root=Path(source_root).resolve(); workbook=Path(workbook).resolve(); output=Path(output_dir).resolve()
    missing=[name for name in REQUIRED_SOURCE if not (source_root/name).is_file()]
    if missing: raise ValueError("效能源码不完整，缺少: %s" % ",".join(missing))
    if not workbook.is_file(): raise ValueError("Workbook不存在: %s" % workbook)
    state_path=Path(state).resolve() if state else None
    if state_path and not state_path.is_file(): raise ValueError("State不存在: %s" % state_path)
    for label, input_path in (("源码目录", source_root), ("Workbook", workbook), ("State", state_path)):
        if input_path is not None and _is_within(input_path, output):
            raise ValueError(
                "%s不能位于输出目录内: %s。请使用效能人员交付的原始文件作为输入，"
                "输出目录会被整体替换。" % (label, input_path)
            )

    # Build away from current/.  A failed build must not destroy the last
    # working effectiveness package.
    stage = output.parent / (".%s.building-%s" % (output.name, uuid.uuid4().hex[:8]))
    (stage/"source").mkdir(parents=True); (stage/"data").mkdir(); (stage/"state").mkdir()
    files=[]
    for name in REQUIRED_SOURCE:
        target=stage/"source"/name; shutil.copy2(str(source_root/name),str(target)); files.append(("source/"+name,target))
    workbook_target=stage/"data"/workbook.name; shutil.copy2(str(workbook),str(workbook_target)); files.append(("data/"+workbook.name,workbook_target))
    state_rel=None
    if state_path:
        target=stage/"state"/state_path.name; shutil.copy2(str(state_path),str(target)); files.append(("state/"+state_path.name,target)); state_rel="state/"+state_path.name
    # Validate by reconstructing the original runtime before publishing manifest.
    from services.effectiveness_service.app import OriginalRuntimeBackend
    backend=OriginalRuntimeBackend(stage/"source",workbook_target,stage/state_rel if state_rel else None)
    expected = str(expected_product_code or "").strip()
    if expected and backend.product_code != expected:
        shutil.rmtree(str(stage), ignore_errors=True)
        raise ValueError(
            "效能Workbook实际product_code为 %r，与期望值 %r 不一致。"
            "请确认修改的是本次--workbook指向的文件，并检查‘项目信息’!B1。"
            % (backend.product_code, expected)
        )
    if state_rel and backend.app.state_path.is_file():
        # Publish the state after the original application's standard migration.
        # The caller's source state remains untouched.
        shutil.copy2(str(backend.app.state_path), str(stage/state_rel))
    schema = backend.schema()
    manifest={
        "format_version":"effectiveness-original-runtime-package-1.0",
        "product_code":backend.product_code,
        "product_name":backend.product_name,
        "model_version":backend.model_version,
        "algorithm_version":backend.algorithm_version,
        "profile_version":backend.profile_version,
        "source_root":"source",
        "workbook":"data/"+workbook.name,
        "state":state_rel,
        "workbook_fingerprint":backend.app.project.workbook_fingerprint,
        "learning_fingerprint":backend.app.project.learning_fingerprint,
        "state_sha256":backend.state_sha256,
        "active_protocol":backend.protocol,
        "state_mode":"learned_state" if state_rel else "workbook_baseline",
        "capabilities": {
            "dynamic_target_protocol": bool((schema.get("target_protocol_contract") or {}).get("supported")),
            "packaged_protocol_count": len(schema.get("protocol_profiles") or []),
            "counterfactual_improvement": bool(backend.supports_counterfactual_improvement),
            "coupling_model_count": len(schema.get("coupling_models") or []),
            "coupling_edge_count": len(schema.get("coupling_edges") or []),
            "learned_boundary_count": len(schema.get("learned_boundaries") or []),
        },
        "files":[{"path":rel,"sha256":sha256(path)} for rel,path in files],
        "prediction_equivalence":"loads the same source modules + Workbook + State and calls ProjectApp.evaluate",
    }
    path=stage/"effectiveness_runtime_manifest.json"
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    if output.exists(): shutil.rmtree(str(output))
    stage.replace(output)
    return output/"effectiveness_runtime_manifest.json"


def main():
    parser=argparse.ArgumentParser(description="打包原效能工程为独立预测服务运行包")
    parser.add_argument("--source-root",required=True)
    parser.add_argument("--workbook",required=True)
    parser.add_argument("--state",default="")
    parser.add_argument("--output",required=True)
    parser.add_argument("--expected-product-code",default="")
    args=parser.parse_args()
    path = package_runtime(
        args.source_root, args.workbook, args.output, args.state or None,
        expected_product_code=args.expected_product_code or None,
    )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps({
        "status": "PASS",
        "input_workbook": str(Path(args.workbook).resolve()),
        "output_manifest": str(path),
        "product_code": manifest.get("product_code"),
        "product_name": manifest.get("product_name"),
        "state_mode": manifest.get("state_mode"),
        "workbook_fingerprint": manifest.get("workbook_fingerprint"),
        "learning_fingerprint": manifest.get("learning_fingerprint"),
    }, ensure_ascii=False, indent=2))


if __name__=="__main__": main()
