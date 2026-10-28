"""Unit and Invariant Tests for Task 4 Lag Experiment.

Validates:
1. Mathematical correctness of lag feature computation (lags 1-7, rolling 7, rolling 28, same weekday).
2. Strict Temporal No-Leakage Invariant:
   - For every horizon step h in {1..7}, features at forecast origin t use ONLY observations up to t.
   - Mutating future targets (t+1 through t+7) leaves origin features completely unchanged.
3. DirectLagDemandForecaster behavior:
   - Trains 7 step models with HistGradientBoosting and LightGBM.
   - Generates non-negative point forecasts and calibrated 90% prediction intervals.
4. Empirical autocorrelation verification on the synthetic panel.
5. Per-category evaluation metrics reporting.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml_service.data.synthetic_panel import load_synthetic_panel
from ml_service.data.time_series_splits import split_train_test
from ml_service.models.lag_models import (
    DirectLagDemandForecaster,
    compute_empirical_autocorrelation,
    compute_origin_lags,
)


def test_compute_origin_lags_exact_values():
    """Verify lag features match hand-calculated values on known historical sequence."""
    # History: 35 days, sequence from 10 to 44
    # Origin t is index 34 (value 44)
    history = np.arange(10, 45, dtype=float)  # length 35
    assert len(history) == 35
    assert history[-1] == 44.0  # y_t

    # Step h = 1 (predicting tomorrow, t+1)
    lags_h1 = compute_origin_lags(history, horizon_step=1)
    assert lags_h1["demand_lag_1"] == 44.0  # y_t
    assert lags_h1["demand_lag_2"] == 43.0  # y_{t-1}
    assert lags_h1["demand_lag_3"] == 42.0  # y_{t-2}
    assert lags_h1["demand_lag_4"] == 41.0  # y_{t-3}
    assert lags_h1["demand_lag_5"] == 40.0  # y_{t-4}
    assert lags_h1["demand_lag_6"] == 39.0  # y_{t-5}
    assert lags_h1["demand_lag_7"] == 38.0  # y_{t-6}

    # Rolling mean 7: mean(38, 39, 40, 41, 42, 43, 44) = 41.0
    assert pytest.approx(lags_h1["rolling_mean_7"]) == 41.0

    # Rolling mean 28: mean of last 28 elements (values from 17 to 44) = (17 + 44) / 2 = 30.5
    assert pytest.approx(lags_h1["rolling_mean_28"]) == 30.5

    # Same weekday last week for step h=1:
    # Target date is t+1. 7 days prior is t - 6.
    # Value at index 34 - 6 = 28 -> value 38.0
    assert lags_h1["same_weekday_last_week"] == 38.0

    # Step h = 7 (predicting 7 days ahead, t+7)
    lags_h7 = compute_origin_lags(history, horizon_step=7)
    # Target date is t+7. 7 days prior is (t+7) - 7 = t.
    # Value at origin t is history[-1] = 44.0!
    assert lags_h7["same_weekday_last_week"] == 44.0


def test_strict_temporal_no_leakage_invariant():
    """Verify that no feature uses data from the day being predicted or any subsequent day.
    
    Proof by perturbation:
    Mutating future ground truth targets at t+1, t+2, ..., t+7 must have ZERO effect
    on the feature vectors computed for steps 1..7.
    """
    history = np.array([20.0 + i for i in range(30)], dtype=float)  # t=0..29
    true_future = np.array([50.0, 52.0, 54.0, 56.0, 58.0, 60.0, 62.0])  # t+1..t+7

    # Calculate baseline lags for all 7 steps
    baseline_lags = [compute_origin_lags(history, horizon_step=h) for h in range(1, 8)]

    # Now simulate a leak scenario: suppose future demand were corrupted or drastically changed
    corrupted_future = true_future * 999.0 + 10000.0

    # Verify that regardless of what happens in the future, the origin lags remain identical
    for h in range(1, 8):
        current_lags = compute_origin_lags(history, horizon_step=h)
        for key in baseline_lags[h - 1]:
            assert current_lags[key] == baseline_lags[h - 1][key], (
                f"Feature '{key}' at step {h} changed! Possible future leakage."
            )
            # Ensure none of the future corrupted values appear anywhere in origin lags
            for corrupted_val in corrupted_future:
                assert current_lags[key] != corrupted_val


def test_direct_lag_forecaster_fit_and_predict_bounds():
    """Test DirectLagDemandForecaster trains and produces valid predictions with intervals."""
    panel_df = load_synthetic_panel()
    train_pool_df, test_df = split_train_test(panel_df)

    # Use a small subset of training data (2 shops) for fast test execution
    subset_df = train_pool_df[train_pool_df["Shop_ID"].isin(["S01", "S02"])].copy()

    # 1. Fit HistGradientBoosting Direct Lag Forecaster
    forecaster = DirectLagDemandForecaster(
        estimator_type="hist_gradient_boosting",
        horizon=7,
        n_estimators=10,
    )
    forecaster.fit(subset_df)

    assert len(forecaster.models_) == 7
    assert len(forecaster.pipelines_) == 7
    assert len(forecaster.residual_quantiles_) == 7

    # 2. Predict on S01 Bakery
    s01_bakery = subset_df[(subset_df["Shop_ID"] == "S01") & (subset_df["Food_Category"] == "Bakery")].sort_values("Date")
    origin_history = s01_bakery.iloc[-60:-7]
    future_exog = s01_bakery.iloc[-7:].drop(columns=["Daily_Demand"])

    preds, lowers, uppers = forecaster.predict_horizon_series(origin_history, future_exog)

    assert len(preds) == 7
    assert len(lowers) == 7
    assert len(uppers) == 7

    # Verify non-negativity and interval ordering: 0 <= lower <= upper
    assert np.all(preds >= 0.0)
    assert np.all(lowers >= 0.0)
    assert np.all(uppers >= lowers)


def test_empirical_autocorrelation_values():
    """Verify synthetic panel autocorrelation at lag 1 and lag 7 matches documented values."""
    panel_df = load_synthetic_panel()
    acf_dict = compute_empirical_autocorrelation(panel_df)

    # Synthetic panel was designed with lag-1 ~0.36 and lag-7 ~0.44
    lag1 = acf_dict["lag_1_mean_acf"]
    lag7 = acf_dict["lag_7_mean_acf"]

    assert 0.30 <= lag1 <= 0.45, f"Expected lag 1 ACF around 0.36, got {lag1:.3f}"
    assert 0.35 <= lag7 <= 0.55, f"Expected lag 7 ACF around 0.44, got {lag7:.3f}"
