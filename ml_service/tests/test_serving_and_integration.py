"""Tests for Task 6: Serving and Integration.

Covers:
1. Model serialization integrity (joblib artifact, metadata schema, test metrics).
2. ModelRegistry export & sequence feature engineering (lags, rolling stats, cyclic transforms, fallback priors).
3. FastAPI Endpoints (/predict/demand, /predict/inventory-plan, /registry/status).
4. Backward compatibility (/v1/plan, /v1/insights/dataset, /health).
5. Downstream reorder simulation integrity and counterfactual metrics labeling.
"""

import json
import math
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from ml_service.app import DEFAULT_SERVICE_TOKEN, app, clear_model_cache
from ml_service.models.registry import ModelRegistry, get_registry_status
from ml_service.scoring.reorder import (
    COUNTERFACTUAL_ASSUMPTIONS,
    ReorderRecommendation,
    compute_recommended_reorder,
)


@pytest.fixture
def client():
    clear_model_cache()
    return TestClient(app)


@pytest.fixture
def valid_headers():
    token = os.getenv("ML_SERVICE_TOKEN", DEFAULT_SERVICE_TOKEN)
    return {"X-Service-Token": token}


# ============================================================================
# 1. Model Serialization & Registry Export
# ============================================================================

def test_serialized_model_and_metadata_exist():
    """Verify serialized model artifacts exist and have required metadata schema."""
    saved_dir = Path(__file__).resolve().parent.parent / "models" / "saved"
    model_path = saved_dir / "best_synthetic_sequence_demand_model.joblib"
    meta_path = saved_dir / "best_synthetic_sequence_demand_model_metadata.json"

    assert model_path.exists(), f"Missing serialized model: {model_path}"
    assert meta_path.exists(), f"Missing metadata: {meta_path}"

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["model_name"] == "HistGradientBoosting_History"
    assert "metrics" in meta
    assert "test_wape" in meta["metrics"]
    assert meta["metrics"]["test_wape"] < 0.20  # WAPE ~0.133
    assert len(meta["feature_names"]) == 56


def test_registry_loads_active_model_and_status():
    """Verify ModelRegistry correctly loads model and returns status."""
    registry = ModelRegistry()
    assert registry.is_model_available()

    model = registry.get_active_model()
    assert model is not None

    status = get_registry_status()
    assert status["registry_status"] == "active"
    assert "HistGradientBoosting_History" in status["active_model_name"]
    assert status["total_features"] == 56
    assert "Bakery" in status["supported_categories"]


def test_registry_sequence_feature_preparation():
    """Verify sequence feature prep handles historical sales, rolling windows, and calendar features."""
    registry = ModelRegistry()
    recent_history = [120.0, 115.0, 130.0, 125.0, 140.0, 110.0, 105.0]  # 7 days

    feats = registry.prepare_sequence_features(
        shop_id="SHOP_001",
        category="Bakery",
        business_type="Restaurant",
        target_date="2026-03-15",
        promo=True,
        weather="Rainy",
        city="North",
        historical_sales=recent_history,
    )

    assert feats.shape[0] == 1
    assert feats.shape[1] == 56
    # Verify lag 1 is the most recent sales value (105.0)
    assert feats["demand_lag_1"].iloc[0] == 105.0
    # Verify rolling 7-day mean
    assert pytest.approx(feats["rolling_mean_7"].iloc[0], rel=1e-3) == sum(recent_history) / 7.0
    # Verify cyclical day of year
    assert "sin_doy" in feats.columns
    assert "cos_doy" in feats.columns


def test_registry_fallback_prior_when_no_history():
    """When historical sales are empty, fallback prior should default safely."""
    registry = ModelRegistry()
    feats = registry.prepare_sequence_features(
        shop_id="SHOP_999",
        category="Vegetables",
        business_type="Supermarket",
        target_date="2026-05-01",
        promo=False,
        weather="Sunny",
        historical_sales=[],
    )
    assert feats.shape[0] == 1
    # Fallback prior produces valid non-null floats
    assert not feats.isna().any().any()
    assert feats["demand_lag_1"].iloc[0] > 0


# ============================================================================
# 2. FastAPI Endpoints: /predict/demand
# ============================================================================

