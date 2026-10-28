"""Unit tests for Task 5: Diebold-Mariano test, Paired Bootstrap, and Event Adaptation."""

import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from reports.task5_comparison_and_events import (
    diebold_mariano_test,
    paired_bootstrap_test,
    load_events_log,
    perform_event_adaptation_analysis,
)


def test_diebold_mariano_identical_errors():
    """Identical error series must produce 0 test statistic and p-value 1.0."""
    e = np.array([1.0, -2.0, 0.5, -0.5, 3.0, -1.0])
    dm_stat, p_val = diebold_mariano_test(e, e, h=1, criterion="mae")
    assert math.isclose(dm_stat, 0.0, abs_tol=1e-6)
    assert math.isclose(p_val, 1.0, abs_tol=1e-6)


def test_diebold_mariano_clear_superiority():
    """Model with much smaller errors should produce negative dm_stat with significant p-value."""
    np.random.seed(42)
    n = 200
    e_superior = np.random.normal(0, 1, size=n)
    e_inferior = np.random.normal(0, 10, size=n)

    dm_stat, p_val = diebold_mariano_test(e_superior, e_inferior, h=1, criterion="mae")
    assert dm_stat < -5.0
    assert p_val < 0.001


def test_diebold_mariano_lag_truncation():
    """Diebold-Mariano test should handle multi-step horizons (h > 1)."""
    np.random.seed(123)
    e1 = np.random.normal(0, 2, size=150)
    e2 = np.random.normal(0, 4, size=150)

    dm_stat, p_val = diebold_mariano_test(e1, e2, h=7, criterion="mae")
    assert dm_stat < 0
    assert 0.0 <= p_val <= 1.0


def test_paired_bootstrap_test_bounds():
    """Paired bootstrap test must return valid confidence interval and p-value."""
    np.random.seed(42)
    y_true = np.random.uniform(50, 150, size=200)
    y_pred_best = y_true + np.random.normal(0, 5, size=200)
    y_pred_comp = y_true + np.random.normal(0, 25, size=200)

    res = paired_bootstrap_test(y_true, y_pred_best, y_pred_comp, n_boot=500, seed=42)
    assert res["wape_best"] < res["wape_comp"]
    assert res["delta_wape"] < 0
    assert res["ci_95_low"] <= res["delta_wape"] <= res["ci_95_high"]
    assert res["ci_95_high"] < 0  # 95% CI strictly negative (best beats comp)
    assert res["p_value"] == 0.0


def test_load_events_log_expansion():
    """Events log loader must expand range strings ('start..end') into distinct daily rows."""
    events_df = load_events_log()
    assert len(events_df) > 400
    assert "date" in events_df.columns
    assert "event_type" in events_df.columns
    assert "multiplier" in events_df.columns
    assert pd.api.types.is_datetime64_any_dtype(events_df["date"])

    # Verify event types present
    unique_types = set(events_df["event_type"].unique())
    assert "shock" in unique_types
    assert "regime_slump" in unique_types
    assert "regime_boom" in unique_types


def test_event_adaptation_categorization():
    """Test event matching logic and regime onset vs sustained categorization."""
    # Synthetic mini pred_df
    dates = pd.date_range("2025-01-01", periods=10, freq="D")
    records = []
    for d in dates:
        records.append({
            "Date": d,
            "Shop_ID": "SHOP_01",
            "Food_Category": "Bakery",
            "Business_Type": "Bakery",
            "City": "Mumbai",
            "Daily_Demand": 100.0,
            "HistGradientBoosting_History": 95.0,
            "LightGBM_History": 90.0,
            "Global_LSTM": 85.0,
            "Prophet": 80.0,
            "Weekday_Profile": 75.0,
            "Seasonal_Naive_7": 70.0,
        })
    pred_df = pd.DataFrame(records)

    # Mini events df: 5-day slump regime
    events_df = pd.DataFrame([
        {"shop_id": "SHOP_01", "category": "Bakery", "date": pd.Timestamp(f"2025-01-0{i}"), "event_type": "regime_slump", "multiplier": 0.6}
        for i in range(1, 6)
    ])

    ev_summary, adapt_summary = perform_event_adaptation_analysis(pred_df, events_df)

    assert not ev_summary.empty
    assert set(ev_summary["Event_Type"].unique()).issubset({"Normal", "regime_slump"})

    assert not adapt_summary.empty
    phases = set(adapt_summary["Regime_Phase"].unique())
    assert "Onset (Days 1-3)" in phases
    assert "Sustained (Days 4+)" in phases
