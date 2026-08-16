# -*- coding: utf-8 -*-
"""Offline comparison using the REAL ``HistorySeededGenerator`` (beam search)
against the TB-GFlowNet diversity supplement.

This is a research/validation harness, **not** wired into the recommendation
workflow.  Both generators share one mock ``Store`` / runtime / evaluator, so
the GFlowNet reward is derived from the *same* evaluation the beam search uses.

Reports, for two scenarios (targets inside vs outside the historical envelope):
efficiency (evaluation calls), filter satisfaction (strict vs best-effort) and
diversity (distinct candidates), plus a merge-and-dedupe demonstration.
"""
from __future__ import print_function

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.gflownet_generator import TabularTBGFlowNet, merge_beam_gflownet  # noqa: E402
from app.local_generator import HistorySeededGenerator  # noqa: E402


# --------------------------------------------------------------------------- #
# Synthetic product (same attributes used by both generators)
# --------------------------------------------------------------------------- #
ATTRIBUTES = [
    {"id": "attr_001", "label": "额定载荷", "values": list(range(11))},
    {"id": "attr_002", "label": "运行速度", "values": list(range(11))},
    {"id": "attr_003", "label": "材料类型", "values": [0, 1, 2]},
]
ENVELOPE = {"attr_001": (3, 7), "attr_002": (3, 7), "attr_003": (0, 1)}
FEASIBILITY_GATE = 0.65

PARAMETER_DEFINITIONS = {
    "attr_001": {"parameter_id": "attr_001", "label": "额定载荷", "value_type": "number",
                 "search_type": "integer", "min_value": 0, "max_value": 10,
                 "decimal_places": 0, "enabled": 1, "auto_adjustable": 1,
                 "allowed_values_json": None},
    "attr_002": {"parameter_id": "attr_002", "label": "运行速度", "value_type": "number",
                 "search_type": "integer", "min_value": 0, "max_value": 10,
                 "decimal_places": 0, "enabled": 1, "auto_adjustable": 1,
                 "allowed_values_json": None},
    "attr_003": {"parameter_id": "attr_003", "label": "材料类型", "value_type": "enum",
                 "search_type": "ordered_discrete", "min_value": None, "max_value": None,
                 "decimal_places": 0, "enabled": 1, "auto_adjustable": 1,
                 "allowed_values_json": json.dumps([0, 1, 2])},
}

SEEDS = [
    {"agreement_id": "H-01", "params": {"attr_001": 3, "attr_002": 4, "attr_003": 0}, "tags": []},
    {"agreement_id": "H-02", "params": {"attr_001": 4, "attr_002": 5, "attr_003": 1}, "tags": []},
    {"agreement_id": "H-03", "params": {"attr_001": 5, "attr_002": 3, "attr_003": 0}, "tags": []},
    {"agreement_id": "H-04", "params": {"attr_001": 6, "attr_002": 6, "attr_003": 1}, "tags": []},
    {"agreement_id": "H-05", "params": {"attr_001": 7, "attr_002": 4, "attr_003": 0}, "tags": []},
    {"agreement_id": "H-06", "params": {"attr_001": 4, "attr_002": 7, "attr_003": 1}, "tags": []},
    {"agreement_id": "H-07", "params": {"attr_001": 5, "attr_002": 5, "attr_003": 0}, "tags": []},
    {"agreement_id": "H-08", "params": {"attr_001": 6, "attr_002": 7, "attr_003": 1}, "tags": []},
]


# --------------------------------------------------------------------------- #
# Mock Store / runtime / evaluator shared by both generators
# --------------------------------------------------------------------------- #
def evaluate(params):
    a = params["attr_001"]
    b = params["attr_002"]
    c = params["attr_003"]
    capability = 40.0 + 4.0 * a + 3.0 * b + 5.0 * c
    price = 2.0 + 0.6 * a + 0.5 * b + 1.5 * c
    ood = 0.0
    ood += max(0.0, ENVELOPE["attr_001"][0] - a) + max(0.0, a - ENVELOPE["attr_001"][1])
    ood += max(0.0, ENVELOPE["attr_002"][0] - b) + max(0.0, b - ENVELOPE["attr_002"][1])
    ood += 2.0 if c not in ENVELOPE["attr_003"] else 0.0
    feasibility = max(0.0, 1.0 - 0.15 * ood)
    return {"capability_score": capability, "predicted_price_wan": price,
            "feasibility_probability": feasibility, "in_domain": ood == 0.0}


def mock_evaluate(params, base_params=None, target_protocol=None):
    """Same evaluation the production ``_evaluate_with_rules`` would return."""
    ev = evaluate(params)
    feasibility = ev["feasibility_probability"]
    gate_passed = feasibility >= FEASIBILITY_GATE
    anomaly_status = "in_domain" if ev["in_domain"] else (
        "caution" if feasibility >= FEASIBILITY_GATE else "out_of_domain")
    return {
        "predicted_price_wan": ev["predicted_price_wan"],
        "price_interval_wan": [ev["predicted_price_wan"], ev["predicted_price_wan"]],
        "capability_score": ev["capability_score"],
        "conservative_capability_score": ev["capability_score"],
        "protocol_score_interval": [ev["capability_score"], ev["capability_score"]],
        "support_at_80": None,
        "support_at_100": None,
        "score_uncertainty_width": 0.0,
        "feasibility_probability": feasibility,
        "physical_gate": {
            "passed": gate_passed,
            "decision": "pass" if gate_passed else "reject_low_feasibility_probability",
            "probability": feasibility,
            "probability_threshold": FEASIBILITY_GATE,
        },
        "cost_effectiveness": ev["capability_score"] / max(ev["predicted_price_wan"], 1e-9),
        "parameters": dict(params),
        "anomaly_assessment": {
            "status": anomaly_status,
            "is_anomaly": anomaly_status != "in_domain",
            "score": round(1.0 - feasibility, 4),
            "items": [],
        },
        "rule_messages": [],
        "coupling_assessments": [],
        "hard_risk_reasons": [],
        "learned_boundary_violations": [],
        "risk_contributors": [],
        "requirement_assessment": {},
        "model_versions": {"effectiveness": "mock", "price": "mock"},
        "model_audit": {"effectiveness": {}, "price": {}},
    }


