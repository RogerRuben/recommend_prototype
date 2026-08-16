# -*- coding: utf-8 -*-
"""One-time DataMaster cleanup for the AIRCRAFT_DOOR_LOCK_BASIC_DEMO acceptance state.

Removes model-mirrored fields left over from the previous servo/actuator demo
(``model_bound=1`` rows) and adds the business-enum -> model-number mappings that
the price service needs so Chinese business values are encoded before the HTTP
call.  Keeps the operator-maintained ``model_bound=0`` field set (attr_001..attr_007).

Idempotent: running it again is a no-op after the first successful run.
"""
from __future__ import print_function

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "protocol_demo.db"

MAPPINGS = {
    "attr_002": {"0": 0, "1": 1},
    "attr_003": {"高强铝合金": 0, "不锈钢": 1, "钛合金": 2},
    "attr_004": {"机械插销": 0, "旋转锁舌": 1, "楔形锁块": 2},
}


def main():
    if not DB.is_file():
        raise SystemExit("数据库不存在: %s" % DB)
    backup_dir = ROOT / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = backup_dir / ("protocol_demo_%s_doordlock_cleanup.db" % stamp)
    shutil.copy2(str(DB), str(backup))

    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    try:
        stale = [str(r["parameter_id"]) for r in conn.execute(
            "SELECT parameter_id FROM parameter_definitions WHERE model_bound=1 ORDER BY display_order"
        )]
        print("stale model_bound=1 fields (%d): %s" % (len(stale), ", ".join(stale)))

        if stale:
            placeholders = ",".join("?" for _ in stale)
            # Drop orphaned business rules that pointed at the stale fields.
            for table, column in [
                ("tag_rules", "parameter_id"),
                ("indicator_couplings", "parameter_a"),
                ("indicator_couplings", "parameter_b"),
                ("constraint_rules", "left_parameter"),
                ("constraint_rules", "right_parameter"),
            ]:
                cursor = conn.execute(
                    "DELETE FROM %s WHERE %s IN (%s)" % (table, column, placeholders), stale
                )
                if cursor.rowcount:
                    print("deleted %d rows from %s.%s" % (cursor.rowcount, table, column))
            cursor = conn.execute(
                "DELETE FROM parameter_definitions WHERE model_bound=1"
            )
            print("deleted %d parameter_definitions rows" % cursor.rowcount)

        for parameter_id, mapping in MAPPINGS.items():
            row = conn.execute(
                "SELECT parameter_id, value_type, allowed_values_json, model_value_mapping_json "
                "FROM parameter_definitions WHERE parameter_id=?", (parameter_id,)
            ).fetchone()
            if row is None:
                print("skip %s: not present" % parameter_id)
                continue
            encoded = json.dumps(mapping, ensure_ascii=False)
            current = row["model_value_mapping_json"]
            if current == encoded:
                print("skip %s: mapping already set" % parameter_id)
                continue
            conn.execute(
                "UPDATE parameter_definitions SET model_value_mapping_json=? WHERE parameter_id=?",
                (encoded, parameter_id),
            )
            print("set mapping %s -> %s (was %r)" % (parameter_id, mapping, current))

        conn.commit()

        remaining = [dict(r) for r in conn.execute(
            "SELECT parameter_id, label, value_type, model_bound, enabled FROM parameter_definitions ORDER BY display_order"
        )]
        print("remaining fields (%d):" % len(remaining))
        for r in remaining:
            print("  %s | %s | %s | model_bound=%s enabled=%s" % (
                r["parameter_id"], r["label"], r["value_type"], r["model_bound"], r["enabled"]
            ))
        print("backup:", backup)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
