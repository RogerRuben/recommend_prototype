# -*- coding: utf-8 -*-
from __future__ import print_function

import hashlib
import json
import threading
import time
import traceback
import uuid


class GenerationTaskManager(object):
    def __init__(self, application, ttl_seconds=3600):
        self.app = application
        self.ttl = ttl_seconds
        self.lock = threading.RLock()
        self.tasks = {}
        self.by_fingerprint = {}

    def fingerprint(self, request):
        # sort_by / page / page_size / source_mode are presentation-only and must
        # never trigger a new generation: they re-rank an existing batch.
        relevant = dict((key, request.get(key)) for key in (
            "session_id", "selected_tags", "max_price", "min_capability", "min_cost_effectiveness",
            "min_feasibility", "indicator_filter_mode", "indicator_filters", "count",
            "target_protocol"
        ))
        # Frozen parameters change which seed values are locked during search, so
        # a different frozen set must never reuse a previously cached batch.
        relevant["frozen_parameters"] = sorted(set(request.get("frozen_parameters") or []))
        relevant["product_code"] = self.app.runtime.schema["product_code"]
        relevant["master_data_version"] = self.app.store.master_data_version()
        relevant["models"] = self.app.runtime.manifest().get("model_versions") or {
            "effectiveness": self.app.runtime.manifest()["effectiveness"]["model_version"],
            "price": self.app.runtime.manifest()["price"]["model_version"],
        }
        raw = json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def start(self, request, force=False):
        self.cleanup()
        req = dict(request or {})
        session_id = str(req.get("session_id") or "default")
        req["session_id"] = session_id
        req["count"] = max(1, min(int(req.get("count") or 10), 30))
        fp = self.fingerprint(req)
        with self.lock:
            old_id = self.by_fingerprint.get(fp)
            if old_id and old_id in self.tasks and not force:
                task = self.tasks[old_id]
                if task["status"] == "completed":
                    return self.public(task)
                if task["status"] in ("queued", "running"):
                    return self.public(task)
                # A failed cached task must not permanently block the same request.
                self.tasks.pop(old_id, None)
                if self.by_fingerprint.get(fp) == old_id:
                    self.by_fingerprint.pop(fp, None)
            task_id = "GENTASK-" + uuid.uuid4().hex[:12].upper()
            task = {
                "task_id": task_id,
                "fingerprint": fp,
                "session_id": session_id,
                "status": "queued",
                "progress": 0,
                "message": "已进入生成队列",
                "search_profile": dict(req.get("search_profile") or {}),
                "created_at": time.time(),
                "updated_at": time.time(),
                "request": req,
                "result": None,
                "error": None,
            }
            self.tasks[task_id] = task
            self.by_fingerprint[fp] = task_id
            thread = threading.Thread(target=self._worker, args=(task_id,), name=task_id)
            thread.daemon = True
            thread.start()
            return self.public(task)

    def _worker(self, task_id):
        with self.lock:
            task = self.tasks[task_id]
            profile = task.get("search_profile") or {}
            task.update(
                status="running", progress=5 if profile.get("deep_exploration") else 8,
                message=profile.get("warning") or "正在选择相似历史方案", updated_at=time.time(),
            )
        try:
            def update(progress, message):
                with self.lock:
                    task = self.tasks.get(task_id)
                    if task:
                        task.update(progress=int(progress), message=str(message), updated_at=time.time())
            result = self.app._generate_sync(self.tasks[task_id]["request"], progress_callback=update)
            session_id = self.tasks[task_id]["session_id"]
            batch_id, prepared = self.app.sessions.add_batch(session_id, result.get("candidates", []), fingerprint=self.tasks[task_id].get("fingerprint"))
            result["batch_id"] = batch_id
            result["candidates"] = prepared
            with self.lock:
                self.tasks[task_id].update(status="completed", progress=100, message=result.get("message") or "生成完成", result=result, batch_id=batch_id, updated_at=time.time())
        except Exception as exc:
            traceback.print_exc()
            with self.lock:
                self.tasks[task_id].update(status="failed", progress=100, message="生成失败", error={"type":type(exc).__name__,"message":str(exc)}, updated_at=time.time())

    def get(self, task_id):
        with self.lock:
            task = self.tasks.get(str(task_id))
            return self.public(task) if task else None

    def public(self, task):
        if not task:
            return None
        payload = dict((key, task.get(key)) for key in ("task_id","status","progress","message","session_id","created_at","updated_at","error","fingerprint","batch_id","search_profile"))
        if task.get("status") == "completed":
            result = task.get("result") or {}
            payload["result"] = dict((key,result.get(key)) for key in (
                "count", "requested_count", "evaluated_count", "all_records_count", "usable_count",
                "best_effort_candidate_count", "final_selected_count", "fallback_used",
                "strict_filter_satisfied", "strict_candidate_count", "best_effort_used", "rejection_statistics",
                "seed_agreements", "message", "batch_id", "search_profile", "search_warning",
                "search_iterations", "generation_method"
            ))
            payload["candidates_count"] = len(result.get("candidates") or [])
        return payload

    def invalidate_all(self):
        with self.lock:
            self.tasks.clear()
            self.by_fingerprint.clear()

    def invalidate_session(self, session_id):
        session_id = str(session_id)
        with self.lock:
            targets = [key for key, value in self.tasks.items() if str(value.get("session_id")) == session_id]
            for key in targets:
                fp = self.tasks[key].get("fingerprint")
                self.tasks.pop(key, None)
                if self.by_fingerprint.get(fp) == key:
                    self.by_fingerprint.pop(fp, None)

    def cleanup(self):
        cutoff = time.time() - self.ttl
        with self.lock:
            stale = [key for key,value in self.tasks.items() if value.get("updated_at",0)<cutoff and value.get("status") in ("completed","failed")]
            for key in stale:
                fp = self.tasks[key].get("fingerprint")
                self.tasks.pop(key,None)
                if self.by_fingerprint.get(fp)==key:self.by_fingerprint.pop(fp,None)
