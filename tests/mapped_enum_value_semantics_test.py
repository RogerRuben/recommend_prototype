# -*- coding: utf-8 -*-
"""Mapped enum canonical comparison: 常规型 <-> 1 <-> 1.0 <-> "1" all agree."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.recommender import filter_match  # noqa: E402
from app.value_semantics import canonical_filter_value, values_equal  # noqa: E402


TYPE_DEF = {
    "parameter_id": "type", "label": "类型", "value_type": "enum",
    "model_value_mapping_json": {"常规型": 1, "增强型": 2},
}


def main():
    # A stored model encoding must equal the operator's business label.
    for stored in (1, 1.0, "1", "1.0"):
        assert filter_match({"type": stored}, {"parameter_id": "type", "operator": "text_equals", "value1": "常规型"}, TYPE_DEF), \
            "stored %r must match 常规型" % (stored,)
    assert not filter_match({"type": "2"}, {"parameter_id": "type", "operator": "text_equals", "value1": "常规型"}, TYPE_DEF)
    assert filter_match({"type": 2}, {"parameter_id": "type", "operator": "text_equals", "value1": "增强型"}, TYPE_DEF)

    # canonical_filter_value maps the business label to the model value.
    assert canonical_filter_value("常规型", TYPE_DEF) == 1
    assert canonical_filter_value("增强型", TYPE_DEF) == 2

    # values_equal agrees across numeric/string representations of the mapping.
    assert values_equal("1.0", 1, TYPE_DEF)
    assert values_equal(1, "1", TYPE_DEF)
    assert not values_equal(1, 2, TYPE_DEF)

    print(json.dumps({"status": "PASS", "message": "映射枚举的编码与业务值比较一致"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
