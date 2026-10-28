"""Unit tests for Classic Baselines and Prophet Forecasters (Task 4)."""

import numpy as np
import pandas as pd
import pytest

from models.classic_and_prophet import (
    ClassicPanelBaselines,
    ProphetCategoryForecaster,
)
from models.fair_tabular_baselines import TabularFeatureEngine


@pytest.fixture
def sample_engine():
    """Create a minimal synthetic TabularFeatureEngine for testing."""
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
                    "Festival": "Diwali" if d.day == 15 else "no festival",
                    "Storage_Temperature": 4.0,
                    "Unit_Cost_INR": 40.0,
                    "Unit_Price_INR": 60.0,
                })
    df = pd.DataFrame(rows)
    return TabularFeatureEngine(df)


def test_classic_baselines_shapes_and_bounds(sample_engine):
    """Verify all 4 classic baselines generate valid shapes and non-negative bounds."""
    baselines = ClassicPanelBaselines(sample_engine)
    origin = 50

    for b in ["naive_1", "naive_7", "rolling_mean_28", "weekday_profile"]:
        for h in [1, 7]:
            point, low, high = baselines.predict([origin], horizon=h, baseline_type=b)
            assert point.shape == (72,)
            assert low.shape == (72,)
            assert high.shape == (72,)
            assert np.all(point >= 0.0), f"{b} point prediction must be non-negative"
            assert np.all(low >= 0.0), f"{b} lower interval must be non-negative"
            assert np.all(high >= low), f"{b} upper interval must be >= lower"


def test_seasonal_naive_temporal_boundary(sample_engine):
    """Verify Naive-1 and Naive-7 strictly access past data <= origin T."""
    baselines = ClassicPanelBaselines(sample_engine)
    T = 60

    # Mutate future targets T+1 .. T+7
    orig_future = sample_engine.demand_arr[T + 1 : T + 8, :].copy()
    sample_engine.demand_arr[T + 1 : T + 8, :] += 10000.0

    p_n1, _, _ = baselines.predict([T], horizon=1, baseline_type="naive_1")
    p_n7_h1, _, _ = baselines.predict([T], horizon=1, baseline_type="naive_7")
    p_n7_h7, _, _ = baselines.predict([T], horizon=7, baseline_type="naive_7")

    # Restore data
    sample_engine.demand_arr[T + 1 : T + 8, :] = orig_future

    p_n1_clean, _, _ = baselines.predict([T], horizon=1, baseline_type="naive_1")
    p_n7_h1_clean, _, _ = baselines.predict([T], horizon=1, baseline_type="naive_7")
    p_n7_h7_clean, _, _ = baselines.predict([T], horizon=7, baseline_type="naive_7")

    np.testing.assert_array_equal(p_n1, p_n1_clean)
    np.testing.assert_array_equal(p_n7_h1, p_n7_h1_clean)
    np.testing.assert_array_equal(p_n7_h7, p_n7_h7_clean)


def test_prophet_category_fit_predict():
    """Verify ProphetCategoryForecaster trains with festivals and regressors."""
    dates = pd.date_range("2023-01-01", periods=120, freq="D")
    df_cat = pd.DataFrame({
        "Date": dates,
        "Daily_Demand": 100.0 + 20.0 * np.sin(np.arange(120) * 2 * np.pi / 7.0),
        "Temperature_C": 25.0 + np.random.randn(120),
        "Rain_mm": np.random.exponential(1.0, 120),
        "promo_num": (np.random.rand(120) > 0.8).astype(float),
    })

    holidays = pd.DataFrame({
        "ds": pd.to_datetime(["2023-01-15", "2023-02-14"]),
        "holiday": ["Diwali", "Eid"],
        "lower_window": 0,
        "upper_window": 1,
    })

    m = ProphetCategoryForecaster(holidays_df=holidays, use_regressors=True, interval_width=0.90)
    m.fit(df_cat.iloc[:100])

    assert m.is_fitted_
    future_df = df_cat.iloc[100:107]
    yhat, low, high = m.predict(future_df)

    assert len(yhat) == 7
    assert len(low) == 7
    assert len(high) == 7
    assert np.all(yhat >= 0.0)
    assert np.all(low >= 0.0)
    assert np.all(high >= low)
