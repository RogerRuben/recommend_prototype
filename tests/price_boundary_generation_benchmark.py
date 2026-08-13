# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import random
import shutil
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_generator import HistorySeededGenerator
from app.gflownet_generator import TabularTrajectoryBalanceGFlowNet
from app.model_runtime import IntegratedModelRuntime
from app.model_service_client import ModelServiceGateway, ServiceBackedRuntime
from app.product_releases import ProductReleaseService
from app.store import Store
from services.common.http_service import make_handler
from services.effectiveness_service.app import EffectivenessService, backend_from_package
from services.price_service.app import PriceService


OUT = ROOT / "outputs" / "019fb26c_basic_aircraft_door_lock_models_20260812"
SOURCE = ROOT / "outputs" / "019fb26c_basic_product_demo" / "basic_aircraft_door_lock_history_demo.xlsx"
PRODUCT_CODE = "AIRCRAFT_DOOR_LOCK_BASIC_DEMO"


def start_http(application):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(application))
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server, thread, "http://127.0.0.1:%d" % server.server_address[1]


def main():
    temp_root = Path(tempfile.mkdtemp(prefix="price_boundary_benchmark_"))
    servers = []
    try:
        bootstrap_runtime = IntegratedModelRuntime(ROOT / "models")
        bootstrap_store = Store(
            temp_root / "bootstrap.db", ROOT / "data" / "virtual_protocol_dataset.csv",
            bootstrap_runtime, temp_root / "bootstrap_backups",
        )
        analyzed = ProductReleaseService(bootstrap_store, bootstrap_runtime).analyze_history(
            SOURCE.name, SOURCE.read_bytes(), PRODUCT_CODE,
            "基础航空舱门锁（虚拟功能演示）", ["-1", "\\", "/"],
        )

        price = PriceService(OUT / "price" / "price_native_bundle.pkl", None)
        effect = EffectivenessService(
            backend_from_package(OUT / "effectiveness_runtime" / "effectiveness_runtime_manifest.json")
        )
        price_server, price_thread, price_url = start_http(price)
        effect_server, effect_thread, effect_url = start_http(effect)
        servers.extend([(price_server, price_thread), (effect_server, effect_thread)])
        remote = ServiceBackedRuntime(
            ModelServiceGateway(None, price_url, effect_url, timeout=30, fallback=False)
        )

        store = Store(
            temp_root / "benchmark.db", ROOT / "data" / "virtual_protocol_dataset.csv",
            remote, temp_root / "benchmark_backups",
        )
        data = dict((key, []) for key in (
            "products", "parameters", "tags", "tag_rules", "couplings", "constraints", "agreements"
        ))
        data["products"] = [{
            "product_code": PRODUCT_CODE, "product_name": "边界生成测试", "enabled": 1,
        }]
        data["parameters"] = [dict(item) for item in analyzed["data"]["parameters"]]
        data["agreements"] = [dict(item) for item in analyzed["data"]["agreements"]]
        store.replace_from_datamaster(data, evaluate_agreements=False, sync_model_contract=False)
        store.sync_model_schema()

        def decorate(evaluation, business_params, base_params=None):
            result = dict(evaluation)
            model_parameters = dict(result.get("parameters") or {})
            result["model_parameters"] = model_parameters
            result["parameters"] = store.business_parameters(model_parameters, business_params)
            result["rule_messages"] = store.assess_rules(result["parameters"], base_params)
            return result

        calls = {"single": 0, "batch": 0}

        def evaluate_one(params, base_params=None, target_protocol=None):
            calls["single"] += 1
            encoded = store.runtime_parameters(params)
            return decorate(remote.evaluate(encoded, target_protocol=target_protocol), params, base_params)

        def evaluate_batch(items):
            calls["batch"] += 1
            prepared = []
            for index, item in enumerate(items):
                prepared.append({
                    "candidate_id": item.get("candidate_id") or str(index),
                    "parameters": store.runtime_parameters(item.get("parameters") or {}),
                    "target_protocol": item.get("target_protocol"),
                })
            values = remote.evaluate_batch(prepared)
            return [
                decorate(value, items[index].get("parameters") or {}, items[index].get("base_parameters"))
                for index, value in enumerate(values)
            ]

        historical = store.historical_agreements()
        historical_prices = sorted(float(item["predicted_price_wan"]) for item in historical)
        minimum = historical_prices[0]
        maximum = historical_prices[-1]
        generator = HistorySeededGenerator(
            store, remote, evaluate_one, evaluate_batch_callback=evaluate_batch,
        )

        # A broad mixed-domain probe distinguishes search failure from a target
        # that the current price/effectiveness artifacts simply cannot reach.
        definitions = store.parameter_map()
        rng = random.Random(20260812)
        global_samples = []
        for index in range(1000):
            params = dict(historical[index % len(historical)]["params"])
            for key, definition in definitions.items():
                if key not in params or not definition.get("auto_adjustable", 1):
                    continue
                kind = generator._search_type(definition)
                allowed = generator._normalized_allowed_values(definition)
                if kind == "boolean":
                    params[key] = rng.choice([0, 1])
                elif kind in ("ordered_discrete", "unordered_enum") and allowed:
                    params[key] = rng.choice(allowed)
                elif kind in ("continuous", "integer"):
                    if definition.get("min_value") is None or definition.get("max_value") is None:
                        continue
                    lower = float(definition.get("min_value"))
                    upper = float(definition.get("max_value"))
                    value = rng.uniform(lower, upper)
                    params[key] = int(round(value)) if kind == "integer" else value
            generator._round_values(params, definitions)
            global_samples.append({"candidate_id": "GLOBAL-%04d" % index, "parameters": params})
        global_values = []
        calls["single"], calls["batch"] = 0, 0
        global_started = time.time()
        for offset in range(0, len(global_samples), 250):
            global_values.extend(evaluate_batch(global_samples[offset:offset + 250]))
        physically_accepted = [
            item for item in global_values if (item.get("physical_gate") or {}).get("passed") is not False
        ]
        global_probe = {
            "sample_count": len(global_values),
            "elapsed_seconds": round(time.time() - global_started, 3),
            "batch_calls": calls["batch"],
            "minimum_price_all_wan": round(min(float(item["predicted_price_wan"]) for item in global_values), 6),
            "physically_accepted_count": len(physically_accepted),
            "minimum_price_physically_accepted_wan": (
                round(min(float(item["predicted_price_wan"]) for item in physically_accepted), 6)
                if physically_accepted else None
            ),
        }
        scenarios = [
            ("below_history_1pct", minimum * 0.99),
            ("below_history_2pct", minimum * 0.98),
            ("below_history_3pct", minimum * 0.97),
            ("below_history_5pct", minimum * 0.95),
        ]
        report = {
            "historical_price_range_wan": [round(minimum, 6), round(maximum, 6)],
            "historical_prices_wan": historical_prices,
            "global_probe": global_probe,
            "scenarios": [],
        }
        deep_baseline_result = None
        for name, target in scenarios:
            calls["single"], calls["batch"] = 0, 0
            started = time.time()
            ratio = max(0.0, (minimum - target) / minimum)
            search_mode = "deep_extrapolation" if ratio > 0.030001 else "fast"
            result = generator.generate(
                {"max_price": target}, count=3, seed=20260812,
                budget=360 if search_mode == "deep_extrapolation" else 120,
                search_mode=search_mode,
            )
            if name == "below_history_5pct":
                deep_baseline_result = result
            elapsed = time.time() - started
            candidates = result.get("candidates") or []
            report["scenarios"].append({
                "name": name,
                "target_max_price_wan": round(target, 6),
                "search_mode": search_mode,
                "elapsed_seconds": round(elapsed, 3),
                "batch_calls": calls["batch"],
                "single_calls": calls["single"],
                "evaluated_count": result.get("evaluated_count"),
                "search_iterations": result.get("search_iterations"),
                "strict_filter_satisfied": result.get("strict_filter_satisfied"),
                "strict_candidate_count": result.get("strict_candidate_count"),
                "returned_count": len(candidates),
                "returned_prices_wan": [round(float(item["predicted_price_wan"]), 6) for item in candidates],
                "returned_strict": [bool(item.get("strict_filter_satisfied")) for item in candidates],
                "returned_best_effort": [bool(item.get("best_effort")) for item in candidates],
                "returned_extrapolation_warning_count": [len(item.get("extrapolation_warnings") or []) for item in candidates],
                "rejection_statistics": result.get("rejection_statistics"),
            })
        gfn_target = minimum * 0.95
        gfn_request = {"max_price": gfn_target}
        gfn_seeds = generator.select_seeds(
            gfn_request, max(8, min(16, len(historical))), historical=historical,
        )
        gfn_runs = []
        best_gfn_records = []
        for gfn_seed in (20260812, 20260813, 20260814):
            calls["single"], calls["batch"] = 0, 0
            gfn = TabularTrajectoryBalanceGFlowNet(
                generator, evaluate_batch, seed=gfn_seed,
            )
            gfn_result = gfn.explore(
                gfn_request, gfn_seeds, store.parameter_map(),
                max_evaluations=360, batch_size=36, max_steps=4, temperature=1.15,
            )
            gfn_records = gfn_result["records"]
            gfn_strict = [
                item for item in gfn_records
                if float(item["evaluation"].get("predicted_price_wan") or 1e99) <= gfn_target
                and (item["evaluation"].get("physical_gate") or {}).get("passed") is not False
                and not any(
                    message.get("severity") == "error" and message.get("source") != "anomaly"
                    for message in item["evaluation"].get("rule_messages") or []
                )
            ]
            diverse = []
            for item in gfn_records:
                if not diverse or min(
                    generator._normalized_distance(item["params"], old["params"], definitions)
                    for old in diverse
                ) >= 0.018:
                    diverse.append(item)
                if len(diverse) >= 3:
                    break
            run = {
                "seed": gfn_seed,
                "method": gfn_result.get("method"),
                "elapsed_seconds": round(gfn_result.get("elapsed_seconds") or 0.0, 3),
                "batch_calls": calls["batch"],
                "single_calls": calls["single"],
                "evaluated_count": gfn_result.get("evaluated_count"),
                "training_batches": gfn_result.get("training_batches"),
                "state_count": gfn_result.get("state_count"),
                "option_count": gfn_result.get("option_count"),
                "duplicate_trajectories": gfn_result.get("duplicate_trajectories"),
                "final_tb_loss": gfn_result.get("final_tb_loss"),
                "strict_candidate_count": len(gfn_strict),
                "minimum_price_wan": round(float(gfn_records[0]["evaluation"]["predicted_price_wan"]), 6) if gfn_records else None,
                "top_diverse_prices_wan": [
                    round(float(item["evaluation"]["predicted_price_wan"]), 6) for item in diverse
                ],
                "top_diverse_distances": [
                    round(generator._normalized_distance(diverse[i]["params"], diverse[j]["params"], definitions), 6)
                    for i in range(len(diverse)) for j in range(i + 1, len(diverse))
                ],
            }
            gfn_runs.append(run)
            if not best_gfn_records or (
                gfn_records and float(gfn_records[0]["evaluation"]["predicted_price_wan"])
                < float(best_gfn_records[0]["evaluation"]["predicted_price_wan"])
            ):
                best_gfn_records = gfn_records
        baseline_prices = [
            float(item["predicted_price_wan"])
            for item in (deep_baseline_result or {}).get("candidates") or []
        ]
        baseline_candidates = (deep_baseline_result or {}).get("candidates") or []
        baseline_distances = [
            round(generator._normalized_distance(
                baseline_candidates[i]["params"], baseline_candidates[j]["params"], definitions,
            ), 6)
            for i in range(len(baseline_candidates))
            for j in range(i + 1, len(baseline_candidates))
        ]
        # The hybrid keeps the strongest beam-search frontier point, then uses
        # GFlowNet samples only where they add material design-space diversity.
        hybrid = []
        if baseline_candidates:
            hybrid.append({
                "source": "deep_beam",
                "params": baseline_candidates[baseline_prices.index(min(baseline_prices))]["params"],
                "price": min(baseline_prices),
            })
        for record in best_gfn_records:
            if not hybrid or min(
                generator._normalized_distance(record["params"], old["params"], definitions)
                for old in hybrid
            ) >= 0.018:
                hybrid.append({
                    "source": "gflownet",
                    "params": record["params"],
                    "price": float(record["evaluation"]["predicted_price_wan"]),
                })
            if len(hybrid) >= 3:
                break
        hybrid_distances = [
            round(generator._normalized_distance(hybrid[i]["params"], hybrid[j]["params"], definitions), 6)
            for i in range(len(hybrid)) for j in range(i + 1, len(hybrid))
        ]
        valid_gfn_prices = [item["minimum_price_wan"] for item in gfn_runs if item["minimum_price_wan"] is not None]
        report["gflownet_comparison_5pct"] = {
            "target_max_price_wan": round(gfn_target, 6),
            "same_unique_evaluation_budget": 360,
            "baseline": {
                "method": (deep_baseline_result or {}).get("generation_method"),
                "evaluated_count": (deep_baseline_result or {}).get("evaluated_count"),
                "strict_candidate_count": (deep_baseline_result or {}).get("strict_candidate_count"),
                "minimum_returned_price_wan": round(min(baseline_prices), 6) if baseline_prices else None,
                "returned_pairwise_distances": baseline_distances,
            },
            "gflownet": {
                "runs": gfn_runs,
                "minimum_price_range_wan": [min(valid_gfn_prices), max(valid_gfn_prices)],
                "mean_minimum_price_wan": round(sum(valid_gfn_prices) / len(valid_gfn_prices), 6),
                "runs_with_strict_candidate": sum(item["strict_candidate_count"] > 0 for item in gfn_runs),
            },
            "hybrid_candidate_set": {
                "note": "keep beam frontier winner, then fill diversity slots from the best GFlowNet run",
                "prices_wan": [round(item["price"], 6) for item in hybrid],
                "sources": [item["source"] for item in hybrid],
                "pairwise_distances": hybrid_distances,
            },
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for server, thread in servers:
            server.shutdown()
            server.server_close()
            thread.join(5)
        shutil.rmtree(str(temp_root), ignore_errors=True)


if __name__ == "__main__":
    main()
