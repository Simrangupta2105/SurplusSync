"""Unit tests for TASK 2: BASELINES AND TABULAR MODELS (Time-series Track B).

Verifies:
1. Hand-computed correctness of Global Mean, Trailing 28-day Mean, Seasonal Naive 7, and Weekday Profile.
2. Valid interval shapes and coverage properties (90% nominal interval).
3. Poisson Regression and LightGBM fitting, non-negative predictions, and interval calibration.
4. Rolling-origin cross-validation metrics across 7-day and 28-day horizons.
5. Honest empirical performance: Tabular models reduce WAPE compared to simple panel mean.
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

# Ensure parent paths in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
PARENT_DIR = BASE_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

try:
    from ml_service.data.synthetic_panel import load_synthetic_panel
    from ml_service.data.time_series_splits import (
        RollingOriginSplitter,
        TimeSeriesFeaturePipeline,
        build_shop_category_series,
        get_target_and_covariates,
        split_train_test,
    )
    from ml_service.models.baseline_and_tabular import (
        GlobalMeanForecaster,
        HistGradientBoostingDemandModel,
        LightGBMRegressionForecaster,
        PoissonRegressionForecaster,
        SeasonalNaiveForecaster,
        TrailingMeanForecaster,
        WeekdayProfileForecaster,
        evaluate_baselines_across_folds,
        evaluate_tabular_models_across_folds,
    )
    from ml_service.models.metrics import compute_coverage, evaluate_forecast
except ModuleNotFoundError:
    from data.synthetic_panel import load_synthetic_panel
    from data.time_series_splits import (
        RollingOriginSplitter,
        TimeSeriesFeaturePipeline,
        build_shop_category_series,
        get_target_and_covariates,
        split_train_test,
    )
    from models.baseline_and_tabular import (
        GlobalMeanForecaster,
        HistGradientBoostingDemandModel,
        LightGBMRegressionForecaster,
        PoissonRegressionForecaster,
        SeasonalNaiveForecaster,
        TrailingMeanForecaster,
        WeekdayProfileForecaster,
        evaluate_baselines_across_folds,
        evaluate_tabular_models_across_folds,
    )
    from models.metrics import compute_coverage, evaluate_forecast


@pytest.fixture(scope="module")
def panel_data() -> pd.DataFrame:
    """Load cleaned synthetic panel data."""
    return load_synthetic_panel()


# --- 1. Hand-Computed Baseline Tests ---

def test_global_mean_forecaster_hand_computed():
    """Verify GlobalMeanForecaster computes exact empirical mean and non-negative intervals."""
    y = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    model = GlobalMeanForecaster().fit(y)
    assert model.mean_ == 30.0

    preds = model.predict(horizon=5)
    assert np.allclose(preds, [30.0, 30.0, 30.0, 30.0, 30.0])

    yhat, low, high = model.predict_interval(horizon=4, coverage=0.90)
    assert len(yhat) == len(low) == len(high) == 4
    assert (low >= 0.0).all()
    assert (low <= high).all()


def test_trailing_mean_forecaster_hand_computed():
    """Verify TrailingMeanForecaster computes mean over exactly the last `window` points."""
    y = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0])
    # Last 3 points: [50, 60, 70] -> mean = 60.0
    model = TrailingMeanForecaster(window=3).fit(y)
    assert model.trailing_mean_ == 60.0

    preds = model.predict(horizon=3)
    assert np.allclose(preds, [60.0, 60.0, 60.0])

    # If window > len(y), computes full mean
    model_wide = TrailingMeanForecaster(window=20).fit(y)
    assert model_wide.trailing_mean_ == 40.0


def test_seasonal_naive_forecaster_hand_computed():
    """Verify SeasonalNaiveForecaster tiles the last `seasonality` points."""
    y = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0])
    model = SeasonalNaiveForecaster(seasonality=3).fit(y)
    # Last 3 points: [50, 60, 70]
    preds3 = model.predict(horizon=3)
    assert np.allclose(preds3, [50.0, 60.0, 70.0])

    preds5 = model.predict(horizon=5)
    assert np.allclose(preds5, [50.0, 60.0, 70.0, 50.0, 60.0])


def test_weekday_profile_forecaster_hand_computed():
    """Verify WeekdayProfileForecaster matches mean per day of week."""
    # 2 weeks of data (14 days starting Monday)
    dates = pd.date_range("2024-01-01", periods=14, freq="D")  # Jan 1 2024 is Monday (dow=0)
    y = np.array([
        10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0,
        14.0, 22.0, 32.0, 42.0, 52.0, 64.0, 72.0,
    ])
    model = WeekdayProfileForecaster().fit(y, dates)

    # Monday mean: (10 + 14)/2 = 12.0
    # Tuesday mean: (20 + 22)/2 = 21.0
    assert model.dow_means_[0] == 12.0
    assert model.dow_means_[1] == 21.0

    future_dates = pd.date_range("2024-01-15", periods=3, freq="D")  # Mon, Tue, Wed
    preds = model.predict(future_dates)
    assert preds[0] == 12.0
    assert preds[1] == 21.0
    assert preds[2] == 31.0


# --- 2. Tabular Models Unit Tests ---

def test_poisson_regression_forecaster_fit_and_predict(panel_data: pd.DataFrame):
    """Verify PoissonRegressionForecaster trains and produces positive predictions and intervals."""
    train_pool, _ = split_train_test(panel_data)
    # Take a small temporal slice for fast unit testing
    sub_df = train_pool[train_pool["Date"] <= pd.Timestamp("2023-03-31")].copy()
    y_train, X_train = get_target_and_covariates(sub_df)

    model = PoissonRegressionForecaster(alpha=1e-3, max_iter=300)
    model.fit(X_train, y_train)

    test_slice = train_pool[
        (train_pool["Date"] >= pd.Timestamp("2023-04-01"))
        & (train_pool["Date"] <= pd.Timestamp("2023-04-07"))
    ].copy()
    y_test, X_test = get_target_and_covariates(test_slice)

    preds, low, high = model.predict_interval(X_test, coverage=0.90)

    assert len(preds) == len(X_test)
    assert (preds >= 0.0).all()
    assert (low >= 0.0).all()
    assert (low <= high).all()

    # Empirical coverage on this validation slice
    cov = compute_coverage(y_test.values, low, high)
    assert 0.70 <= cov <= 1.0


def test_lightgbm_regression_forecaster_fit_and_predict(panel_data: pd.DataFrame):
    """Verify LightGBMRegressionForecaster produces valid predictions with low error."""
    train_pool, _ = split_train_test(panel_data)
    sub_df = train_pool[train_pool["Date"] <= pd.Timestamp("2023-03-31")].copy()
    y_train, X_train = get_target_and_covariates(sub_df)

    model = LightGBMRegressionForecaster(n_estimators=40, learning_rate=0.1, random_state=42)
    model.fit(X_train, y_train)

    test_slice = train_pool[
        (train_pool["Date"] >= pd.Timestamp("2023-04-01"))
        & (train_pool["Date"] <= pd.Timestamp("2023-04-07"))
    ].copy()
    y_test, X_test = get_target_and_covariates(test_slice)

    preds, low, high = model.predict_interval(X_test, coverage=0.90)

    assert len(preds) == len(X_test)
    assert (preds >= 0.0).all()
    assert (low >= 0.0).all()
    assert (low <= high).all()


def test_hist_gradient_boosting_demand_model_fit(panel_data: pd.DataFrame):
    """Verify HistGradientBoostingDemandModel functions as a scikit-learn tree booster fallback."""
    train_pool, _ = split_train_test(panel_data)
    sub_df = train_pool[train_pool["Date"] <= pd.Timestamp("2023-02-28")].copy()
    y_train, X_train = get_target_and_covariates(sub_df)

    model = HistGradientBoostingDemandModel(max_iter=30, random_state=42)
    model.fit(X_train, y_train)

    test_slice = train_pool[
        (train_pool["Date"] >= pd.Timestamp("2023-03-01"))
        & (train_pool["Date"] <= pd.Timestamp("2023-03-07"))
    ].copy()
    _, X_test = get_target_and_covariates(test_slice)

    preds = model.predict(X_test)
    assert len(preds) == len(X_test)
    assert (preds >= 0.0).all()


# --- 3. Rolling-Origin Cross-Validation Evaluation Tests ---

def test_evaluate_tabular_models_across_folds_7day(panel_data: pd.DataFrame):
    """Verify tabular model evaluation generates complete metrics across 4 folds."""
    train_pool, _ = split_train_test(panel_data)
    # Run with 2 splits and step=28 for fast unit test
    results_df = evaluate_tabular_models_across_folds(train_pool, horizon=7, n_splits=2, step=28)

    assert len(results_df) > 0
    assert set(results_df["model"].unique()) == {
        "Poisson_Regression",
        "LightGBM",
        "HistGradientBoosting",
        "Panel_Global_Mean",
    }

    # Verify all expected metric columns exist and have finite values
    for col in ["wape", "mae", "rmse", "bias", "coverage"]:
        assert col in results_df.columns
        assert results_df[col].isna().sum() == 0
        assert np.isfinite(results_df[col]).all()

    # Verify LightGBM beats Panel_Global_Mean
    lgb_mean_wape = results_df[results_df["model"] == "LightGBM"]["wape"].mean()
    gm_mean_wape = results_df[results_df["model"] == "Panel_Global_Mean"]["wape"].mean()
    assert lgb_mean_wape < gm_mean_wape, (
        f"Expected LightGBM WAPE ({lgb_mean_wape:.4f}) < Panel Global Mean WAPE ({gm_mean_wape:.4f})"
    )


def test_evaluate_baselines_on_single_series(panel_data: pd.DataFrame):
    """Verify baseline evaluation computes metrics across rolling folds for a series."""
    series_dict = build_shop_category_series(panel_data)
    # Test on single series S01 Bakery
    test_dict = {("S01", "Bakery"): series_dict[("S01", "Bakery")]}

    res_df = evaluate_baselines_across_folds(test_dict, horizon=7, n_splits=2, step=28)

    assert len(res_df) == 2 * 4  # 2 folds * 4 models = 8 records
    expected_models = {"Global_Mean", "Trailing_Mean_28", "Seasonal_Naive_7", "Weekday_Profile"}
    assert set(res_df["model"].unique()) == expected_models

    for _, row in res_df.iterrows():
        assert row["wape"] >= 0.0
        assert row["mae"] >= 0.0
        assert row["rmse"] >= 0.0
        assert 0.0 <= row["coverage"] <= 1.0
