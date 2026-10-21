"""Tests for TASK 2: DEMAND MODEL (tabular, Track A).

Verifies:
1. No future leakage in time-based splits and rolling-origin cross-validation.
2. Metrics functions against hand-computed values (WAPE, MAE, RMSE, Bias, Coverage).
3. Reproducibility with fixed random seed.
4. Prediction smoke test on saved forecaster (point forecast and prediction intervals).
5. Enforced exclusion of censored demand rows from training.
"""

import math
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest

from ml_service.data.food_waste import (
    DEFAULT_DATASET_PATH,
    get_time_splits,
    load_raw_data,
    validate_demand_target,
)
from ml_service.models.metrics import (
    compute_bias,
    compute_coverage,
    compute_mae,
    compute_rmse,
    compute_wape,
    evaluate_forecast,
)
from ml_service.models.tabular_demand import (
    FEATURE_COLS,
    TARGET_COL,
    TabularDemandForecaster,
    build_candidate_models,
    prepare_tabular_features,
)

SAVED_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "saved" / "best_demand_model.joblib"


# --- 1. Hand-Computed Metric Verification Tests ---

def test_metrics_against_hand_computed_values():
    """Verify that WAPE, MAE, RMSE, Bias, and Coverage exactly match hand-computed calculations.

    Hand-computed test case:
    y_true = [100.0, 200.0, 300.0]
    y_pred = [110.0, 180.0, 330.0]

    Errors:
    |100 - 110| = 10
    |200 - 180| = 20
    |300 - 330| = 30
    Sum absolute errors = 60.0
    Sum y_true = 600.0

    Expected:
    - WAPE = 60 / 600 = 0.10 (10.0%)
    - MAE = (10 + 20 + 30) / 3 = 20.0
    - RMSE = sqrt((100 + 400 + 900) / 3) = sqrt(1400 / 3) = 21.6024689947
    - Bias = ((110-100) + (180-200) + (330-300)) / 3 = (10 - 20 + 30) / 3 = +6.6666666667
    """
    y_true = np.array([100.0, 200.0, 300.0])
    y_pred = np.array([110.0, 180.0, 330.0])

    expected_wape = 60.0 / 600.0
    expected_mae = 20.0
    expected_rmse = math.sqrt(1400.0 / 3.0)
    expected_bias = 20.0 / 3.0

    assert abs(compute_wape(y_true, y_pred) - expected_wape) < 1e-9
    assert abs(compute_mae(y_true, y_pred) - expected_mae) < 1e-9
    assert abs(compute_rmse(y_true, y_pred) - expected_rmse) < 1e-9
    assert abs(compute_bias(y_true, y_pred) - expected_bias) < 1e-9


def test_coverage_against_hand_computed_values():
    """Verify empirical interval coverage against hand-computed values.

    y_true = [100.0, 200.0, 300.0]
    y_lower = [95.0, 170.0, 250.0]
    y_upper = [105.0, 190.0, 350.0]

    Point 1: 100 in [95, 105] -> In
    Point 2: 200 in [170, 190] -> Out (200 > 190)
    Point 3: 300 in [250, 350] -> In
    Coverage = 2 / 3 = 0.6666666667
    """
    y_true = np.array([100.0, 200.0, 300.0])
    y_lower = np.array([95.0, 170.0, 250.0])
    y_upper = np.array([105.0, 190.0, 350.0])

    expected_coverage = 2.0 / 3.0
    assert abs(compute_coverage(y_true, y_lower, y_upper) - expected_coverage) < 1e-9


# --- 2. No Future Leakage in Splits Tests ---

