"""Tests for FastAPI ML Service endpoints (/v1/plan and /v1/insights/dataset)."""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ml_service.app import DEFAULT_SERVICE_TOKEN, app, clear_model_cache


@pytest.fixture
def client():
    clear_model_cache()
    return TestClient(app)


@pytest.fixture
def valid_headers():
    token = os.getenv("ML_SERVICE_TOKEN", DEFAULT_SERVICE_TOKEN)
    return {"X-Service-Token": token}


def test_health_check(client):
    """Health check endpoint returns status."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "models_present" in data


def test_auth_missing_token_returns_401(client):
    """Endpoints require X-Service-Token header."""
    res = client.post("/v1/plan", json={"org_id": 1, "category": "Bakery", "planned_quantity": 50})
    assert res.status_code == 401
    assert "Invalid or missing service token" in res.json()["detail"]

    res2 = client.get("/v1/insights/dataset")
    assert res2.status_code == 401


def test_auth_invalid_token_returns_401(client):
    """Incorrect X-Service-Token is rejected."""
    headers = {"X-Service-Token": "completely-wrong-token-abc"}
    res = client.post("/v1/plan", json={"org_id": 1, "category": "Bakery", "planned_quantity": 50}, headers=headers)
    assert res.status_code == 401


def test_plan_valid_request(client, valid_headers):
    """Valid plan request returns complete prediction payload."""
    payload = {
        "org_id": 42,
        "category": "Bakery",
        "planned_quantity": 100.0,
        "promotion": True,
        "weather": "Sunny",
        "date": "2026-10-21",
        "business_type": "Restaurant",
    }
    res = client.post("/v1/plan", json=payload, headers=valid_headers)
    assert res.status_code == 200
    data = res.json()

    assert "forecast_demand" in data
    assert isinstance(data["forecast_demand"], (int, float))
    assert data["forecast_demand"] > 0

    assert "forecast_range" in data
    assert data["forecast_range"]["min"] <= data["forecast_demand"] <= data["forecast_range"]["max"]

    assert "over_order_ratio" in data
    assert data["over_order_ratio"] > 0

    assert "predicted_waste_level" in data
    assert data["predicted_waste_level"] in {"Low", "Medium", "High"}

    assert "waste_probabilities" in data
    assert set(data["waste_probabilities"].keys()) == {"Low", "Medium", "High"}
    prob_sum = sum(data["waste_probabilities"].values())
    assert 0.98 <= prob_sum <= 1.02

    assert "recommended_quantity" in data
    assert isinstance(data["recommended_quantity"], int)
    assert data["recommended_quantity"] > 0

    assert "explanation" in data
    assert "Bakery" in data["explanation"]
    assert "units" in data["explanation"]

    assert "model_name" in data
    assert data["model_name"] in {"HistGradientBoosting_History", "HistGradientBoostingDemandModel", "Poisson_Regression"}

    assert "model_version" in data
    assert len(data["model_version"]) > 0

    assert "confidence_note" in data

    assert "data_origin" in data
    assert data["data_origin"].startswith("synthetic")
    assert "training_data_note" in data
    assert data["training_data_note"] == "Trained on synthetic demonstration data"
    assert "generated_at" in data


def test_plan_excessive_order_predicts_high_waste(client, valid_headers):
    """Order quantity drastically higher than demand triggers High waste risk."""
    payload = {
        "org_id": 10,
        "category": "Prepared Food",
        "planned_quantity": 600.0,
        "promotion": False,
        "weather": "Rainy",
        "business_type": "Cafeteria",
    }
    res = client.post("/v1/plan", json=payload, headers=valid_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["over_order_ratio"] > 3.0
    assert data["predicted_waste_level"] == "High"
    assert data["waste_probabilities"]["High"] > 0.50


def test_plan_missing_optional_inputs_fallbacks(client, valid_headers):
    """Missing optional fields use defaults and are logged in confidence_note."""
    payload = {
        "org_id": 5,
        "category": "Dairy",
        "planned_quantity": 80.0,
        # promotion, weather, date, business_type omitted
    }
    res = client.post("/v1/plan", json=payload, headers=valid_headers)
    assert res.status_code == 200
    data = res.json()
    assert "Weather condition not specified" in data["confidence_note"]
    assert "Business type not provided" in data["confidence_note"]


def test_plan_category_alias_mapping(client, valid_headers):
    """Category alias like 'produce' maps to 'Vegetables' and notes the mapping."""
    payload = {
        "org_id": 7,
        "category": "Produce",
        "planned_quantity": 120.0,
        "business_type": "Supermarket",
    }
    res = client.post("/v1/plan", json=payload, headers=valid_headers)
    assert res.status_code == 200
    data = res.json()
    assert "mapped to benchmark category 'Vegetables'" in data["confidence_note"]


def test_plan_unrecognized_category_fallback(client, valid_headers):
    """Unrecognized category falls back to Prepared Food baseline."""
    payload = {
        "org_id": 8,
        "category": "ExoticSnacks",
        "planned_quantity": 40.0,
    }
    res = client.post("/v1/plan", json=payload, headers=valid_headers)
    assert res.status_code == 200
    data = res.json()
    assert "not in benchmark taxonomy" in data["confidence_note"]
    assert "Prepared Food" in data["confidence_note"]


def test_plan_missing_models_returns_503(client, valid_headers):
    """Missing model files returns a clean 503 Service Unavailable."""
    with patch("ml_service.app.get_models", side_effect=FileNotFoundError("Mock model file not found")):
        res = client.post("/v1/plan", json={"org_id": 1, "category": "Bakery", "planned_quantity": 50}, headers=valid_headers)
        assert res.status_code == 503
        assert "Predictions temporarily unavailable" in res.json()["detail"]


def test_insights_dataset_returns_precomputed_facts(client, valid_headers):
    """GET /v1/insights/dataset returns aggregate statistics and data card."""
    res = client.get("/v1/insights/dataset", headers=valid_headers)
    assert res.status_code == 200
    data = res.json()

    assert "waste_rate_by_category" in data
    assert "Prepared Food" in data["waste_rate_by_category"]
    assert data["waste_rate_by_category"]["Prepared Food"]["waste_pct_of_remaining"] == 38.75

    assert "waste_reasons_by_category" in data
    assert "Bakery" in data["waste_reasons_by_category"]
    assert "Expired" in data["waste_reasons_by_category"]["Bakery"]

    assert "demand_lift_promotion" in data
    assert data["demand_lift_promotion"]["percentage_lift"] == 33.06

    assert "demand_lift_weather" in data
    assert "Sunny" in data["demand_lift_weather"]
    assert "Hot" in data["demand_lift_weather"]

    assert "over_purchase_share" in data
    assert data["over_purchase_share"]["share_of_orders_over_purchased_pct"] == 64.08

    assert "data_card" in data
    data_card = data["data_card"]
    assert data_card["records"] == 8000
    assert "Synthetic" in data_card["limitations"] or "synthetic" in data_card["limitations"].lower()


def test_insights_no_row_level_data(client, valid_headers):
    """Verify that insights never exposes row-level individual records."""
    res = client.get("/v1/insights/dataset", headers=valid_headers)
    assert res.status_code == 200
    data = res.json()

    # Must not contain individual rows or inventory IDs
    assert "rows" not in data
    assert "records_list" not in data
    assert "INV000001" not in str(data)
