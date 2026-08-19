# -*- coding: utf-8 -*-
"""Legacy release packages without parameter_groups must pass hash and derive groups."""
from __future__ import print_function

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.product_releases import PACKAGE_FORMAT, ProductReleaseService  # noqa: E402
from app.store import Store  # noqa: E402


class StubRuntime(object):
    schema = {"product_code": "P1", "product_name": "产品1"}

    def manifest(self):
        return {"calculation_available": False}

    def feature_roles(self):
        return {"shared_features": [], "effectiveness_only_features": [], "price_only_features": []}

    def all_feature_specs(self):
        return []


def main():
    db_path = ROOT / "data" / "_product_release_legacy_package_test.db"
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
    store = Store(db_path, ROOT / "data" / "virtual_protocol_dataset.csv", StubRuntime())
    service = ProductReleaseService(store, StubRuntime())
    try:
        legacy_data = {
            "products": [{"product_code": "P_OLD", "product_name": "旧产品", "product_description": "", "enabled": 1}],
            "parameters": [
                {"parameter_id": "A1", "label": "A1", "parameter_group": "性能属性", "value_type": "number",
                 "min_value": 0, "max_value": 10, "search_type": "auto", "required": 0,
                 "auto_adjustable": 1, "decimal_places": 2, "display_order": 1, "enabled": 1, "model_bound": 0},
            ],
            "tags": [], "tag_rules": [], "couplings": [], "constraints": [], "agreements": [],
        }
        core = {
            "format": PACKAGE_FORMAT,
            "product_code": "P_OLD",
            "product_name": "旧产品",
            "data": legacy_data,
        }
        package = dict(core)
        package["payload_sha256"] = hashlib.sha256(
            ProductReleaseService._canonical_json(core).encode("utf-8")
        ).hexdigest()
        raw = (json.dumps(package, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

        release = service.import_package(raw)
        assert release["data"]["parameter_groups"] == [], release["data"]["parameter_groups"]
        assert all(p.get("parameter_group") == "性能属性" for p in release["data"]["parameters"] if p["parameter_id"] == "A1")

        # Activate: replace_from_datamaster derives groups from parameters.
        validation = service.validate(release["release_id"])
        assert validation["valid"], validation["errors"]
        service.activate(release["release_id"])
        boot = store.bootstrap()
        group_names = [g["group_name"] for g in boot["parameter_groups"]]
        assert "性能属性" in group_names and "其他" in group_names, group_names
    finally:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                candidate.unlink()

    print(json.dumps({"status": "PASS", "message": "旧发布包缺parameter_groups仍可通过hash校验并自动推导"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
