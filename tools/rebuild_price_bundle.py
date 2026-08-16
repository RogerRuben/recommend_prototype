# -*- coding: utf-8 -*-
"""Rebuild the price bundle correctly from the encoded fixture.

The previously exported bundle was trained on a corrupted target scale (linear
models predicted ~0 and tree models ~2-7M).  This script retrains the scaler and
all six estimators on ``log(historical_price_wan)`` (万元) using the exact 12-sample
fixture, then re-exports through the standard export path so the independent price
service returns 12.6-19.6 万 again.

Run with the same Python that has scikit-learn (e.g. D:\\anaconda\\python.exe):

    D:\\anaconda\\python.exe tools\\rebuild_price_bundle.py
"""
from __future__ import print_function

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor
from sklearn.linear_model import Lasso, Ridge
from sklearn.preprocessing import MinMaxScaler
from sklearn.svm import SVR

from app.xlsx_utils import read_workbook_bytes
from services.price_service.export_native_price_bundle import export_from_notebook

FIXTURE = ROOT / "test_data" / "encoded_aircraft_door_lock_prediction.xlsx"
OUTPUT = ROOT / "services" / "price_service" / "model" / "price_native_bundle.pkl"


def load_fixture():
    wb = read_workbook_bytes(FIXTURE.read_bytes())
    sheet = wb["encoded_history"]
    header = [str(c).strip() for c in sheet[0]]
    data = sheet[1:]
    price_col = header.index("historical_price_wan")
    feat_cols = [c for c in header if c.startswith("attr_")]
    rows = []
    for r in data:
        price = r[price_col]
        feats = [r[header.index(c)] for c in feat_cols]
        if price in (None, "") or any(v in (None, "") for v in feats):
            continue
        rows.append((float(price), [float(v) for v in feats]))
    return feat_cols, rows


def main():
    feat_cols, rows = load_fixture()
    if not rows:
        raise SystemExit("fixture has no complete rows")
    X = np.array([f for _, f in rows], dtype=float)
    y_price = np.array([p for p, _ in rows], dtype=float)
    y = np.log(y_price)

    # Hold out the last few rows for an honest residual/interval estimate.
    n_val = max(1, len(rows) // 4)
    tr_idx = list(range(len(rows) - n_val))
    val_idx = list(range(len(rows) - n_val, len(rows)))

    X_tr_df = pd.DataFrame(X[tr_idx], columns=feat_cols)
    y_tr = y[tr_idx]
    X_val_df = pd.DataFrame(X[val_idx], columns=feat_cols)
    y_val_price = y_price[val_idx]

    scaler = MinMaxScaler(feature_range=(0, 1)).fit(X_tr_df)
    Xs_tr_df = pd.DataFrame(scaler.transform(X_tr_df), columns=feat_cols)

    lasso_model = Lasso(alpha=0.001, max_iter=20000).fit(Xs_tr_df, y_tr)
    ridge_model = Ridge(alpha=1.0).fit(Xs_tr_df, y_tr)
    rf_model = RandomForestRegressor(n_estimators=300, max_depth=None, random_state=20260812).fit(Xs_tr_df, y_tr)
    et_model = ExtraTreesRegressor(n_estimators=300, max_depth=None, random_state=20260812).fit(Xs_tr_df, y_tr)
    svr_model = SVR(C=10.0, gamma=0.1, epsilon=0.01).fit(Xs_tr_df, y_tr)
    gbdt_model = GradientBoostingRegressor(n_estimators=200, max_depth=3, random_state=20260812).fit(Xs_tr_df, y_tr)

    models = {
        "lasso": lasso_model, "ridge": ridge_model, "random_forest": rf_model,
        "extra_trees": et_model, "svr": svr_model, "gbdt": gbdt_model,
    }
    # Equal, transparent ensemble weighting: every estimator predicts on the
    # log(万元) scale, so a simple mean already lands in the 12.6-19.6 万 band.
    weights = {name: 1.0 / len(models) for name in models}

    namespace = {
        "X_train": Xs_tr_df,
        "train_df": X_tr_df,
        "scaler": scaler,
        "lasso_model": lasso_model,
        "ridge_model": ridge_model,
        "rf_model": rf_model,
        "et_model": et_model,
        "svr_model": svr_model,
        "gbdt_model": gbdt_model,
        "X_test": X_val_df,
        "y_test": pd.Series(y_val_price),
        "weights": [weights[name] for name in models],
        "PRODUCT_CODE": "AIRCRAFT_DOOR_LOCK_BASIC_DEMO",
        "PRODUCT_NAME": "AIRCRAFT_DOOR_LOCK_BASIC_DEMO",
        "PRICE_MODEL_SOURCE": "namespace",
        "TARGET_DIVISOR_TO_WAN": 1.0,
        "PRICE_MODEL_VERSION": "price-native-notebook",
        "PRICE_OUTPUT_TRANSFORM": "log",
    }
    bundle = export_from_notebook(
        namespace,
        output=str(OUTPUT),
        product_code="AIRCRAFT_DOOR_LOCK_BASIC_DEMO",
        product_name="AIRCRAFT_DOOR_LOCK_BASIC_DEMO",
        model_version="price-native-notebook",
        target_divisor_to_wan=1.0,
        model_variables={
            "lasso": "lasso_model", "ridge": "ridge_model", "random_forest": "rf_model",
            "extra_trees": "et_model", "svr": "svr_model", "gbdt": "gbdt_model",
        },
        ensemble_weights=[weights[name] for name in models],
        model_source="namespace",
        model_output_transform="log",
    )
    print("rebuilt bundle ->", OUTPUT)
    print("training samples:", len(rows), "features:", feat_cols)
    print("weights:", {k: round(v, 4) for k, v in weights.items()})
    # smoke-check on the fixture rows
    from services.price_service.native_bundle import load_bundle, predict
    b = load_bundle(str(OUTPUT))
    for (price, feats), _ in zip(rows, range(5)):
        params = dict(zip(feat_cols, feats))
        got = predict(b, params)["predicted_price_wan"]
        print("true=%.2f万  api=%.2f万" % (price, got))


if __name__ == "__main__":
    main()
