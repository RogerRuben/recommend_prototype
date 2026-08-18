# -*- coding: utf-8 -*-
"""Unified business value semantics: numeric/boolean equality and coded display."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.recommender import filter_match  # noqa: E402
from app.value_semantics import (  # noqa: E402
    business_display_value, canonical_filter_value, normalize_boolean,
    normalize_numeric, values_equal,
)


class StubRuntime(object):
    def manifest(self):
        return {"calculation_available": False}


def main():
    # Numeric equality across textual/numeric representations.
    assert values_equal(1, 1.0) is True
    assert values_equal("1", "1.0") is True
    assert values_equal("1", "2") is False

    # Boolean normalization covers every legal form.
    for truthy in (True, 1, 1.0, "1", "1.0", "true", "yes", "是", "有"):
        assert normalize_boolean(truthy) is True, repr(truthy)
    for falsy in (False, 0, 0.0, "0", "0.0", "false", "no", "否", "无"):
        assert normalize_boolean(falsy) is False, repr(falsy)
    assert normalize_boolean("not-a-boolean") is None

    # filter_match boolean_is uses the unified boolean semantics.
    assert filter_match({"a": 1.0}, {"parameter_id": "a", "operator": "boolean_is", "value1": "有"}) is True
    assert filter_match({"a": "1.0"}, {"parameter_id": "a", "operator": "boolean_is", "value1": "有"}) is True
    assert filter_match({"a": 0.0}, {"parameter_id": "a", "operator": "boolean_is", "value1": "无"}) is True
    assert filter_match({"a": "1"}, {"parameter_id": "a", "operator": "boolean_is", "value1": "无"}) is False

    # IP grades keep working.
    assert normalize_numeric("IP65") == 65.0
    assert normalize_numeric(65) == 65.0
    assert values_equal("IP65", 65) is True

    # Business display honours the mapping and IP.
    mapping_def = {"value_type": "boolean",
                   "model_value_mapping_json": json.dumps({"有": 1, "无": 0, "无该属性": -1})}
    assert business_display_value(1, mapping_def) == "有"
    assert business_display_value(0, mapping_def) == "无"
    assert business_display_value(-1, mapping_def) == "无该属性"
    assert business_display_value(65, {"value_type": "ip_grade"}) == "IP65"

    # canonical_filter_value normalises a boolean business token.
    assert canonical_filter_value("有", {"value_type": "boolean"}) is True

    # Store.runtime_parameters keeps owning the business -> model mapping.
    from app.store import Store
    db_path = ROOT / "data" / "_value_semantics_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    try:
        store.admin_upsert("parameters", {
            "parameter_id": "attr_x", "label": "布尔属性", "value_type": "boolean",
            "model_value_mapping_json": json.dumps({"有": 1, "无": 0, "无该属性": -1}),
        })
        encoded = store.runtime_parameters({"attr_x": "有"})
        assert encoded["attr_x"] == 1, encoded
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "业务值语义统一"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
