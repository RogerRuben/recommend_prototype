# -*- coding: utf-8 -*-
"""Static UI contracts for the compact V21.4 design workspace."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")

    assert "参数辅助设计系统" in html
    assert "方案智能推荐" in html
    assert "工业技术协议智能推荐系统" not in html
    assert "<h3>业务目标</h3>" not in html
    assert "<h3>推荐排序</h3>" not in html
    assert 'class="card action-card generation-box"' not in html

    scenario = html[html.index('class="card scenario-card"'):html.index('class="card filter-card requirements-card"')]
    assert 'id="maxPrice"' in scenario and 'id="minCapability"' in scenario
    assert 'id="targetProtocol"' in scenario
    assert 'class="product-context"' in html
    assert 'id="sortMenu"' in html and 'id="sortMenuLabel"' in html
    assert 'id="generationPopover"' in html and "✦ 生成新方案" in html

    add_filter = js[js.index("function addFilter("):js.index("function collectFilters(")]
    collect_filters = js[js.index("function collectFilters("):js.index("function sourceBadge(")]
    assert 'data-state="editing"' not in html
    assert "filter-confirmed-summary" in add_filter
    assert "confirm-filter" in add_filter and "cancel-filter" in add_filter and "edit-filter" in add_filter
    assert 'wrap.dataset.state="confirmed"' in add_filter
    assert "wrap._confirmedData=data" in add_filter
    assert "markGenerationCriteriaDirty()" in add_filter
    assert '.filter-row[data-state="confirmed"]' in collect_filters
    assert "row._confirmedData" in collect_filters
    assert "search.oninput=refreshParameterOptions" in add_filter
    assert "selectParameter(button.getAttribute" in add_filter
    assert ".filter-row.parameter-selected" in css
    assert ".toolbar-popover" in css and ".generation-popover" in css
    print("PASS V21.4 compact workspace contracts")


if __name__ == "__main__":
    main()

