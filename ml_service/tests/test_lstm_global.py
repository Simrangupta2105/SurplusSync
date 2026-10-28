"""Unit tests for Global Multi-Horizon PyTorch LSTM Forecaster (Task 3)."""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import torch

from models.fair_tabular_baselines import TabularFeatureEngine
from models.lstm_global import (
    GlobalLSTMForecaster,
    GlobalMultiHorizonLSTM,
    get_parameter_count,
)


@pytest.fixture
def sample_engine():
    """Create a minimal synthetic TabularFeatureEngine for fast unit testing."""
    dates = pd.date_range("2023-01-01", periods=100, freq="D")
    shops = [f"S{i:02d}" for i in range(1, 13)]
    cats = ["Bakery", "Dairy", "Produce", "Meat", "Pantry", "Prepared Meals"]

    rows = []
    rng = np.random.RandomState(42)
    for shop in shops:
        city = "CityA" if shop in shops[:3] else ("CityB" if shop in shops[3:6] else ("CityC" if shop in shops[6:9] else "CityD"))
        for cat in cats:
            base = rng.uniform(30, 80)
            for d in dates:
                rows.append({
                    "Date": d,
                    "Shop_ID": shop,
                    "Food_Category": cat,
                    "City": city,
                    "Business_Type": "Supermarket",
                    "Latitude": 12.97,
                    "Longitude": 77.59,
                    "Shelf_Life_Days": 5,
                    "Lead_Time_Days": 1,
                    "Daily_Demand": float(base + rng.poisson(10)),
                    "Promotion": "Yes" if rng.rand() > 0.8 else "No",
                    "Rain_mm": float(rng.exponential(2.0) if rng.rand() > 0.7 else 0.0),
                    "Temperature_C": float(25.0 + rng.normal(0, 3)),
                    "Weather": "Sunny",
                    "Festival": "no festival",
                    "Storage_Temperature": 4.0,
                    "Unit_Cost_INR": 40.0,
                    "Unit_Price_INR": 60.0,
                })
    df = pd.DataFrame(rows)
    return TabularFeatureEngine(df)


def test_parameter_counts():
    """Verify exact parameter counts for all 4 ablations."""
    m_a = GlobalMultiHorizonLSTM(use_covariates=False, use_embeddings=False, use_cross_series=False)
    m_b = GlobalMultiHorizonLSTM(use_covariates=True, use_embeddings=False, use_cross_series=False)
    m_c = GlobalMultiHorizonLSTM(use_covariates=True, use_embeddings=True, use_cross_series=False)
    m_d = GlobalMultiHorizonLSTM(use_covariates=True, use_embeddings=True, use_cross_series=True)

    p_a = get_parameter_count(m_a)
    p_b = get_parameter_count(m_b)
    p_c = get_parameter_count(m_c)
    p_d = get_parameter_count(m_d)

    assert p_a == 7047, f"Expected 7047 for Ablation A, got {p_a}"
    assert p_b == 12231, f"Expected 12231 for Ablation B, got {p_b}"
    assert p_c == 13391, f"Expected 13391 for Ablation C, got {p_c}"
    assert p_d == 13519, f"Expected 13519 for Ablation D, got {p_d}"


def test_forward_pass_shapes():
    """Verify output shape (B, 7) across all ablations."""
    batch_size = 16
    lookback = 28
    horizons = 7

    # Ablation A
    m_a = GlobalMultiHorizonLSTM(use_covariates=False, use_embeddings=False, use_cross_series=False)
    x_a = torch.randn(batch_size, lookback, 1)
    out_a = m_a(x_a)
    assert out_a.shape == (batch_size, horizons)

    # Ablation D (all features enabled)
    m_d = GlobalMultiHorizonLSTM(use_covariates=True, use_embeddings=True, use_cross_series=True)
    x_d = torch.randn(batch_size, lookback, 11)
    shop_idx = torch.randint(0, 12, (batch_size,))
    cat_idx = torch.randint(0, 6, (batch_size,))
    city_idx = torch.randint(0, 4, (batch_size,))
    fut_cov = torch.randn(batch_size, 63)
    out_d = m_d(x_d, shop_idx=shop_idx, cat_idx=cat_idx, city_idx=city_idx, fut_cov=fut_cov)
    assert out_d.shape == (batch_size, horizons)


def test_strict_no_leakage_by_perturbation(sample_engine):
    """Perturbing future demand (T+1..T+7) must have ZERO impact on predictions at origin T."""
    forecaster = GlobalLSTMForecaster(
        use_covariates=True,
        use_embeddings=True,
        use_cross_series=True,
        epochs=2,
        batch_size=64,
        random_seed=42,
    )
    # Fit on early origins
    train_origs = np.arange(28, 50)
    forecaster.fit(sample_engine, train_origs, stride=1)

    eval_origin = 50
    preds_before = forecaster.predict(sample_engine, [eval_origin])

    # Severely perturb future targets at T+1 .. T+7
    original_future = sample_engine.demand_arr[eval_origin + 1 : eval_origin + 8, :].copy()
    sample_engine.demand_arr[eval_origin + 1 : eval_origin + 8, :] += 5000.0

    preds_after = forecaster.predict(sample_engine, [eval_origin])

    # Restore data
    sample_engine.demand_arr[eval_origin + 1 : eval_origin + 8, :] = original_future

    np.testing.assert_allclose(
        preds_before,
        preds_after,
        atol=1e-5,
        err_msg="Strict leakage test failed: mutating future demand altered origin T forecast!",
    )


def test_fit_predict_interval_bounds(sample_engine):
    """Verify non-negativity and interval bounds lower <= point <= upper (almost surely)."""
    forecaster = GlobalLSTMForecaster(
        use_covariates=False,
        use_embeddings=False,
        use_cross_series=False,
        epochs=3,
        batch_size=64,
        random_seed=123,
    )
    train_origs = np.arange(28, 60)
    forecaster.fit(sample_engine, train_origs, stride=2)

    eval_orig = 65
    preds = forecaster.predict(sample_engine, [eval_orig])
    lower, upper = forecaster.predict_interval(sample_engine, [eval_orig])

    assert np.all(preds >= 0.0), "Predicted demand must be non-negative"
    assert np.all(lower >= 0.0), "Lower bound must be non-negative"
    assert np.all(upper >= lower), "Upper bound must be >= lower bound"
