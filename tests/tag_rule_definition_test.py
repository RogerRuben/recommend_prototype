# -*- coding: utf-8 -*-
"""Store tag-rule matching passes parameter definitions into filter_match."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.store import Store  # noqa: E402


TYPE_DEF = {
    "parameter_id": "type", "label": "类型", "value_type": "enum",
    "model_value_mapping_json": {"常规型": 1, "增强型": 2},
}


def main():
    # _tag_rule_match needs no instance state, so skip the DB-backed __init__.
    store = Store.__new__(Store)
    definitions = {"type": TYPE_DEF}
    rule = {"parameter_id": "type", "operator": "text_equals", "value1": "常规型"}
    assert store._tag_rule_match({"type": 1.0}, rule, definitions) is True
    assert store._tag_rule_match({"type": "1"}, rule, definitions) is True
    assert store._tag_rule_match({"type": 2}, rule, definitions) is False

    print(json.dumps({"status": "PASS", "message": "自动Tag规则透传参数定义，映射枚举一致匹配"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
