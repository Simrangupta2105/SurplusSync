"""Task 4 Lag Feature Experiment Runner: Direct Multi-Step vs Exogenous Baselines.

Evaluates whether adding the past 7 days of demand (lags 1-7, 7d/28d rolling means,
same weekday last week) improves demand forecasting accuracy over models using only
exogenous covariates:
- Models: HistGradientBoosting and LightGBM
- Evaluated on:
  1. 4 rolling-origin cross-validation folds on pre-cutoff data (Date < 2025-10-03)
  2. The untouched final 90-day holdout (2025-10-03 to 2025-12-31), evaluated once
- Metrics: WAPE, MAE, RMSE, Bias, 90% Prediction Interval Coverage
- Granularity: Overall and per food category (Bakery, Dairy, Fruits, Meat, Prepared Food, Vegetables)
- Autocorrelation analysis: verifies synthetic autocorrelation structure (lag-1 and lag-7)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Sequence, Tuple

# Ensure ml_service and workspace root are in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR.parent
for p in [str(WORKSPACE_DIR), str(BASE_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
import pandas as pd

try:
    from ml_service.data.synthetic_panel import load_synthetic_panel
    from ml_service.data.time_series_splits import (
        KNOWN_COVARIATES,
        RollingOriginSplitter,
        get_target_and_covariates,
        split_train_test,
    )
    from ml_service.models.baseline_and_tabular import (
        HistGradientBoostingDemandModel,
        LightGBMRegressionForecaster,
    )
    from ml_service.models.lag_models import (
        DirectLagDemandForecaster,
        compute_empirical_autocorrelation,
    )
    from ml_service.models.metrics import evaluate_forecast
except ModuleNotFoundError:
    from data.synthetic_panel import load_synthetic_panel
    from data.time_series_splits import (
        KNOWN_COVARIATES,
        RollingOriginSplitter,
        get_target_and_covariates,
        split_train_test,
    )
    from models.baseline_and_tabular import (
        HistGradientBoostingDemandModel,
        LightGBMRegressionForecaster,
    )
    from models.lag_models import (
        DirectLagDemandForecaster,
        compute_empirical_autocorrelation,
    )
    from models.metrics import evaluate_forecast


REPORTS_DIR = Path(__file__).resolve().parent
RESULTS_JSON_PATH = REPORTS_DIR / "task4_lag_experiment_results.json"


def run_cv_evaluation(
    train_pool_df: pd.DataFrame,
    n_splits: int = 4,
    horizon: int = 7,
    step: int = 28,
) -> pd.DataFrame:
    """Evaluate No-Lag vs Direct-Lag models across rolling-origin CV folds."""
    splitter = RollingOriginSplitter(n_splits=n_splits, horizon=horizon, step=step)
    records: List[Dict[str, Any]] = []

    # Get unique series list
    series_keys = list(train_pool_df.groupby(["Shop_ID", "Food_Category"]).groups.keys())

    for fold_idx, (train_df, val_df, fold) in enumerate(splitter.split_panel(train_pool_df)):
        # 1. Train No-Lag Models on train_df
        y_train, X_train = get_target_and_covariates(train_df)
        y_val, X_val = get_target_and_covariates(val_df)

        hgb_nolag = HistGradientBoostingDemandModel().fit(X_train, y_train)
        lgb_nolag = LightGBMRegressionForecaster().fit(X_train, y_train)

        # 2. Train Direct-Lag Models on train_df
        hgb_lag = DirectLagDemandForecaster(estimator_type="hist_gradient_boosting", horizon=horizon).fit(train_df)
        lgb_lag = DirectLagDemandForecaster(estimator_type="lightgbm", horizon=horizon).fit(train_df)

        # 3. Evaluate per series in val_df
        for (shop_id, food_cat) in series_keys:
            val_s = val_df[(val_df["Shop_ID"] == shop_id) & (val_df["Food_Category"] == food_cat)].sort_values("Date")
            if len(val_s) != horizon:
                continue

            y_true, val_exog = get_target_and_covariates(val_s)
            train_s = train_df[(train_df["Shop_ID"] == shop_id) & (train_df["Food_Category"] == food_cat)].sort_values("Date")

            # A. HistGradientBoosting No Lags
            hgb_nl_pred, hgb_nl_low, hgb_nl_high = hgb_nolag.predict_interval(val_exog)
            ev_hgb_nl = evaluate_forecast(y_true, hgb_nl_pred, hgb_nl_low, hgb_nl_high)
            records.append({
                "model": "HistGradientBoosting",
                "variant": "No_Lags",
                "fold_idx": fold.fold_idx,
                "shop_id": shop_id,
                "food_category": food_cat,
                **ev_hgb_nl,
            })

            # B. HistGradientBoosting With Lags (Direct)
            hgb_l_pred, hgb_l_low, hgb_l_high = hgb_lag.predict_horizon_series(train_s, val_exog)
            ev_hgb_l = evaluate_forecast(y_true, hgb_l_pred, hgb_l_low, hgb_l_high)
            records.append({
                "model": "HistGradientBoosting",
                "variant": "With_Lags_Direct",
                "fold_idx": fold.fold_idx,
                "shop_id": shop_id,
                "food_category": food_cat,
                **ev_hgb_l,
            })

            # C. LightGBM No Lags
            lgb_nl_pred, lgb_nl_low, lgb_nl_high = lgb_nolag.predict_interval(val_exog)
            ev_lgb_nl = evaluate_forecast(y_true, lgb_nl_pred, lgb_nl_low, lgb_nl_high)
            records.append({
                "model": "LightGBM",
                "variant": "No_Lags",
                "fold_idx": fold.fold_idx,
                "shop_id": shop_id,
                "food_category": food_cat,
                **ev_lgb_nl,
            })

            # D. LightGBM With Lags (Direct)
            lgb_l_pred, lgb_l_low, lgb_l_high = lgb_lag.predict_horizon_series(train_s, val_exog)
            ev_lgb_l = evaluate_forecast(y_true, lgb_l_pred, lgb_l_low, lgb_l_high)
            records.append({
                "model": "LightGBM",
                "variant": "With_Lags_Direct",
                "fold_idx": fold.fold_idx,
                "shop_id": shop_id,
                "food_category": food_cat,
                **ev_lgb_l,
            })

    return pd.DataFrame(records)


def run_final_test_evaluation(
    train_pool_df: pd.DataFrame,
    test_df: pd.DataFrame,
    horizon: int = 7,
) -> pd.DataFrame:
    """Evaluate models on the untouched final 90-day test set using rolling 7-day windows."""
    # Fit models on the full pre-cutoff training pool
    y_train, X_train = get_target_and_covariates(train_pool_df)

    hgb_nolag = HistGradientBoostingDemandModel().fit(X_train, y_train)
    lgb_nolag = LightGBMRegressionForecaster().fit(X_train, y_train)

    hgb_lag = DirectLagDemandForecaster(estimator_type="hist_gradient_boosting", horizon=horizon).fit(train_pool_df)
    lgb_lag = DirectLagDemandForecaster(estimator_type="lightgbm", horizon=horizon).fit(train_pool_df)

    # In the final 90-day test set (October 3 to December 31, 2025 = 90 days),
    # evaluate non-overlapping 7-day multi-step blocks (12 windows = 84 days)
    test_dates = sorted(test_df["Date"].unique())
    n_windows = len(test_dates) // horizon  # 12 windows

    records: List[Dict[str, Any]] = []
    series_keys = list(test_df.groupby(["Shop_ID", "Food_Category"]).groups.keys())

    # Full combined panel for extracting history up to window origin
    full_panel = pd.concat([train_pool_df, test_df], ignore_index=True).sort_values(["Shop_ID", "Food_Category", "Date"])

    for w in range(n_windows):
        window_dates = test_dates[w * horizon : (w + 1) * horizon]
        origin_date = window_dates[0] - pd.Timedelta(days=1)

        window_df = test_df[test_df["Date"].isin(window_dates)]
        history_df = full_panel[full_panel["Date"] <= origin_date]

        for (shop_id, food_cat) in series_keys:
            val_s = window_df[(window_df["Shop_ID"] == shop_id) & (window_df["Food_Category"] == food_cat)].sort_values("Date")
            if len(val_s) != horizon:
                continue

            y_true, val_exog = get_target_and_covariates(val_s)
            train_s = history_df[(history_df["Shop_ID"] == shop_id) & (history_df["Food_Category"] == food_cat)].sort_values("Date")

            # A. HistGradientBoosting No Lags
            p_hgb_nl, l_hgb_nl, u_hgb_nl = hgb_nolag.predict_interval(val_exog)
            ev_hgb_nl = evaluate_forecast(y_true, p_hgb_nl, l_hgb_nl, u_hgb_nl)
            records.append({
                "model": "HistGradientBoosting",
                "variant": "No_Lags",
                "window_idx": w,
                "shop_id": shop_id,
                "food_category": food_cat,
                **ev_hgb_nl,
            })

            # B. HistGradientBoosting With Lags
            p_hgb_l, l_hgb_l, u_hgb_l = hgb_lag.predict_horizon_series(train_s, val_exog)
            ev_hgb_l = evaluate_forecast(y_true, p_hgb_l, l_hgb_l, u_hgb_l)
            records.append({
                "model": "HistGradientBoosting",
                "variant": "With_Lags_Direct",
                "window_idx": w,
                "shop_id": shop_id,
                "food_category": food_cat,
                **ev_hgb_l,
            })

            # C. LightGBM No Lags
            p_lgb_nl, l_lgb_nl, u_lgb_nl = lgb_nolag.predict_interval(val_exog)
            ev_lgb_nl = evaluate_forecast(y_true, p_lgb_nl, l_lgb_nl, u_lgb_nl)
            records.append({
                "model": "LightGBM",
                "variant": "No_Lags",
                "window_idx": w,
                "shop_id": shop_id,
                "food_category": food_cat,
                **ev_lgb_nl,
            })

            # D. LightGBM With Lags
            p_lgb_l, l_lgb_l, u_lgb_l = lgb_lag.predict_horizon_series(train_s, val_exog)
            ev_lgb_l = evaluate_forecast(y_true, p_lgb_l, l_lgb_l, u_lgb_l)
            records.append({
                "model": "LightGBM",
                "variant": "With_Lags_Direct",
                "window_idx": w,
                "shop_id": shop_id,
                "food_category": food_cat,
                **ev_lgb_l,
            })

    return pd.DataFrame(records)


def run_and_save_task4_experiment() -> Dict[str, Any]:
    """Execute complete Task 4 experimental evaluation and persist results."""
    panel_df = load_synthetic_panel()
    train_pool_df, test_df = split_train_test(panel_df)

    # 1. Autocorrelation analysis
    acf_metrics = compute_empirical_autocorrelation(panel_df)

    # 2. Rolling-origin CV evaluation (4 folds)
    print("Running Rolling-Origin CV evaluation for Task 4...")
    cv_df = run_cv_evaluation(train_pool_df, n_splits=4, horizon=7, step=28)

    # Summarize CV metrics
    cv_summary = cv_df.groupby(["model", "variant"])[["wape", "mae", "rmse", "bias", "coverage"]].mean().reset_index()
    cv_cat_summary = cv_df.groupby(["model", "variant", "food_category"])[["wape", "mae", "rmse", "bias", "coverage"]].mean().reset_index()

    # 3. Final 90-day test set evaluation
    print("Running untouched Final 90-day Test evaluation for Task 4...")
    test_results_df = run_final_test_evaluation(train_pool_df, test_df, horizon=7)

    test_summary = test_results_df.groupby(["model", "variant"])[["wape", "mae", "rmse", "bias", "coverage"]].mean().reset_index()
    test_cat_summary = test_results_df.groupby(["model", "variant", "food_category"])[["wape", "mae", "rmse", "bias", "coverage"]].mean().reset_index()

    payload = {
        "autocorrelation": acf_metrics,
        "cv_summary": cv_summary.to_dict(orient="records"),
        "cv_category_summary": cv_cat_summary.to_dict(orient="records"),
        "test_summary": test_summary.to_dict(orient="records"),
        "test_category_summary": test_cat_summary.to_dict(orient="records"),
    }

    with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Results saved to {RESULTS_JSON_PATH}")
    return payload


if __name__ == "__main__":
    run_and_save_task4_experiment()
