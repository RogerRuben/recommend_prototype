# -*- coding: utf-8 -*-
"""Offline price-training environment and native export smoke test."""
from __future__ import print_function

import json
import math
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd
import seaborn as sns
import sklearn
import xgboost
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from xgboost import XGBRegressor

from services.price_service.export_native_price_bundle import export_from_notebook
from services.price_service.native_bundle import load_bundle, predict


REPORT_PATH = ROOT / "logs" / "price_training_environment_test_report.json"


def check(condition, name, report):
    if not condition:
        raise AssertionError(name)
    report["checks"].append({"name": name, "status": "PASS"})


def main():
    report = {
        "test": "price_training_environment",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python": sys.version,
        "versions": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "openpyxl": openpyxl.__version__,
            "matplotlib": matplotlib.__version__,
            "seaborn": sns.__version__,
            "sklearn": sklearn.__version__,
            "xgboost": xgboost.__version__,
        },
        "checks": [],
        "status": "RUNNING",
    }
    try:
        check(sys.version_info[:2] == (3, 8), "使用Python 3.8训练环境", report)
        rng = np.random.RandomState(20260730)
        rows = 160
        thrust = rng.uniform(5.0, 20.0, rows)
        speed = rng.uniform(10.0, 100.0, rows)
        batch = rng.randint(1, 500, rows).astype(float)
        price = (
            4.5 + thrust * 0.72 + speed * 0.035 - batch * 0.008
            + rng.normal(0.0, 0.18, rows)
        )
        frame = pd.DataFrame({
            "额定推力": thrust,
            "运行速度": speed,
            "采购批量": batch,
        })
        train = frame.iloc[:120].copy()
        test = frame.iloc[120:].copy()
        y_train = np.log(price[:120])
        y_test = price[120:]
        scaler = StandardScaler().fit(train)
        train_scaled = scaler.transform(train)
        models = {
            "ridge": Ridge(alpha=0.15).fit(train_scaled, y_train),
            "svr": SVR(C=12.0, gamma="scale").fit(train_scaled, y_train),
            "gbdt": GradientBoostingRegressor(
                random_state=20260730, n_estimators=35
            ).fit(train_scaled, y_train),
            "xgboost": XGBRegressor(
                n_estimators=25,
                max_depth=3,
                learning_rate=0.08,
                subsample=0.9,
                colsample_bytree=0.9,
                random_state=20260730,
                n_jobs=1,
                objective="reg:squarederror",
            ).fit(train_scaled, y_train),
        }
        check(len(models) == 4, "Ridge、SVR、GBDT和XGBoost训练完成", report)

        with tempfile.TemporaryDirectory(
            prefix="price_training_env_",
            dir=str(ROOT / "runtime"),
        ) as temp:
            temp_root = Path(temp)
            excel_path = temp_root / "training_roundtrip.xlsx"
            frame.head(12).to_excel(excel_path, index=False)
            roundtrip = pd.read_excel(excel_path, engine="openpyxl")
            check(list(roundtrip.columns) == list(frame.columns), "pandas/openpyxl读写训练表通过", report)

            plot_path = temp_root / "training_plot.png"
            plt.figure(figsize=(5, 3))
            sns.scatterplot(x=thrust[:40], y=price[:40])
            plt.tight_layout()
            plt.savefig(plot_path, dpi=100)
            plt.close()
            check(plot_path.is_file() and plot_path.stat().st_size > 1000, "matplotlib/seaborn绘图通过", report)

            bundle_path = temp_root / "price_native_bundle.pkl"
            namespace = {
                "X_train": train,
                "X_test": test,
                "y_train": y_train,
                "y_test": y_test,
                "scaler": scaler,
                "ridge_model": models["ridge"],
                "svr_model": models["svr"],
                "gbdt_model": models["gbdt"],
                "xgb_model": models["xgboost"],
            }
            names = ["ridge", "svr", "gbdt", "xgboost"]
            weights = [0.2, 0.2, 0.3, 0.3]
            metadata = {
                "额定推力": {
                    "field_name": "rated_thrust",
                    "field_label": "额定推力",
                    "dtype": "number",
                    "unit": "kN",
                },
                "运行速度": {
                    "field_name": "speed",
                    "field_label": "运行速度",
                    "dtype": "number",
                    "unit": "mm/s",
                },
                "采购批量": {
                    "field_name": "batch_size",
                    "field_label": "采购批量",
                    "dtype": "integer",
                    "unit": "台",
                },
            }
            export_from_notebook(
                namespace,
                output=bundle_path,
                product_code="PRICE_TRAINING_ENV_TEST",
                product_name="价格训练环境验收",
                model_version="training-env-smoke-v1",
                target_divisor_to_wan=1.0,
                field_metadata=metadata,
                ensemble_model_names=names,
                ensemble_weights=weights,
                strict=True,
                model_source="namespace",
            )
            bundle = load_bundle(bundle_path)
            sample = {
                "rated_thrust": float(test.iloc[0]["额定推力"]),
                "speed": float(test.iloc[0]["运行速度"]),
                "batch_size": int(test.iloc[0]["采购批量"]),
            }
            served = predict(bundle, sample)["predicted_price_wan"]
            prepared = scaler.transform([[
                sample["rated_thrust"], sample["speed"], sample["batch_size"],
            ]])
            expected = 0.0
            for name, weight in zip(names, weights):
                expected += float(weight) * math.exp(
                    float(models[name].predict(prepared)[0])
                )
            # The public service result is intentionally rounded to 6 decimals.
            check(
                abs(float(served) - expected) <= 5e-7,
                "原生bundle与训练对象集成预测等价",
                report,
            )
            check(
                bundle["feature_order"]
                == ["rated_thrust", "speed", "batch_size"],
                "训练列到稳定业务字段ID映射正确",
                report,
            )
            check(
                set(bundle["required_modules"]) == {"sklearn", "xgboost"},
                "正式bundle记录实际运行依赖",
                report,
            )

        report["status"] = "PASS"
    except Exception as exc:
        report["status"] = "FAIL"
        report["error"] = "%s: %s" % (type(exc).__name__, exc)
        raise
    finally:
        report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