def mock_evaluate_batch(items):
    return [mock_evaluate(item.get("parameters") or {}, item.get("base_parameters")) for item in items]


class _MockEffectiveness(object):
    couplings = []
    coupling_edges = []
    learned_boundaries = []


class _MockRuntime(object):
    schema = {"product_code": "SYNTH", "product_name": "合成产品"}
    effectiveness = _MockEffectiveness()


class _MockStore(object):
    def parameter_map(self):
        return PARAMETER_DEFINITIONS

    def historical_agreements(self, target_protocol=None):
        return SEEDS

    def tag_map(self):
        return {}

    def tag_rule_branches(self, selected_tags, max_branches=24):
        return [{"rules": [], "tag_groups": {}, "unresolved_tags": []}]

    def coupling_rows(self):
        return []

    def constraint_rows(self):
        return []

    def derive_tags(self, params, evaluation=None, inherited_tags=None):
        return []

    def tag_evidence(self, params, evaluation=None, inherited_tags=None):
        return {}

    def _positioning(self, tags):
        return "通用技术方案"

    @staticmethod
    def _compare(left, operator, right):
        if operator == "gt":
            return left > right
        if operator == "gte":
            return left >= right
        if operator == "lt":
            return left < right
        if operator == "lte":
            return left <= right
        if operator == "eq":
            return abs(left - right) <= 1e-9
        return False


def _generator():
    return HistorySeededGenerator(_MockStore(), _MockRuntime(), mock_evaluate, mock_evaluate_batch)


# --------------------------------------------------------------------------- #
# Beam (real) + GFlowNet (reward from the same evaluator)
# --------------------------------------------------------------------------- #
def run_beam(req, count=5, budget=500):
    result = _generator().generate(
        dict(req, selected_tags=[], indicator_filters=[], count=count),
        count=count, seed=7, budget=budget, search_mode="fast",
    )
    candidates = result.get("candidates", [])
    return {
        "evaluations": result.get("evaluated_count", 0),
        "candidates": candidates,
        "strict": [c for c in candidates if c.get("strict_filter_satisfied")],
        "best_effort": [c for c in candidates if not c.get("strict_filter_satisfied")],
    }


def run_gflownet(req, train_episodes=3000, sample_n=400, rng_seed=7):
    def reward(params):
        ev = mock_evaluate(params)
        satisfied = (
            ev["capability_score"] >= req["min_capability"]
            and ev["predicted_price_wan"] <= req["max_price"]
        )
        base = 100.0 if satisfied else 0.5
        return base * (0.2 + 0.8 * ev["feasibility_probability"])

    gf = TabularTBGFlowNet(ATTRIBUTES, [s["params"] for s in SEEDS], reward, seed=rng_seed)
    gf.train(episodes=train_episodes, learning_rate=0.05)
    samples = gf.sample_unique(n=sample_n, max_attempts=sample_n * 3)
    strict, best_effort = [], []
    for params, _r in samples:
        ev = mock_evaluate(params)
        satisfied = ev["capability_score"] >= req["min_capability"] and ev["predicted_price_wan"] <= req["max_price"]
        if not satisfied:
            continue
        if ev["feasibility_probability"] >= FEASIBILITY_GATE:
            strict.append(params)
        else:
            best_effort.append(params)
    return {
        "reward_calls": train_episodes + len(samples),
        "sampled": len(samples),
        "strict": strict,
        "best_effort": best_effort,
    }


def _uniq_keys(items):
    seen = set()
    for item in items:
        params = item.get("params", item) if isinstance(item, dict) else item
        seen.add(tuple(sorted((str(k), str(v)) for k, v in params.items())))
    return len(seen)


def main():
    scenarios = [
        ("历史经验内（目标在历史包络内）", {"min_capability": 90.0, "max_price": 13.0}),
        ("历史经验外（目标需要外推）", {"min_capability": 108.0, "max_price": 16.0}),
    ]
    for name, req in scenarios:
        beam = run_beam(req)
        gf = run_gflownet(req)
        merged = merge_beam_gflownet(beam["candidates"], [(p, 0.0) for p in gf["strict"] + gf["best_effort"]])
        print("=" * 72)
        print("场景：%s" % name)
        print("  需求：最低效能 %.0f，最高价格 %.1f 万元" % (req["min_capability"], req["max_price"]))
        print("  Beam Search：模型评价 %d 次 → 严格 %d 个、探索 %d 个（去重）" % (
            beam["evaluations"], _uniq_keys(beam["strict"]), _uniq_keys(beam["best_effort"])))
        print("  GFlowNet   ：奖励调用 %d 次 → 采样 %d 个，严格 %d 个、探索 %d 个（去重）" % (
            gf["reward_calls"], gf["sampled"], _uniq_keys(gf["strict"]), _uniq_keys(gf["best_effort"])))
        print("  合并去重后：%d 个候选（Beam %d + GFlowNet 新增 %d）" % (
            len(merged), _uniq_keys(beam["candidates"]),
            max(0, len(merged) - _uniq_keys(beam["candidates"]))))
    print("=" * 72)


if __name__ == "__main__":
    main()
