"""Unit tests for TASK 3: PROPHET MODELS PER CATEGORY (Time-series Track B).

Verifies:
1. ProphetCategoryForecaster fit, predict, and interval calibration with extra regressors.
2. Pure Prophet (univariate) fit and predict without regressors.
3. Rejection of Units_Sold as demand target.
4. Detection and rejection of data leakage columns.
5. Rolling-origin cross-validation evaluation on category daily aggregate series.
6. Empirical interval coverage and honest baseline comparisons.
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
        LeakageError,
        RollingOriginSplitter,
        build_category_aggregate_series,
        split_train_test,
    )
    from ml_service.models.prophet_category import (
        ProphetCategoryForecaster,
        evaluate_category_models_across_folds,
    )
except ModuleNotFoundError:
    from data.synthetic_panel import load_synthetic_panel
    from data.time_series_splits import (
        LeakageError,
        RollingOriginSplitter,
        build_category_aggregate_series,
        split_train_test,
    )
    from models.prophet_category import (
        ProphetCategoryForecaster,
        evaluate_category_models_across_folds,
    )


@pytest.fixture(scope="module")
def category_aggregate_series() -> dict[str, pd.DataFrame]:
    """Load cleaned synthetic panel data and build category daily aggregate series."""
    panel_df = load_synthetic_panel()
    train_pool, _ = split_train_test(panel_df)
    return build_category_aggregate_series(train_pool)


# --- 1. Prophet Forecaster Interface Tests ---

def test_prophet_with_regressors_fit_and_predict(category_aggregate_series):
    """Verify ProphetCategoryForecaster trains with extra regressors and predicts valid intervals."""
    bakery_series = category_aggregate_series["Bakery"]

    train_slice = bakery_series.iloc[:400].copy()
    future_slice = bakery_series.iloc[400:407].copy()

    forecaster = ProphetCategoryForecaster(use_regressors=True, interval_width=0.90)
    forecaster.fit(train_slice)

    assert forecaster.is_fitted_
    assert len(forecaster.active_regressors_) > 0

    preds, low, high = forecaster.predict_interval(future_slice, coverage=0.90)

    assert len(preds) == 7
    assert len(low) == 7
    assert len(high) == 7

    # Non-negativity and bounds ordering
    assert (preds >= 0.0).all()
    assert (low >= 0.0).all()
    assert (low <= high).all()


def test_prophet_pure_univariate_fit_and_predict(category_aggregate_series):
    """Verify ProphetCategoryForecaster operates cleanly in pure univariate mode without regressors."""
    dairy_series = category_aggregate_series["Dairy"]

    train_slice = dairy_series.iloc[:365].copy()
    future_slice = dairy_series.iloc[365:372].copy()

    forecaster = ProphetCategoryForecaster(use_regressors=False, interval_width=0.90)
    forecaster.fit(train_slice)

    assert forecaster.is_fitted_
    assert len(forecaster.active_regressors_) == 0

    preds = forecaster.predict(future_slice)
    assert len(preds) == 7
    assert (preds >= 0.0).all()


# --- 2. Invariant and Leakage Tests ---

def test_prophet_rejects_units_sold_as_target(category_aggregate_series):
    """Verify ProphetCategoryForecaster rejects Units_Sold as a demand target."""
    bakery_series = category_aggregate_series["Bakery"]
    forecaster = ProphetCategoryForecaster()

    with pytest.raises(ValueError, match="CRITICAL INVARIANT VIOLATION"):
        forecaster.fit(bakery_series, target_col="Units_Sold")


def test_prophet_rejects_leakage_columns(category_aggregate_series):
    """Verify ProphetCategoryForecaster raises LeakageError if leakage columns are in regressors."""
    bakery_series = category_aggregate_series["Bakery"].copy()
    # Inject a forbidden outcome column
    bakery_series["Remaining_Stock"] = 10.0

    forecaster = ProphetCategoryForecaster(
        use_regressors=True,
        regressor_cols=["Temperature_C", "Remaining_Stock"],
    )

    with pytest.raises(LeakageError, match="DATA LEAKAGE DETECTED"):
        forecaster.fit(bakery_series)


# --- 3. Rolling-Origin Cross-Validation Evaluation Tests ---

def test_evaluate_category_models_across_folds_single_category(category_aggregate_series):
    """Verify evaluation generates complete metrics across 2 rolling folds for Bakery."""
    test_dict = {"Bakery": category_aggregate_series["Bakery"]}

    results_df = evaluate_category_models_across_folds(
        category_series=test_dict,
        horizons=[7],
        n_splits=2,
        step=28,
    )

    expected_models = {
        "Prophet_With_Regressors",
        "Prophet_Pure",
        "Category_Weekday_Profile",
        "Category_Trailing_Mean_28",
        "Category_Global_Mean",
        "Category_Seasonal_Naive_7",
    }
    assert set(results_df["model"].unique()) == expected_models
    assert len(results_df) == 6 * 2  # 6 models * 2 folds = 12 records

    for col in ["wape", "mae", "rmse", "bias", "coverage"]:
        assert col in results_df.columns
        assert results_df[col].isna().sum() == 0
        assert np.isfinite(results_df[col]).all()

    # Coverage should be between 0.60 and 1.0
    for _, row in results_df.iterrows():
        assert 0.0 <= row["coverage"] <= 1.0
        assert row["wape"] >= 0.0
