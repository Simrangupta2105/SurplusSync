"""Unit tests for TASK 4: PYTORCH LSTM (CPU) (Time-series Track B).

Verifies:
1. PyTorchLSTMForecaster deterministic reproducibility with fixed random seed.
2. Non-negative predictions and valid 90% uncertainty intervals.
3. Rejection of Units_Sold as demand target.
4. Detection and rejection of data leakage columns.
5. Multivariate LSTM operation with exogenous covariates.
6. Multi-seed evaluation runner across fixed seeds.
7. Ablation study runner comparing lookbacks, capacities, and covariates.
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
        build_category_aggregate_series,
        split_train_test,
    )
    from ml_service.models.lstm_forecaster import (
        PyTorchLSTMForecaster,
        evaluate_lstm_multi_seed,
        run_lstm_ablation_study,
    )
except ModuleNotFoundError:
    from data.synthetic_panel import load_synthetic_panel
    from data.time_series_splits import (
        LeakageError,
        build_category_aggregate_series,
        split_train_test,
    )
    from models.lstm_forecaster import (
        PyTorchLSTMForecaster,
        evaluate_lstm_multi_seed,
        run_lstm_ablation_study,
    )


@pytest.fixture(scope="module")
def bakery_series() -> pd.DataFrame:
    """Load cleaned synthetic panel and extract Bakery category daily series."""
    panel_df = load_synthetic_panel()
    train_pool, _ = split_train_test(panel_df)
    cat_series = build_category_aggregate_series(train_pool)
    return cat_series["Bakery"]


# --- 1. Deterministic Reproducibility & Output Validity ---

def test_lstm_reproducibility_with_fixed_seed(bakery_series: pd.DataFrame):
    """Verify PyTorchLSTMForecaster produces identical predictions with identical seed."""
    train_slice = bakery_series.iloc[:200].copy()

    m1 = PyTorchLSTMForecaster(lookback=14, hidden_size=8, epochs=10, random_seed=42)
    m1.fit(train_slice)
    p1 = m1.predict(horizon=7)

    m2 = PyTorchLSTMForecaster(lookback=14, hidden_size=8, epochs=10, random_seed=42)
    m2.fit(train_slice)
    p2 = m2.predict(horizon=7)

    assert np.allclose(p1, p2, atol=1e-5), "Predictions from identical seeds must be identical"


def test_lstm_predict_interval_bounds(bakery_series: pd.DataFrame):
    """Verify 90% uncertainty intervals are non-negative and properly ordered."""
    train_slice = bakery_series.iloc[:250].copy()

    model = PyTorchLSTMForecaster(lookback=14, hidden_size=8, epochs=12, random_seed=123)
    model.fit(train_slice)

    preds, low, high = model.predict_interval(horizon=7, coverage=0.90)

    assert len(preds) == len(low) == len(high) == 7
    assert (preds >= 0.0).all()
    assert (low >= 0.0).all()
    assert (low <= high).all()


# --- 2. Invariant & Leakage Enforcement ---

def test_lstm_rejects_units_sold_as_target(bakery_series: pd.DataFrame):
    """Verify PyTorchLSTMForecaster rejects Units_Sold as demand target."""
    model = PyTorchLSTMForecaster()
    with pytest.raises(ValueError, match="CRITICAL INVARIANT VIOLATION"):
        model.fit(bakery_series, target_col="Units_Sold")


def test_lstm_rejects_leakage_columns(bakery_series: pd.DataFrame):
    """Verify PyTorchLSTMForecaster raises LeakageError if leakage columns appear in covariates."""
    bad_df = bakery_series.copy()
    bad_df["Remaining_Stock"] = 15.0

    model = PyTorchLSTMForecaster(
        use_covariates=True,
        covariate_cols=["Temperature_C", "Remaining_Stock"],
    )
    with pytest.raises(LeakageError, match="DATA LEAKAGE DETECTED"):
        model.fit(bad_df)


# --- 3. Multivariate Sequence Operation ---

def test_lstm_multivariate_with_covariates(bakery_series: pd.DataFrame):
    """Verify LSTM trains and forecasts with exogenous covariates."""
    train_slice = bakery_series.iloc[:250].copy()
    val_slice = bakery_series.iloc[250:257].copy()

    model = PyTorchLSTMForecaster(
        lookback=14,
        hidden_size=8,
        epochs=10,
        random_seed=42,
        use_covariates=True,
        covariate_cols=["Temperature_C", "Rain_mm", "Is_Weekend", "Is_Holiday"],
    )
    model.fit(train_slice)

    preds, low, high = model.predict_interval(horizon=7, future_covariates_df=val_slice)

    assert len(preds) == 7
    assert (preds >= 0.0).all()
    assert (low <= high).all()


# --- 4. Multi-Seed & Ablation Runners ---

def test_evaluate_lstm_multi_seed_smoke(bakery_series: pd.DataFrame):
    """Verify multi-seed evaluation runs across 2 seeds on rolling folds."""
    test_dict = {"Bakery": bakery_series.iloc[:350].copy()}

    res_df = evaluate_lstm_multi_seed(
        category_series=test_dict,
        seeds=[42, 123],
        horizon=7,
        n_splits=1,
        step=28,
    )

    assert len(res_df) == 2  # 2 seeds * 1 fold = 2 records
    assert set(res_df["seed"].unique()) == {42, 123}
    for col in ["wape", "mae", "rmse", "bias", "coverage"]:
        assert col in res_df.columns
        assert np.isfinite(res_df[col]).all()


def test_run_lstm_ablation_study_smoke(bakery_series: pd.DataFrame):
    """Verify ablation runner produces summary comparing architectures."""
    test_dict = {"Bakery": bakery_series.iloc[:300].copy()}

    ablation_summary = run_lstm_ablation_study(
        category_series=test_dict,
        horizon=7,
        n_splits=1,
        step=28,
    )

    assert len(ablation_summary) == 6  # 6 configurations
    assert "ablation_config" in ablation_summary.columns
    assert "wape" in ablation_summary.columns
    assert "mae" in ablation_summary.columns
    assert (ablation_summary["wape"] >= 0.0).all()
