# -*- coding: utf-8 -*-
"""V21.2 scenario state closure: latest response and generated-batch provenance."""
from __future__ import print_function

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "app" / "static" / "app.js"
sys.path.insert(0, str(ROOT))


def test_latest_recommendation_response_wins():
    source = APP_JS.read_text(encoding="utf-8")
    line = next(line.strip() for line in source.splitlines() if line.strip().startswith("async function recommend("))
    harness = r"""
const vm = require('vm');
const fn = process.argv[1];
const pending = [];
const rendered = [];
const elements = {
  loading:{classList:{remove(){},add(){}}},
  sourceMode:{value:'historical'},
};
const context = {
  state:{recommendSeq:0,recommendAppliedSeq:0,currentBatchId:null,generationBatchStale:false,page:1},
  q:(id)=>elements[id] || (elements[id]={value:'',classList:{remove(){},add(){}}}),
  show:()=>{}, hide:()=>{}, toast:()=>{}, requestPayload:()=>({}),
  api:()=>new Promise((resolve,reject)=>pending.push({resolve,reject})),
  renderResults:(data)=>rendered.push(data.scenario), showEmptyGeneration:()=>{},
  requestSnapshot:()=>'', setGenerationStatus:()=>{}, pollGenerationForDisplay:()=>{},
  clearTimeout:()=>{}, setTimeout:()=>{},
};
vm.createContext(context);
vm.runInContext(fn, context);
(async()=>{
  const oldRequest=context.recommend(false);
  const latestRequest=context.recommend(false);
  pending[1].resolve({scenario:'performance'});
  await latestRequest;
  pending[0].resolve({scenario:'cost'});
  await oldRequest;
  if (rendered.join(',') !== 'performance') throw new Error('stale response was rendered: '+rendered);
  if (context.state.recommendAppliedSeq !== 2) throw new Error('latest sequence was not applied');
  console.log('RACE_GUARD_OK');
})().catch((error)=>{console.error(error);process.exit(1)});
"""
    run = subprocess.run(["node", "-e", harness, line], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "RACE_GUARD_OK" in run.stdout


def test_generated_batch_requires_matching_generation_fingerprint():
    from app.server import GeneratedSessions

    sessions = GeneratedSessions()
    batch_id, _items = sessions.add_batch(
        "session", [{"candidate_id": "one"}], fingerprint="cost-fingerprint"
    )
    assert sessions.get("session", batch_id, fingerprint="cost-fingerprint")
    assert sessions.get("session", batch_id, fingerprint="performance-fingerprint") == []
    metadata = sessions.batch_metadata("session", batch_id)
    assert metadata["fingerprint"] == "cost-fingerprint"
    assert metadata["count"] == 1

    # No implicit "latest batch" lookup is allowed in recommendation code: the
    # current UI must explicitly carry the batch selected for its criteria.
    server_source = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
    assert "if calculation_available and requested_batch_id else []" in server_source


def test_scenario_constraints_share_business_target_inputs():
    source = APP_JS.read_text(encoding="utf-8")
    assert 'max_price:"maxPrice",min_capability:"minCapability"' in source
    assert "沿用上方" in source
    assert "data-scenario-option" not in source
    assert 'scenario_options:scenarioOptionValues()' in source


def test_optimization_scenario_is_first_workflow_step():
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    source = APP_JS.read_text(encoding="utf-8")

    workflow = html.index("推荐工作流程")
    scenario = html.index('id="scenarioChoices"')
    tags = html.index('id="tagGroups"')
    targets = html.index('id="maxPrice"')
    filters = html.index('id="addFilterBtn"')
    assert workflow < scenario < tags < targets < filters
    assert '<span class="step-index">01</span><h3>选择优化场景</h3>' in html
    assert '<span class="step-index">02</span><h3>应用场景与功能偏好</h3>' in html
    assert '<span class="step-index">03</span><h3>业务目标</h3>' in html
    assert "① 选择优化场景" in html and "⑦ 查看 / 调整 / 保存方案" in html

    tour = source[source.index("function playTour(){"):source.index("function playDetailTour(){")]
    ordered_targets = [
        '#scenarioChoices', '#tagGroups', '#maxPrice', '#addFilterBtn',
        '#recommendBtn', '#generateBtn', '.results-toolbar',
    ]
    positions = [tour.index(target) for target in ordered_targets]
    assert positions == sorted(positions)
    assert "① 选择优化场景" in tour and "⑦ 推荐结果" in tour
    assert "ipdemo-tour-v21-2-scenario-first" in tour


if __name__ == "__main__":
    test_latest_recommendation_response_wins()
    test_generated_batch_requires_matching_generation_fingerprint()
    test_scenario_constraints_share_business_target_inputs()
    test_optimization_scenario_is_first_workflow_step()
    print("PASS V21.2 scenario state closure")
