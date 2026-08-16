# -*- coding: utf-8 -*-
"""Generate a self-consistent V11 effectiveness demo state for a workbook.

Uses the expert runtime's own deterministic demo-state generator
(ProjectApp.prepare_demo_state) so the output state's learning_fingerprint is
bound to the supplied workbook.  This is a demo state: every simulated expert
judgment is clearly labeled as simulation ("系统模拟专家，仅用于演示").

Typical use (aircraft door lock 12-sample acceptance fixture)::

    python tools/gen_effectiveness_demo_state.py \
        --source D:\\pycodes\\source \
        --workbook test_data\\基础航空舱门锁_效能项目_12样本.xlsx \
        --output test_data\\expert_state_v11_12样本.json

The resulting file can be passed to PACKAGE_EFFECTIVENESS_SERVICE_MODEL_WIN7.bat
as the State JSON path.
"""
from __future__ import print_function

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="生成与Workbook学习指纹一致的V11效能演示State")
    parser.add_argument("--source", required=True, help="专家运行时源码目录（含 interactive_project_app.py）")
    parser.add_argument("--workbook", required=True, help="效能项目Workbook路径")
    parser.add_argument("--output", required=True, help="输出State JSON路径")
    parser.add_argument("--preference-count", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20260812)
    parser.add_argument("--state-dir", default="", help="临时状态目录；默认位于输出文件同级的 .eff_state_gen")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    workbook = Path(args.workbook).resolve()
    output = Path(args.output).resolve()
    state_dir = Path(args.state_dir).resolve() if args.state_dir else (output.parent / ".eff_state_gen")

    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    from interactive_project_app import ProjectApp, PROFILE_VERSION

    state_dir.mkdir(parents=True, exist_ok=True)
    app = ProjectApp(workbook, state_dir=state_dir, seed=args.seed)
    expected = app.project.learning_fingerprint
    app.prepare_demo_state(preference_count=args.preference_count)

    state_path = app.state_path
    if not state_path.is_file():
        raise RuntimeError("State文件未生成: %s" % state_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))

    if state.get("profile_version") != PROFILE_VERSION:
        raise RuntimeError("profile_version不匹配: %r" % state.get("profile_version"))
    if state.get("learning_fingerprint") != expected:
        raise RuntimeError(
            "learning_fingerprint不匹配: %r != %r" % (state.get("learning_fingerprint"), expected)
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print("OK")
    print("output        =", output)
    print("profile_ver   =", state.get("profile_version"))
    print("learning_fp   =", state.get("learning_fingerprint"))
    print("workbook_fp   =", state.get("workbook_fingerprint"))
    print("data_mode     =", state.get("data_mode"))
    print("existing      =", len(state.get("existing_samples", [])))
    print("pref_evidence =", len(state.get("preference_evidence", [])))
    print("feas_evidence =", len(state.get("feasibility_evidence", [])))
    print("bt_model      =", bool(state.get("bt_model")))
    print("uta_model     =", bool(state.get("uta_model")))


if __name__ == "__main__":
    main()
