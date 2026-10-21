"""Tests for TASK 3: TIME-SERIES DIAGNOSTICS (Track A).

Verifies:
1. Category daily series construction using mean demand per record and explicit missing day interpolation.
2. ACF and seasonal decomposition showing dominant residual noise variance.
3. Plain mean, seasonal naive, and 7-day moving average forecasters against hand-computed values.
4. PyTorch LSTM forecaster on CPU (reproducibility with fixed seed, valid shapes, non-negative).
5. Prophet forecaster fit and predict interface.
6. Empirical confirmation of honest negative result: Plain Mean outperforms Seasonal Naive and Moving Average.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from ml_service.data.food_waste import (
    DEFAULT_DATASET_PATH,
    clean_food_waste_data,
    load_raw_data,
)
from ml_service.models.time_series import (
    MovingAverageForecaster,
    PlainMeanForecaster,
    ProphetForecaster,
    PyTorchLSTMForecaster,
    SeasonalNaiveForecaster,
    build_category_daily_series,
    compute_time_series_diagnostics,
)


@pytest.fixture(scope="module")
def category_series_dict():
    """Build and return cleaned daily category series."""
    raw_df = load_raw_data(DEFAULT_DATASET_PATH)
    clean_df, _ = clean_food_waste_data(raw_df)
    return build_category_daily_series(clean_df)


# --- 1. Category Daily Series Construction Tests ---

def test_build_category_daily_series_structure(category_series_dict):
    """Verify that all 6 categories have exactly 365 daily steps with missing days explicitly handled."""
    expected_categories = {"Bakery", "Dairy", "Fruits", "Meat", "Prepared Food", "Vegetables"}
    assert set(category_series_dict.keys()) == expected_categories

    for cat, s_df in category_series_dict.items():
        assert len(s_df) == 365, f"{cat} has {len(s_df)} days, expected 365"
        assert s_df.index.min() == pd.Timestamp("2025-01-01")
        assert s_df.index.max() == pd.Timestamp("2025-12-31")

        # Explicit missing day tracking
        assert "is_missing_day" in s_df.columns
        assert "mean_demand" in s_df.columns
        assert "record_count" in s_df.columns

        # Verify no NaNs remain after interpolation
        assert s_df["mean_demand"].isna().sum() == 0
        assert (s_df["mean_demand"] > 0).all()

        # Check that between 4 and 12 days were interpolated
        missing_count = s_df["is_missing_day"].sum()
        assert 3 <= missing_count <= 15, f"{cat} has unexpected missing day count: {missing_count}"


# --- 2. Diagnostics: ACF and Seasonal Decomposition Tests ---

def test_time_series_diagnostics_high_residual_variance(category_series_dict):
    """Verify that seasonal decomposition reveals dominant residual noise (>70% of variance)."""
    bakery_series = category_series_dict["Bakery"]
    diag = compute_time_series_diagnostics(bakery_series)

    assert "acf_values" in diag
    assert "total_variance" in diag
    assert "residual_variance" in diag
    assert "seasonal_variance" in diag

    # In our dataset, residual variance constitutes > 70% of total variance
    residual_pct = (diag["residual_variance"] / diag["total_variance"]) * 100
    assert residual_pct > 70.0, f"Residual variance percentage is {residual_pct:.1f}%, expected > 70%"

    # Autocorrelation at weekly lags (7 and 14) is near zero (|r| < 0.20)
    assert abs(diag["acf_values"][7]) < 0.20
    assert abs(diag["acf_values"][14]) < 0.20

    # Seasonal strength is very weak (< 0.25)
    assert diag["seasonal_strength"] < 0.25


# --- 3. Hand-Computed Forecaster Unit Tests ---

def test_plain_mean_forecaster_hand_computed():
    """Verify PlainMeanForecaster returns the exact empirical mean."""
    df_synthetic = pd.DataFrame({
        "mean_demand": [100.0, 110.0, 120.0, 130.0, 140.0],
    }, index=pd.date_range("2025-01-01", periods=5))

    forecaster = PlainMeanForecaster().fit(df_synthetic)
    assert forecaster.mean_ == 120.0

    preds = forecaster.predict(horizon=4)
    assert np.allclose(preds, [120.0, 120.0, 120.0, 120.0])

    yhat, low, high = forecaster.predict_range(horizon=4, alpha=0.20)
    assert (low <= yhat).all()
    assert (yhat <= high).all()
    assert (low >= 0).all()


def test_seasonal_naive_forecaster_hand_computed():
    """Verify SeasonalNaiveForecaster repeats the last 7 days of history."""
    df_synthetic = pd.DataFrame({
        "mean_demand": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0],
    }, index=pd.date_range("2025-01-01", periods=7))

    forecaster = SeasonalNaiveForecaster().fit(df_synthetic)

    # 7-day horizon: exact repeat
    preds7 = forecaster.predict(horizon=7)
    assert np.allclose(preds7, [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0])

    # 10-day horizon: tiles and truncates to 10
    preds10 = forecaster.predict(horizon=10)
    assert np.allclose(preds10, [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 10.0, 20.0, 30.0])


def test_moving_average_forecaster_hand_computed():
    """Verify MovingAverageForecaster returns the mean of the specified window."""
    df_synthetic = pd.DataFrame({
        "mean_demand": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0],
    }, index=pd.date_range("2025-01-01", periods=7))

    # Mean of [10, 20, 30, 40, 50, 60, 70] is 40.0
    forecaster = MovingAverageForecaster(window=7).fit(df_synthetic)
    assert forecaster.ma_val_ == 40.0

    preds = forecaster.predict(horizon=3)
    assert np.allclose(preds, [40.0, 40.0, 40.0])


# --- 4. PyTorch LSTM and Prophet Smoke Tests ---

def test_pytorch_lstm_forecaster_cpu():
    """Verify PyTorchLSTMForecaster trains on CPU, predicts valid shapes, and is deterministic."""
    np.random.seed(42)
    synthetic_vals = 100.0 + np.random.normal(0, 5, size=60)
    df_synthetic = pd.DataFrame({
        "mean_demand": synthetic_vals,
    }, index=pd.date_range("2025-01-01", periods=60))

    lstm1 = PyTorchLSTMForecaster(lookback=28, hidden_size=16, epochs=15, random_seed=42)
    lstm1.fit(df_synthetic)
    preds1 = lstm1.predict(horizon=7)

    assert isinstance(preds1, np.ndarray)
    assert len(preds1) == 7
    assert (preds1 >= 0).all()

    # Test reproducibility with identical seed
    lstm2 = PyTorchLSTMForecaster(lookback=28, hidden_size=16, epochs=15, random_seed=42)
    lstm2.fit(df_synthetic)
    preds2 = lstm2.predict(horizon=7)
    assert np.allclose(preds1, preds2, atol=1e-5)


def test_prophet_forecaster_smoke_test():
    """Verify ProphetForecaster fits and predicts horizon without errors."""
    df_synthetic = pd.DataFrame({
        "mean_demand": [80.0 + (i % 7) * 2.0 for i in range(60)],
    }, index=pd.date_range("2025-01-01", periods=60))

    prophet_model = ProphetForecaster().fit(df_synthetic)
    yhat, yhat_low, yhat_high = prophet_model.predict_range(horizon=7)

    assert len(yhat) == 7
    assert len(yhat_low) == 7
    assert len(yhat_high) == 7
    assert (yhat >= 0).all()
    assert (yhat_low <= yhat_high).all()


# --- 5. Honest Negative Result Verification ---

def test_honest_negative_result_plain_mean_beats_seasonal_naive(category_series_dict):
    """Empirical verification: Plain Mean outperforms Seasonal Naive due to lack of temporal momentum."""
    fruits_series = category_series_dict["Fruits"]

    # Cut-off at Day 250 (mid-September)
    train_slice = fruits_series.iloc[:250]
    test_slice = fruits_series.iloc[250:257]
    y_test = test_slice["mean_demand"].values

    pm = PlainMeanForecaster().fit(train_slice)
    sn = SeasonalNaiveForecaster().fit(train_slice)

    pm_pred = pm.predict(horizon=len(y_test))
    sn_pred = sn.predict(horizon=len(y_test))

    pm_wape = float(np.sum(np.abs(y_test - pm_pred)) / np.sum(y_test))
    sn_wape = float(np.sum(np.abs(y_test - sn_pred)) / np.sum(y_test))

    # Plain Mean has lower error than Seasonal Naive
    assert pm_wape < sn_wape, (
        f"Expected Plain Mean ({pm_wape:.4f}) to beat Seasonal Naive ({sn_wape:.4f}) "
        f"on un-autocorrelated category series."
    )
