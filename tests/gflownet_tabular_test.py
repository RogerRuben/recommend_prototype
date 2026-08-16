# -*- coding: utf-8 -*-
"""Standalone smoke/behaviour test for the experimental TB-GFlowNet.

Verifies the sampler learns to concentrate probability on the highest-reward
terminal object (P(x) ∝ R(x)) without being wired into the recommendation flow.
"""
from __future__ import print_function

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.gflownet_generator import TabularTBGFlowNet  # noqa: E402


def main():
    attributes = [
        {"id": "attr_a", "label": "属性A", "values": [0, 1, 2]},
        {"id": "attr_b", "label": "属性B", "values": [0, 1]},
    ]
    seeds = [
        {"attr_a": 0, "attr_b": 0},
        {"attr_a": 1, "attr_b": 1},
    ]

    def reward(params):
        # The "best" object is attr_a=2 and attr_b=1.
        return 10.0 if (params["attr_a"] == 2 and params["attr_b"] == 1) else 1.0

    gf = TabularTBGFlowNet(attributes, seeds, reward, seed=42)
    losses = gf.train(episodes=800, learning_rate=0.05)

    # Loss should trend down from the initial value.
    assert losses[-1] < losses[0], (losses[0], losses[-1])

    samples = [gf.sample_trajectory()[0] for _ in range(2000)]
    counts = Counter((s["attr_a"], s["attr_b"]) for s in samples)
    best = counts[(2, 1)]
    # Uniform over the 6 reachable terminal objects would be ~333/2000; the
    # learned sampler should over-sample the rewarded object substantially.
    assert best > 600, dict(counts)
    assert best > counts[(0, 0)], dict(counts)

    print(json.dumps({
        "status": "PASS",
        "best_frequency": round(best / 2000.0, 3),
        "initial_loss": round(losses[0], 4),
        "final_loss": round(losses[-1], 4),
        "top_counts": dict(("a=%s,b=%s" % key, value) for key, value in counts.most_common(3)),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
