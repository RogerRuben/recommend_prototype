# -*- coding: utf-8 -*-
"""Regression test: the expert-weighted tree must survive a cross-process pickle.

The training notebook used to define ``ExpertWeightedTreeRegressor`` in
``__main__``, which made the exported price bundle un-loadable by the
independent price service.  It now lives in
``services.price_service.expert_tree`` so a fresh interpreter can unpickle it.
"""
from __future__ import print_function

import json
import os
import pickle
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import sklearn  # noqa: F401
    import pandas as pd  # noqa: F401
    import numpy as np  # noqa: F401
except Exception:
    print(json.dumps({"status": "SKIP", "message": "sklearn/pandas/numpy not installed"}, ensure_ascii=False))
    raise SystemExit(0)

from services.price_service.expert_tree import ExpertWeightedTreeRegressor


def main():
    # Fit a tiny tree on toy data so the pickled object has a real root_ tree.
    X = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], "b": [5.0, 4.0, 3.0, 2.0, 1.0, 0.0]})
    y = np.log(np.array([10.0, 12.0, 11.0, 20.0, 21.0, 22.0]))
    model = ExpertWeightedTreeRegressor(max_depth=3, min_samples_leaf=1, lambda_expert=0.5, expert_map={"a": 5, "b": 2})
    model.fit(X, y)

    blob = pickle.dumps(model)
    # The class must be referenced by its importable module path, never __main__.
    assert b"expert_tree" in blob, "pickle must reference services.price_service.expert_tree"

    with tempfile.TemporaryDirectory(prefix="expert_tree_pickle_") as raw:
        path = Path(raw) / "model.pkl"
        path.write_bytes(blob)
        code = (
            "import pickle,sys,json\n"
            "m=pickle.load(open(%r,'rb'))\n"
            "import pandas as pd\n"
            "pred=m.predict(pd.DataFrame({'a':[1.5],'b':[3.5]}))\n"
            "print(json.dumps({'module':type(m).__module__,'pred':float(pred[0])}))\n"
            % str(path)
        )
        out = subprocess.check_output([sys.executable, "-c", code], cwd=str(ROOT))
        payload = json.loads(out.decode("utf-8"))
        assert payload["module"] == "services.price_service.expert_tree", payload
        assert isinstance(payload["pred"], float), payload

    print(json.dumps({"status": "PASS", "module": "services.price_service.expert_tree"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
