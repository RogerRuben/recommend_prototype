# -*- coding: utf-8 -*-
"""Manual tags are human facts: preserved when inherited, never silently dropped."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.store import Store  # noqa: E402


class StubRuntime(object):
    def manifest(self):
        return {"calculation_available": False}

    def feature_roles(self):
        return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}

    def all_feature_specs(self):
        return []


def main():
    db_path = ROOT / "data" / "_manual_tag_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    try:
        store.admin_upsert("tags", {"tag_id": "TAG-MANUAL", "tag_name": "人工标签", "derivation_mode": "manual", "weight": 1.0})
        store.admin_upsert("tags", {"tag_id": "TAG-RULE", "tag_name": "规则标签", "derivation_mode": "rule", "weight": 1.0})

        # Inherited manual tag is preserved.
        derived = store.derive_tags({}, {}, ["TAG-MANUAL", "TAG-RULE"])
        assert "TAG-MANUAL" in derived, derived
        # A manual tag that was never confirmed is not derived from parameters.
        derived2 = store.derive_tags({}, {}, [])
        assert "TAG-MANUAL" not in derived2, derived2

        # tag_evidence reflects the manual/inherited distinction.
        ev = store.tag_evidence({}, {}, ["TAG-MANUAL"])
        assert ev["TAG-MANUAL"]["matched"] is True
        assert ev["TAG-MANUAL"]["status"] == "manual_confirmed"
        ev2 = store.tag_evidence({}, {}, [])
        assert ev2["TAG-MANUAL"]["matched"] is False
        assert ev2["TAG-MANUAL"]["status"] == "expert_confirmation_required"

        print(json.dumps({"status": "PASS", "message": "人工维护Tag被继承时保留，未确认时不派生"}, ensure_ascii=False))
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()


if __name__ == "__main__":
    main()
