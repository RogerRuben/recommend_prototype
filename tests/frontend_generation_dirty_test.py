# -*- coding: utf-8 -*-
"""Static guards for frontend generation-criteria dirty tracking and snapshot."""
from __future__ import print_function

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "app" / "static" / "app.js"


def main():
    source = APP_JS.read_text(encoding="utf-8")

    assert "function markGenerationCriteriaDirty" in source, "markGenerationCriteriaDirty missing"
    assert "markGenerationCriteriaDirty()" in source

    # requestSnapshot must include budget/rounds so auto-switch can detect stale tasks.
    snapshot_idx = source.find("function requestSnapshot(){")
    snapshot_body = source[snapshot_idx:source.find("\n", snapshot_idx)]
    assert "generationBudget" in snapshot_body and "generationRounds" in snapshot_body, "snapshot missing budget/rounds"

    # The duplicate collectFrozen from the old UI must be gone.
    assert source.count("function collectFrozen()") == 1, "duplicate collectFrozen still present"

    # Frozen group select and item changes mark generation dirty.
    assert "refreshFrozenSummary();markGenerationCriteriaDirty()" in source

    # Run the real stale-result renderer with a minimal DOM. Old generated cards
    # and their click cache must disappear without starting a recommendation.
    lines = []
    for name in ("syncSourceMode", "showStaleGenerationResults"):
        lines.append(next(line.strip() for line in source.splitlines()
                          if line.strip().startswith("function " + name + "(")))
    harness = r"""
const vm=require('vm');
const functions=process.argv[1];
function classes(active){return{active:!!active,toggle(name,value){if(name==='active')this.active=!!value},add(){},remove(){}}}
const elements={
 sourceMode:{value:'generated'},resultSummary:{textContent:''},pagination:{innerHTML:'old'},
 results:{innerHTML:'old'},generationReport:{classList:classes(false)},
 viewHistoricalAfterStale:{onclick:null},regenerateAfterStale:{onclick:null},
};
const tabs=[{dataset:{source:'historical'},classList:classes(false)},{dataset:{source:'generated'},classList:classes(true)}];
let recommends=0,generates=0;
const context={state:{itemsById:{old:{}} ,page:9},q:(id)=>elements[id],document:{querySelectorAll:()=>tabs},hide:()=>{},recommend:()=>{recommends++},generate:()=>{generates++}};
vm.createContext(context);vm.runInContext(functions+'\nshowStaleGenerationResults();',context);
if(elements.sourceMode.value!=='historical'||!tabs[0].classList.active||tabs[1].classList.active)throw new Error('source tab not synchronized');
if(Object.keys(context.state.itemsById).length||elements.pagination.innerHTML!=='')throw new Error('old result state retained');
if(!elements.results.innerHTML.includes('当前需求已变化')||!elements.results.innerHTML.includes('重新生成'))throw new Error('stale state missing');
if(recommends||generates)throw new Error('renderer started a request');
elements.viewHistoricalAfterStale.onclick();elements.regenerateAfterStale.onclick();
if(recommends!==1||generates!==1||context.state.page!==1)throw new Error('stale actions not wired');
console.log('STALE_UI_OK');
"""
    run = subprocess.run(["node", "-e", harness, "\n".join(lines)], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "STALE_UI_OK" in run.stdout
    assert "if(hadBatch)showStaleGenerationResults()" in source

    print(json.dumps({"status": "PASS", "message": "前端生成条件脏标记与 requestSnapshot 已补齐"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