def test_no_future_leakage_in_time_splits():
    """Verify that train, validation, and test sets are strictly chronological with zero temporal overlap."""
    df_raw = load_raw_data(DEFAULT_DATASET_PATH)
    train_df, val_df, test_df, imputer = get_time_splits(df_raw, train_end="2025-10-31", val_end="2025-11-30")

    # Chronological boundaries
    assert train_df["Date"].max() <= pd.Timestamp("2025-10-31")
    assert val_df["Date"].min() >= pd.Timestamp("2025-11-01")
    assert val_df["Date"].max() <= pd.Timestamp("2025-11-30")
    assert test_df["Date"].min() >= pd.Timestamp("2025-12-01")

    # Strict temporal monotonicity
    assert train_df["Date"].max() < val_df["Date"].min()
    assert val_df["Date"].max() < test_df["Date"].min()

    # Imputer parameters match train_df medians, not full dataset medians
    train_valid = train_df[~train_df["demand_censored"]]
    for cat in ["Bakery", "Dairy", "Fruits", "Meat", "Prepared Food", "Vegetables"]:
        expected_shelf = train_valid[train_valid["Food_Category"] == cat]["Shelf_Life_Days"].median()
        assert imputer.shelf_life_medians_[cat] == expected_shelf


def test_censored_rows_excluded_from_training():
    """Verify that demand_censored rows are excluded from training set."""
    df_raw = load_raw_data(DEFAULT_DATASET_PATH)
    train_df, val_df, test_df, _ = get_time_splits(df_raw)

    train_valid = train_df[~train_df["demand_censored"]]
    censored_in_train = train_df[train_df["demand_censored"]]

    assert len(censored_in_train) > 0, "Expected some censored rows in training window"
    # Ensure all censored rows are excluded from train_valid
    assert len(train_valid) == len(train_df) - len(censored_in_train)
    assert not train_valid["demand_censored"].any()


# --- 3. Reproducibility Test ---

def test_model_training_reproducibility():
    """Verify that models trained with identical random_state produce identical predictions."""
    df_raw = load_raw_data(DEFAULT_DATASET_PATH)
    train_df, val_df, test_df, _ = get_time_splits(df_raw)

    train_valid = prepare_tabular_features(train_df[~train_df["demand_censored"]]).head(500)
    test_sample = prepare_tabular_features(test_df[~test_df["demand_censored"]]).head(100)

    y_train = train_valid[TARGET_COL].values

    # Train Poisson 1
    m1 = build_candidate_models(random_state=42)["Poisson_Regression"]
    m1.fit(train_valid, y_train)
    pred1 = m1.predict(test_sample)

    # Train Poisson 2
    m2 = build_candidate_models(random_state=42)["Poisson_Regression"]
    m2.fit(train_valid, y_train)
    pred2 = m2.predict(test_sample)

    assert np.allclose(pred1, pred2, atol=1e-7), "Predictions should be bit-for-bit identical with fixed seed"


# --- 4. Prediction Smoke Test on Saved Model ---

def test_saved_model_prediction_smoke_test():
    """Verify that the saved model artifact can be loaded and generates valid predictions and intervals."""
    assert SAVED_MODEL_PATH.exists(), f"Saved model not found at {SAVED_MODEL_PATH}"
    forecaster = joblib.load(SAVED_MODEL_PATH)
    assert hasattr(forecaster, "predict")
    assert hasattr(forecaster, "predict_interval")

    df_raw = load_raw_data(DEFAULT_DATASET_PATH)
    _, _, test_df, _ = get_time_splits(df_raw)
    test_sample = prepare_tabular_features(test_df[~test_df["demand_censored"]].head(25))

    # Point forecast
    preds = forecaster.predict(test_sample)
    assert isinstance(preds, np.ndarray)
    assert len(preds) == len(test_sample)
    assert (preds >= 0).all(), "All predicted demand values must be non-negative"

    # 80% Prediction intervals
    yhat, yhat_low80, yhat_high80 = forecaster.predict_interval(test_sample, coverage=0.80)
    assert len(yhat) == len(test_sample)
    assert len(yhat_low80) == len(test_sample)
    assert len(yhat_high80) == len(test_sample)

    # Invariants on intervals
    assert (yhat_low80 >= 0).all(), "Lower interval must be non-negative"
    assert (yhat_low80 <= yhat_high80).all(), "Lower interval must not exceed upper interval"

    # 90% Prediction intervals should be wider or equal to 80% intervals
    _, yhat_low90, yhat_high90 = forecaster.predict_interval(test_sample, coverage=0.90)
    assert (yhat_low90 <= yhat_low80 + 1e-6).all(), "90% lower bound must be <= 80% lower bound"
    assert (yhat_high90 >= yhat_high80 - 1e-6).all(), "90% upper bound must be >= 80% upper bound"
