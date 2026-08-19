# -*- coding: utf-8 -*-
"""An empty generation result must not be cached as a successful completed task."""
from __future__ import print_function

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.generation_tasks import GenerationTaskManager  # noqa: E402


class _Runtime(object):
    schema = {"product_code": "P1"}

    def manifest(self):
        return {"model_versions": {"effectiveness": "e1", "price": "p1"}}


class _Store(object):
    def master_data_version(self):
        return "v1"


class _Sessions(object):
    def add_batch(self, session_id, items, fingerprint=None):
        return "BATCH-%d" % len(items), items


class _App(object):
    def __init__(self):
        self.runtime = _Runtime()
        self.store = _Store()
        self.sessions = _Sessions()
        self.calls = 0

    def _generate_sync(self, request, progress_callback=None):
        self.calls += 1
        if self.calls == 1:
            return {"candidates": [], "count": 0, "message": "empty first"}
        return {"candidates": [{"agreement_id": "G1", "params": {}}], "count": 1, "message": "ok"}


def _wait(mgr, task_id, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = mgr.get(task_id)
        if task and task["status"] in ("completed", "failed"):
            return task
        time.sleep(0.01)
    raise AssertionError("generation task did not finish: %s" % task_id)


def main():
    app = _App()
    mgr = GenerationTaskManager(app)
    request = {"session_id": "s1", "selected_tags": [], "max_price": 12,
               "indicator_filters": [], "indicator_filter_mode": "all", "count": 5,
               "target_protocol": None}

    first = mgr.start(request)
    first_task = _wait(mgr, first["task_id"])
    assert first_task["status"] == "completed", first_task
    assert first_task["result"]["empty_result"] is True, first_task["result"]
    assert first_task["candidates_count"] == 0

    # The same fingerprint must start a new task instead of returning the empty cache.
    second = mgr.start(request)
    assert second["task_id"] != first["task_id"], "empty completed task must not be reused"
    second_task = _wait(mgr, second["task_id"])
    assert second_task["status"] == "completed", second_task
    assert second_task["result"].get("empty_result") is False, second_task["result"]
    assert second_task["candidates_count"] == 1

    print(json.dumps({"status": "PASS", "message": "空结果不缓存，同条件再次生成会重新搜索"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
