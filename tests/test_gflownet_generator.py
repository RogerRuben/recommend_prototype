# -*- coding: utf-8 -*-
from __future__ import print_function

import unittest

from app.gflownet_generator import TabularTrajectoryBalanceGFlowNet


class _FakeGenerator(object):
    def __init__(self):
        self.finalized = 0

    @staticmethod
    def _local_statistics(seeds, definitions):
        return [], {}, dict((key, 1.0) for key in definitions), {}

    @staticmethod
    def _search_type(definition):
        return definition.get("data_type", "continuous")

    @staticmethod
    def _attribute_neighbors(current, definition, std, scale,
                             include_bounds=False, exhaustive_discrete=False):
        if definition.get("data_type") == "boolean":
            return [0, 1]
        return [0.0, 2.5, 5.0, 7.5, 10.0]

    @staticmethod
    def _value_equal(left, right, definition):
        return left == right

    def _finalize_params(self, params, base, locked, definitions, soft_strength=0.24):
        self.finalized += 1
        params["x"] = max(0.0, min(10.0, float(params["x"])))
        params["flag"] = int(bool(params["flag"]))
        return [], []


class GFlowNetGeneratorTest(unittest.TestCase):
    def test_state_is_independent_of_edit_order(self):
        explorer = TabularTrajectoryBalanceGFlowNet(_FakeGenerator(), lambda items: [])
        self.assertEqual(
            explorer._state_key(1, {"x": 2.5, "flag": 1}),
            explorer._state_key(1, {"flag": 1, "x": 2.5}),
        )

    def test_explore_obeys_unique_budget_and_uses_joint_evaluator(self):
        generator = _FakeGenerator()
        batches = []

        def evaluate_batch(items):
            batches.append(list(items))
            result = []
            for item in items:
                params = item["parameters"]
                result.append({
                    "predicted_price_wan": 1.0 + float(params["x"]) + float(params["flag"]),
                    "feasibility_probability": 0.9,
                    "capability_score": 80.0,
                    "conservative_capability_score": 75.0,
                    "physical_gate": {"passed": True},
                    "rule_messages": [],
                })
            return result

        explorer = TabularTrajectoryBalanceGFlowNet(generator, evaluate_batch, seed=17)
        result = explorer.explore(
            {"max_price": 2.0},
            [
                {"agreement_id": "A", "params": {"x": 10.0, "flag": 1}},
                {"agreement_id": "B", "params": {"x": 5.0, "flag": 0}},
            ],
            {
                "x": {"enabled": 1, "auto_adjustable": 1, "data_type": "continuous"},
                "flag": {"enabled": 1, "auto_adjustable": 1, "data_type": "boolean"},
            },
            max_evaluations=20,
            batch_size=8,
            max_steps=2,
        )

        self.assertGreater(result["evaluated_count"], 0)
        self.assertLessEqual(result["evaluated_count"], 20)
        self.assertEqual(result["method"], "tabular_trajectory_balance_gflownet_experiment")
        self.assertGreater(generator.finalized, 0)
        self.assertTrue(batches)
        prices = [item["evaluation"]["predicted_price_wan"] for item in result["records"]]
        self.assertEqual(prices, sorted(prices))


if __name__ == "__main__":
    unittest.main()
