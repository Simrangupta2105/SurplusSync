"""Unit tests for ModelRegistry and Task 1 Serving (Time-Series Track B).

Verifies:
1. The registry returns the selected model per category (HistGradientBoostingDemandModel for all 6 categories).
2. The registry loads the active demand model and metadata.
3. Fallback works gracefully when the primary synthetic artifact is missing.
4. An error is raised when all artifacts are missing.
5. The /v1/plan endpoint response carries all required metadata:
   - model_name
   - model_version
   - data_origin
   - generated_at
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ml_service.app import DEFAULT_SERVICE_TOKEN, app
from ml_service.models.registry import (
    SAVED_MODELS_DIR,
    SUPPORTED_CATEGORIES,
    ModelRegistry,
)


@pytest.fixture(autouse=True)
def reset_registry():
    """Clear registry cache before and after every test."""
    ModelRegistry.clear_cache()
    yield
    ModelRegistry.clear_cache()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def valid_headers():
    token = os.getenv("ML_SERVICE_TOKEN", DEFAULT_SERVICE_TOKEN)
    return {"X-Service-Token": token}


def test_registry_returns_selected_model_per_category():
    """Verify that the registry specifies winning model for all categories."""
    for category in SUPPORTED_CATEGORIES:
        model_name = ModelRegistry.get_selected_model_name_for_category(category)
        assert model_name in {"HistGradientBoosting_History", "HistGradientBoostingDemandModel"}, (
            f"Expected winning model for category {category}, got {model_name}"
        )


def test_registry_loads_demand_model_and_metadata():
    """Verify primary demand model and metadata load cleanly from saved models dir."""
    model, metadata = ModelRegistry.get_demand_model()
    assert model is not None
    assert metadata is not None
    assert "data_origin" in metadata
    assert metadata["data_origin"].startswith("synthetic")
    assert metadata.get("is_fallback") is False


def test_registry_predict_demand_produces_valid_intervals():
    """Verify predict_demand generates positive demand and ordered 90% intervals."""
    features = {
        "business_type": "Restaurant",
        "promotion": True,
        "weather": "Sunny",
        "day_of_week": 4,
        "month": 11,
    }
    demand, low, high, meta = ModelRegistry.predict_demand("Bakery", features)

    assert isinstance(demand, float)
    assert demand > 0
    assert 0.0 <= low <= demand <= high
    assert "model_name" in meta
    assert "data_origin" in meta


def test_registry_fallback_when_primary_missing():
    """Verify graceful fallback to Track A model when primary synthetic artifact is missing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Copy only the fallback model and its metadata
        fallback_src = SAVED_MODELS_DIR / "best_demand_model.joblib"
        fallback_meta_src = SAVED_MODELS_DIR / "best_demand_model_metadata.json"

        if fallback_src.is_file():
            shutil.copy(fallback_src, tmp_path / "best_demand_model.joblib")
        if fallback_meta_src.is_file():
            shutil.copy(fallback_meta_src, tmp_path / "best_demand_model_metadata.json")

        model, meta = ModelRegistry.get_demand_model(registry_dir=tmp_path)
        assert model is not None
        assert meta["is_fallback"] is True
        assert meta["model_name"] == "Poisson_Regression"

        # Verify predictions still function seamlessly under fallback
        features = {
            "business_type": "Supermarket",
            "promotion": False,
            "weather": "Rainy",
            "day_of_week": 1,
            "month": 5,
        }
        demand, low, high, ret_meta = ModelRegistry.predict_demand("Dairy", features, registry_dir=tmp_path)
        assert demand > 0
        assert 0.0 <= low <= demand <= high


def test_registry_raises_when_all_artifacts_missing():
    """Verify clean FileNotFoundError when registry dir contains no model artifacts."""
    with tempfile.TemporaryDirectory() as empty_dir:
        with pytest.raises(FileNotFoundError, match="No demand model artifacts found"):
            ModelRegistry.get_demand_model(registry_dir=empty_dir)


def test_plan_endpoint_response_carries_metadata(client, valid_headers):
    """Verify /v1/plan response includes model_name, model_version, data_origin, and generated_at."""
    payload = {
        "org_id": 1,
        "category": "Prepared Food",
        "planned_quantity": 120.0,
        "promotion": True,
        "weather": "Sunny",
        "business_type": "Restaurant",
    }
    res = client.post("/v1/plan", json=payload, headers=valid_headers)
    assert res.status_code == 200
    data = res.json()

    # Required Task 1 response fields
    assert "model_name" in data
    assert data["model_name"] in {"HistGradientBoosting_History", "HistGradientBoostingDemandModel", "Poisson_Regression"}

    assert "model_version" in data
    assert len(data["model_version"]) > 0

    assert "data_origin" in data
    assert data["data_origin"].startswith("synthetic")

    assert "training_data_note" in data
    assert data["training_data_note"] == "Trained on synthetic demonstration data"

    assert "generated_at" in data
    assert "T" in data["generated_at"]  # ISO-8601 timestamp string format
