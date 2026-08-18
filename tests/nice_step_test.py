# -*- coding: utf-8 -*-
"""Engineering-friendly nice step and parameter canonicalization."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.value_semantics import canonicalize_parameter_value, nice_engineering_step  # noqa: E402


def main():
    assert nice_engineering_step(0.0589) == 0.05, nice_engineering_step(0.0589)
    assert nice_engineering_step(1.73) == 2, nice_engineering_step(1.73)
    assert nice_engineering_step(13.8) == 10, nice_engineering_step(13.8)
    assert nice_engineering_step(0.5) == 0.5, nice_engineering_step(0.5)

    # A continuous parameter moving by a nice step lands on a readable grid.
    step = nice_engineering_step(0.0589)
    assert round(4.5 - step, 3) == 4.45, round(4.5 - step, 3)

    # Canonicalization by definition.
    continuous = {"parameter_id": "w", "value_type": "number", "decimal_places": 3}
    assert canonicalize_parameter_value(continuous, 4.44112137) == 4.441
    integer = {"parameter_id": "n", "value_type": "number", "search_type": "integer"}
    assert canonicalize_parameter_value(integer, 12.7) == 13
    boolean = {"parameter_id": "b", "value_type": "boolean"}
    assert canonicalize_parameter_value(boolean, "1.0") == 1.0

    print(json.dumps({"status": "PASS", "message": "工程友好步长吸附到1/2/2.5/5/10网格"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
