# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import math
import pickle
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.price_service.export_native_price_bundle import export_from_notebook
from services.price_service.native_bundle import load_bundle, predict
from services.price_service.app import PriceService


class Column(object):
    def __init__(self, values):
        self.values = list(values)
    def min(self):
        return min(self.values)
    def max(self):
        return max(self.values)
    def mean(self):
        return sum(self.values) / float(len(self.values))


class Frame(object):
    def __init__(self, columns, rows):
        self.columns = list(columns)
        self._data = dict((name, Column([row[i] for row in rows])) for i, name in enumerate(columns))
    def __getitem__(self, key):
        return self._data[key]


class IdentityScaler(object):
    def transform(self, rows):
        if hasattr(rows, "rows"):
            return rows.rows
        return rows


class ConstantLogModel(object):
    def __init__(self, native_price):
        self.value = math.log(float(native_price))
    def predict(self, rows):
        try:
            count = len(rows)
        except Exception:
            count = 1
        return [self.value] * count


def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        # Notebook memory deliberately contains an extra model. Only the three
        # actually saved files may be exported in saved_files mode.
        saved = {
            "xgb.pkl": ConstantLogModel(10.0),
            "svr.pkl": ConstantLogModel(20.0),
            "gbdt.pkl": ConstantLogModel(40.0),
        }
        for filename, model in saved.items():
            with (root / filename).open("wb") as handle:
                pickle.dump(model, handle, protocol=4)

        namespace = {
            "X_train": Frame(["A", "B"], [[1, 2], [3, 4]]),
            "scaler": IdentityScaler(),
            "lasso_model": ConstantLogModel(999.0),
            "weights": [1, 2, 3, 4, 5, 6, 7],
        }
        output = root / "price_native_bundle.pkl"
        bundle = export_from_notebook(
            namespace,
            output=output,
            product_code="HOTFIX_TEST",
            target_divisor_to_wan=1,
            model_source="saved_files",
            saved_model_dir=root,
        )
        assert list(bundle["models"].keys()) == ["xgboost", "svr", "gbdt"]
        assert [x["name"] for x in bundle["ensemble"]["members"]] == ["xgboost", "svr", "gbdt"]
        expected_weights = [3.0 / 16.0, 6.0 / 16.0, 7.0 / 16.0]
        actual_weights = [x["weight"] for x in bundle["ensemble"]["members"]]
        assert max(abs(a - b) for a, b in zip(actual_weights, expected_weights)) < 1e-12
        assert "lasso" not in bundle["models"]

        loaded = load_bundle(output)
        result = predict(loaded, {"A": 2, "B": 3})
        expected = 10.0 * expected_weights[0] + 20.0 * expected_weights[1] + 40.0 * expected_weights[2]
        assert abs(result["predicted_price_wan"] - expected) < 1e-6
        assert [x["name"] for x in result["member_predictions"]] == ["xgboost", "svr", "gbdt"]

        service = PriceService(output, None)
        health = service.health()
        assert health["backend"] == "native_pickle"
        assert health["model_count"] == 3
        assert health["model_names"] == ["xgboost", "svr", "gbdt"]

        manifest = json.loads(Path(str(output) + ".manifest.json").read_text(encoding="utf-8"))
        assert manifest["model_count"] == 3
        assert manifest["model_names"] == ["xgboost", "svr", "gbdt"]

        # A stale non-canonical Notebook weight vector must no longer block a
        # valid partial-model export. Automatic export falls back to equal weights.
        namespace["weights"] = [0.2, 0.8]
        fallback_output = root / "price_native_bundle_stale_weights.pkl"
        fallback = export_from_notebook(
            namespace, output=fallback_output, product_code="HOTFIX_TEST",
            target_divisor_to_wan=1, model_source="saved_files", saved_model_dir=root,
        )
        fallback_weights = [x["weight"] for x in fallback["ensemble"]["members"]]
        assert max(abs(value - 1.0 / 3.0) for value in fallback_weights) < 1e-12
        assert fallback["export_notes"]["weight_source"] == "equal_weights_stale_notebook_weights_ignored"
        print(json.dumps({
            "status": "PASS",
            "saved_model_count": 3,
            "saved_models": manifest["model_names"],
            "prediction": result["predicted_price_wan"],
            "stale_weight_fallback": fallback_weights,
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
