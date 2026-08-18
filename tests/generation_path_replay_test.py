# -*- coding: utf-8 -*-
"""Replayable generation path: replaying nodes from the seed reaches final params."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator, _classify_move  # noqa: E402


def main():
    assert _classify_move("结构调整：是否液冷/冷却液流量") == "structural_move"
    assert _classify_move("工程联动：功率/散热") == "coupled_move"
    assert _classify_move("单属性：功率调整为120") == "single_move"

    gen = HistorySeededGenerator(None, None, None)

    # Synthetic chain mirroring the acceptance scenario:
    #   seed {a:1, b:10} -> Step1 a 1->0 (structural, projection b 10->-1) -> Step2 c 5->6
    r1 = {"params": {"a": 1, "b": 10, "c": 5},
          "generation_trace": {"node_id": "N1", "move_type": "single_move",
                               "move": {"changes": [{"parameter_id": "a", "before": None, "after": 1}]}}}
    r2 = {"params": {"a": 0, "b": -1, "c": 5},
          "generation_trace": {"node_id": "N2", "parent_node_id": "N1", "move_type": "structural_move",
                               "move": {"changes": [
                                   {"parameter_id": "a", "before": 1, "after": 0},
                                   {"parameter_id": "b", "before": 10, "after": -1},
                               ]}}}
    r3 = {"params": {"a": 0, "b": -1, "c": 6},
          "generation_trace": {"node_id": "N3", "parent_node_id": "N2", "move_type": "single_move",
                               "move": {"changes": [{"parameter_id": "c", "before": 5, "after": 6}]}}}

    node_map = {"N1": r1, "N2": r2, "N3": r3}
    path = gen._build_generation_path(r3, node_map)
    assert [p["node_id"] for p in path] == ["N1", "N2", "N3"], path

    # Replay: apply every node's changes in order and reach the final params.
    params = {"a": 1, "b": 10, "c": 5}
    for node in path:
        for change in (node.get("move") or {}).get("changes") or []:
            params[change["parameter_id"]] = change["after"]
    assert params == r3["params"], params

    print(json.dumps({"status": "PASS", "message": "generation_path可回放并到达最终参数"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