def test_predict_demand_h1_success(client, valid_headers):
    """Test point forecast + 90% confidence range for horizon = 1."""
    payload = {
        "shop_id": "SHOP_001",
        "category": "Bakery",
        "business_type": "Restaurant",
        "date": "2026-04-10",
        "horizon": 1,
        "promotion": True,
        "weather": "Sunny",
        "historical_sales": [95.0, 102.0, 110.0, 108.0, 115.0, 120.0, 118.0],
    }
    res = client.post("/predict/demand", json=payload, headers=valid_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["shop_id"] == "SHOP_001"
    assert data["category"] == "Bakery"
    assert data["horizon_days"] == 1
    assert len(data["predictions"]) == 1

    p1 = data["predictions"][0]
    assert p1["step"] == 1
    assert p1["forecast_demand"] > 0
    assert p1["forecast_range"]["min"] <= p1["forecast_demand"] <= p1["forecast_range"]["max"]
    assert "confidence_std" in p1


def test_predict_demand_multi_day_horizon(client, valid_headers):
    """Test multi-day recursive rollout for horizon = 7."""
    payload = {
        "shop_id": "SHOP_002",
        "category": "Prepared Food",
        "business_type": "Cafe",
        "date": "2026-04-10",
        "horizon": 7,
        "promotion": False,
        "weather": "Rainy",
        "historical_sales": [75.0, 80.0, 82.0, 78.0, 85.0, 88.0, 90.0],
    }
    res = client.post("/predict/demand", json=payload, headers=valid_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["horizon_days"] == 7
    assert len(data["predictions"]) == 7
    # All steps should have valid non-negative forecasts
    for i, p in enumerate(data["predictions"]):
        assert p["step"] == i + 1
        assert p["forecast_demand"] >= 0


def test_predict_demand_invalid_horizon_fails(client, valid_headers):
    """Horizon outside 1..14 should be rejected by validation."""
    payload = {
        "shop_id": "SHOP_001",
        "category": "Bakery",
        "horizon": 30,  # invalid
    }
    res = client.post("/predict/demand", json=payload, headers=valid_headers)
    assert res.status_code == 422


# ============================================================================
# 3. FastAPI Endpoints: /predict/inventory-plan
# ============================================================================

def test_predict_inventory_plan_reorder_calculation(client, valid_headers):
    """Test full inventory plan with safety stock, shelf-life cap, and explanation."""
    payload = {
        "shop_id": "SHOP_003",
        "category": "Dairy",
        "business_type": "Supermarket",
        "sellable_on_hand": 30.0,
        "on_order": 0.0,
        "shelf_life_days": 5,
        "service_level": 0.90,
        "historical_sales": [120.0, 115.0, 125.0, 130.0, 128.0, 135.0, 140.0],
    }
    res = client.post("/predict/inventory-plan", json=payload, headers=valid_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["recommended_order_quantity"] >= 0
    assert data["forecast_demand"] > 0
    assert data["safety_stock"] > 0
    assert "waste_risk" in data
    assert "explanation" in data
    assert data["service_level"] == 0.90


def test_predict_inventory_plan_shelf_life_capping(client, valid_headers):
    """Prepared food with short shelf life (2 days) triggers shelf-life safety cap."""
    payload = {
        "shop_id": "SHOP_004",
        "category": "Prepared Food",
        "sellable_on_hand": 0.0,
        "shelf_life_days": 2,  # Very short shelf life
        "service_level": 0.99,  # High service level would otherwise demand huge safety stock
        "historical_sales": [50.0] * 14,
    }
    res = client.post("/predict/inventory-plan", json=payload, headers=valid_headers)
    assert res.status_code == 200
    data = res.json()

    # Shelf-life cap is 0.70 * shelf_life * forecast = 0.70 * 2 * forecast = 1.4 * forecast
    # Recommended order must be constrained by the shelf-life cap
    assert data["shelf_life_cap"] is not None
    assert data["shelf_cap_applied"] is True
    assert data["recommended_order_quantity"] <= math.ceil(data["shelf_life_cap"]) + 1


# ============================================================================
# 4. Registry Status & Health Endpoints
# ============================================================================

def test_registry_status_endpoint(client, valid_headers):
    """Test GET /registry/status returns live registry metadata."""
    res = client.get("/registry/status", headers=valid_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["registry_status"] == "active"
    assert "HistGradientBoosting" in data["active_model_name"]


def test_backward_compatibility_v1_plan(client, valid_headers):
    """Existing POST /v1/plan must maintain backward compatibility."""
    payload = {
        "org_id": 1,
        "category": "Bakery",
        "planned_quantity": 100.0,
        "promotion": True,
        "weather": "Sunny",
        "business_type": "Restaurant",
    }
    res = client.post("/v1/plan", json=payload, headers=valid_headers)
    assert res.status_code == 200
    data = res.json()
    assert "forecast_demand" in data
    assert "predicted_waste_level" in data
    assert "recommended_quantity" in data


# ============================================================================
# 5. Downstream Reorder Simulation & Counterfactual Labeling
# ============================================================================

def test_reorder_simulation_metrics_artifacts_exist():
    """Verify Task 6 simulation generated required CSV and chart artifacts with correct labeling."""
    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    macro_csv = reports_dir / "reorder_simulation_metrics_task6.csv"
    cat_csv = reports_dir / "reorder_simulation_by_category_task6.csv"
    plot_png = reports_dir / "figures" / "reorder_simulation_comparison_task6.png"

    assert macro_csv.exists(), f"Missing {macro_csv}"
    assert cat_csv.exists(), f"Missing {cat_csv}"
    assert plot_png.exists(), f"Missing {plot_png}"

    import pandas as pd
    df = pd.read_csv(macro_csv)
    # Must contain both operator and 3 AI policies
    assert len(df) == 4
    assert "Actual Operator" in df["policy"].values
    assert "AI Reorder (90% SL)" in df["policy"].values
    assert "counterfactual_waste_estimate" in df.columns


def test_reorder_recommendation_unit_logic():
    """Verify compute_recommended_reorder adheres to safety stock and caps."""
    rec = compute_recommended_reorder(
        product_name="Croissant",
        forecast_demand=100.0,
        sellable_on_hand=20.0,
        on_order=10.0,
        lead_time_days=1,
        shelf_life_days=3,
        service_level=0.90,
        forecast_error_std=15.0,
        pack_size=5,
    )
    assert isinstance(rec, ReorderRecommendation)
    assert rec.recommended_order_quantity >= 0
    # Pack size rounding
    assert rec.recommended_order_quantity % 5 == 0
    # Must include counterfactual disclaimer
    assert len(rec.counterfactual_assumptions) == len(COUNTERFACTUAL_ASSUMPTIONS)
