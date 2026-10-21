"""Unit and integration tests for Task 5: Dataset Calibration & Synthetic Ledger configuration.

Verifies:
1. compute_calibration_parameters() extracts all required empirical distributions.
2. Parameter invariants:
   - Business type scales (Supermarket > Restaurant > Cafeteria)
   - Promotion lift > 1.20
   - Weather multipliers (Rainy dampens demand, Hot/Sunny increases demand)
   - Category waste rates and reason mixes match empirical limits
   - Donation probability given waste (~23%) and strictly zero donation when waste is 0
   - Purchase/demand ratio median ~1.14
3. YAML serialization and deserialization integrity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

import pytest
import yaml

from ml_service.data.calibration import (
    DEFAULT_CALIBRATION_PATH,
    compute_calibration_parameters,
    generate_calibration_yaml,
    load_calibration_config,
)
from ml_service.data.food_waste import DEFAULT_DATASET_PATH, load_raw_data


@pytest.fixture(scope="module")
def raw_df():
    return load_raw_data(DEFAULT_DATASET_PATH)


@pytest.fixture(scope="module")
def calib_config(raw_df):
    return compute_calibration_parameters(raw_df)


def test_calibration_business_type_scales(calib_config: Dict[str, Any]) -> None:
    """Verify relative business scale rankings and reasonable bounds."""
    biz = calib_config["business_types"]
    assert set(biz.keys()) == {"Restaurant", "Supermarket", "Cafeteria", "Cloud Kitchen"}

    # Supermarket has highest volume, Cafeteria lowest
    assert biz["Supermarket"]["relative_scale"] > 1.30
    assert biz["Supermarket"]["relative_scale"] > biz["Restaurant"]["relative_scale"]
    assert biz["Restaurant"]["relative_scale"] > biz["Cafeteria"]["relative_scale"]
    assert biz["Cafeteria"]["relative_scale"] < 0.75


def test_calibration_promotion_lift(calib_config: Dict[str, Any]) -> None:
    """Verify promotion lift is positive and within empirical bounds (1.25 to 1.45)."""
    promo = calib_config["promotion"]
    assert "lift_multiplier" in promo
    lift = promo["lift_multiplier"]
    assert 1.25 < lift < 1.45
    assert promo["mean_demand_promo_yes"] > promo["mean_demand_promo_no"]
    assert promo["pct_increase"] > 25.0


def test_calibration_weather_multipliers(calib_config: Dict[str, Any]) -> None:
    """Verify weather multipliers: Rainy dampens demand (< 0.85), Sunny/Hot lifts demand (> 1.05)."""
    weather = calib_config["weather"]
    assert set(weather.keys()) == {"Sunny", "Rainy", "Cloudy", "Hot", "Unknown"}

    assert weather["Rainy"]["multiplier"] < 0.85
    assert weather["Sunny"]["multiplier"] > 1.05
    assert weather["Hot"]["multiplier"] > 1.05


def test_calibration_category_waste_and_shelf_life(calib_config: Dict[str, Any]) -> None:
    """Verify category waste rates and shelf life distributions."""
    cats = calib_config["categories"]
    expected_categories = {"Bakery", "Dairy", "Fruits", "Meat", "Prepared Food", "Vegetables"}
    assert set(cats.keys()) == expected_categories

    for cat_name, data in cats.items():
        # Waste rate of purchase is between 3% and 9%
        assert 0.03 <= data["waste_rate_of_purchase"] <= 0.09
        # Waste rate of remaining stock is between 18% and 42%
        assert 0.18 <= data["waste_rate_of_remaining"] <= 0.42

        # Waste reason mix contains all 5 reasons summing to ~1.0
        reasons = data["waste_reason_mix"]
        assert len(reasons) == 5
        assert pytest.approx(sum(reasons.values()), abs=0.01) == 1.0

        # Shelf life sanity
        sl = data["shelf_life_days"]
        assert 1.0 <= sl["min"] <= sl["median"] <= sl["max"] <= 14.0


def test_calibration_donation_invariants(calib_config: Dict[str, Any]) -> None:
    """CRITICAL INVARIANT: Donation strictly 0 when waste is 0, ~23% when waste > 0."""
    don = calib_config["donation"]
    assert 0.20 <= don["p_donation_given_waste"] <= 0.27
    assert don["p_donation_given_zero_waste"] == 0.0


def test_calibration_purchase_demand_ratio(calib_config: Dict[str, Any]) -> None:
    """Verify purchase/demand ratio distribution."""
    pdr = calib_config["purchase_demand_ratio"]
    assert 1.05 <= pdr["median"] <= 1.25
    assert 1.10 <= pdr["mean"] <= 1.30
    assert pdr["std"] > 0.15


def test_calibration_yaml_roundtrip(tmp_path: Path, raw_df) -> None:
    """Verify YAML configuration file generates, saves, and reloads without loss."""
    test_yaml = tmp_path / "test_calibration.yaml"
    saved_path = generate_calibration_yaml(raw_dataset_path=DEFAULT_DATASET_PATH, output_path=test_yaml)
    assert saved_path.exists()

    loaded = load_calibration_config(saved_path)
    assert loaded["meta"]["total_records"] == 8000
    assert "Supermarket" in loaded["business_types"]
    assert "lift_multiplier" in loaded["promotion"]
    assert DEFAULT_CALIBRATION_PATH.exists()
