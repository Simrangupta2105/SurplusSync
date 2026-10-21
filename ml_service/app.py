"""SurplusSync Machine Learning Service (FastAPI).

Provides endpoints for:
1. POST /v1/plan:
   - Computes demand forecast, waste risk level, over-order ratio, recommended order quantity,
     and plain-language operational explanation.
2. GET /v1/insights/dataset:
   - Returns aggregate benchmark statistics, category discard rates, demand lift multipliers,
     and dataset card documentation. Strictly returns no row-level records.

Security:
- All external API calls require the 'X-Service-Token' header matching ML_SERVICE_TOKEN.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from ml_service.scoring.reorder import compute_recommended_reorder

# Model directories and files
BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models" / "saved"
DEMAND_MODEL_PATH = MODELS_DIR / "best_demand_model.joblib"
WASTE_CLASSIFIER_PATH = MODELS_DIR / "best_waste_classifier.joblib"

DEFAULT_SERVICE_TOKEN = "surplussync-service-token-dev"

# Category baseline defaults for shelf life and storage temp
CATEGORY_DEFAULTS = {
    "Bakery": {"shelf_life": 3.0, "storage_temp": 22.0},
    "Dairy": {"shelf_life": 7.0, "storage_temp": 4.0},
    "Fruits": {"shelf_life": 5.0, "storage_temp": 5.0},
    "Meat": {"shelf_life": 4.0, "storage_temp": 2.0},
    "Prepared Food": {"shelf_life": 2.0, "storage_temp": 3.0},
    "Vegetables": {"shelf_life": 5.0, "storage_temp": 5.0},
}

CATEGORY_ALIASES = {
    "produce": "Vegetables",
    "produce & fresh greens": "Vegetables",
    "meat & poultry": "Meat",
    "prepared & cooked meals": "Prepared Food",
    "fruit": "Fruits",
    "vegetable": "Vegetables",
}

VALID_BUSINESS_TYPES = {"Restaurant", "Supermarket", "Cafeteria", "Cloud Kitchen"}
VALID_WEATHERS = {"Sunny", "Rainy", "Cloudy", "Hot", "Unknown"}


# --- Authentication Dependency ---

def verify_service_token(
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token"),
) -> str:
    """Validate X-Service-Token against the configured ML_SERVICE_TOKEN."""
    expected_token = os.getenv("ML_SERVICE_TOKEN", DEFAULT_SERVICE_TOKEN)
    if not x_service_token or x_service_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing service token.",
            headers={"WWW-Authenticate": "X-Service-Token"},
        )
    return x_service_token


# --- Pydantic Schemas ---

class PlanRequest(BaseModel):
    org_id: Union[int, str]
    category: str
    planned_quantity: float = Field(..., gt=0, description="Planned order quantity in units")
    promotion: Optional[bool] = False
    weather: Optional[str] = None
    date: Optional[str] = None
    business_type: Optional[str] = None


class ForecastRange(BaseModel):
    min: float
    max: float


class PlanResponse(BaseModel):
    forecast_demand: float
    forecast_range: ForecastRange
    over_order_ratio: float
    predicted_waste_level: str
    waste_probabilities: Dict[str, float]
    recommended_quantity: int
    explanation: str
    model_version: str
    confidence_note: str


# --- Model Loading & Caching ---

@lru_cache(maxsize=1)
def get_models() -> Tuple[Any, Any]:
    """Load and cache the trained demand and waste classifier models.

    Raises FileNotFoundError if either artifact is missing.
    """
    if not DEMAND_MODEL_PATH.is_file() or not WASTE_CLASSIFIER_PATH.is_file():
        raise FileNotFoundError(
            "Trained models not found. Please train models or ensure artifacts exist in "
            f"{MODELS_DIR}"
        )
    demand_model = joblib.load(DEMAND_MODEL_PATH)
    waste_classifier = joblib.load(WASTE_CLASSIFIER_PATH)
    return demand_model, waste_classifier


def clear_model_cache() -> None:
    """Clear cached model instances (used in testing)."""
    get_models.cache_clear()


# --- FastAPI Application ---

app = FastAPI(
    title="SurplusSync ML Service",
    description="Internal machine learning microservice for demand forecasting and waste-risk scoring.",
    version="1.0.0",
)


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """Public health probe."""
    models_ready = DEMAND_MODEL_PATH.is_file() and WASTE_CLASSIFIER_PATH.is_file()
    return {
        "status": "healthy" if models_ready else "degraded",
        "models_present": models_ready,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post(
    "/v1/plan",
    response_model=PlanResponse,
    dependencies=[Depends(verify_service_token)],
)
def plan_purchase(payload: PlanRequest) -> PlanResponse:
    """Evaluate a tentative purchasing plan and return demand forecast, waste risk, and recommendations."""
    # 1. Load models or raise 503
    try:
        demand_model, waste_classifier = get_models()
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Predictions temporarily unavailable: {err}",
        ) from err
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Predictions temporarily unavailable: Error loading ML models ({err})",
        ) from err

    confidence_notes: List[str] = []

    # 2. Parse and normalize Date
    target_date = date.today()
    if payload.date:
        try:
            target_date = datetime.strptime(payload.date.strip(), "%Y-%m-%d").date()
        except ValueError:
            confidence_notes.append(f"Invalid date '{payload.date}'; defaulted to today ({target_date})")
    day_of_week = target_date.weekday()
    month = target_date.month

    # 3. Normalize Business Type
    btype = (payload.business_type or "").strip()
    if btype not in VALID_BUSINESS_TYPES:
        if btype:
            confidence_notes.append(f"Business type '{btype}' unrecognized; defaulted to 'Restaurant'")
        else:
            confidence_notes.append("Business type not provided; defaulted to 'Restaurant'")
        btype = "Restaurant"

    # 4. Normalize Category and look up physical defaults
    raw_cat = (payload.category or "").strip()
    norm_cat = CATEGORY_ALIASES.get(raw_cat.lower(), raw_cat)
    if norm_cat not in CATEGORY_DEFAULTS:
        confidence_notes.append(
            f"Category '{raw_cat}' is not in benchmark taxonomy; evaluated using 'Prepared Food' baseline"
        )
        model_cat = "Prepared Food"
    else:
        model_cat = norm_cat
        if raw_cat.lower() in CATEGORY_ALIASES:
            confidence_notes.append(f"Category '{raw_cat}' mapped to benchmark category '{model_cat}'")

    cat_props = CATEGORY_DEFAULTS[model_cat]
    shelf_life = cat_props["shelf_life"]
    storage_temp = cat_props["storage_temp"]

    # 5. Normalize Weather
    raw_weather = (payload.weather or "").strip()
    if raw_weather not in VALID_WEATHERS:
        if raw_weather:
            confidence_notes.append(f"Weather '{raw_weather}' unrecognized; defaulted to 'Sunny'")
        else:
            confidence_notes.append("Weather condition not specified; defaulted to 'Sunny'")
        weather = "Sunny"
    else:
        weather = raw_weather

    # 6. Normalize Promotion
    promo_bool = bool(payload.promotion)
    promo_str = "Yes" if promo_bool else "No"

    # 7. Predict Demand using Tabular Demand Model
    demand_features_df = pd.DataFrame([{
        "Business_Type": btype,
        "Food_Category": model_cat,
        "Promotion": promo_str,
        "Weather": weather,
        "day_of_week": day_of_week,
        "month": month,
        "Shelf_Life_Days": shelf_life,
        "Storage_Temperature": storage_temp,
    }])

    raw_demand_pred = float(demand_model.predict(demand_features_df)[0])
    forecast_demand = max(1.0, round(raw_demand_pred, 1))

    # Calculate 90% confidence range using Poisson RMSE (approx 17.63)
    forecast_std = 17.63
    range_min = max(0.0, round(forecast_demand - 1.645 * forecast_std, 1))
    range_max = round(forecast_demand + 1.645 * forecast_std, 1)

    # 8. Compute Over-Order Ratio
    planned_qty = float(payload.planned_quantity)
    over_order_ratio = round(planned_qty / (forecast_demand + 1.0), 2)

    # 9. Predict Waste Risk Level using Waste Classifier
    waste_features_df = pd.DataFrame([{
        "Food_Category": model_cat,
        "Business_Type": btype,
        "Promotion": promo_str,
        "Weather": weather,
        "Purchase_Quantity": planned_qty,
        "forecast_demand": forecast_demand,
        "over_order_ratio": over_order_ratio,
        "Shelf_Life_Days": shelf_life,
        "Storage_Temperature": storage_temp,
        "day_of_week": day_of_week,
    }])

    probs = waste_classifier.predict_proba(waste_features_df)[0]
    classes = list(waste_classifier.classes_)
    waste_probs: Dict[str, float] = {}
    for cls_name in ["Low", "Medium", "High"]:
        if cls_name in classes:
            waste_probs[cls_name] = round(float(probs[classes.index(cls_name)]), 4)
        else:
            waste_probs[cls_name] = 0.0

    predicted_waste_level = str(waste_classifier.predict(waste_features_df)[0])

    # 10. Compute Recommended Quantity
    reorder_rec = compute_recommended_reorder(
        forecast_demand=forecast_demand,
        forecast_residual_std=forecast_std,
        shelf_life_days=shelf_life,
        service_level=0.90,
        lead_time_days=1.0,
        shelf_life_cap_ratio=0.70,
        current_on_hand=0.0,
    )
    recommended_qty = int(reorder_rec.suggested_qty)

    # 11. Synthesize Plain-Language Explanation
    pct_diff = round((planned_qty - forecast_demand) / forecast_demand * 100, 1)
    if pct_diff > 0:
        comp_str = f"{abs(pct_diff):.1f}% above forecasted customer demand"
    elif pct_diff < 0:
        comp_str = f"{abs(pct_diff):.1f}% below forecasted customer demand"
    else:
        comp_str = "matching forecasted customer demand"

    promo_text = "active promotional discount" if promo_bool else "no promotions"
    p_high_pct = round(waste_probs.get("High", 0.0) * 100, 1)

    explanation = (
        f"For {model_cat} in a {btype} under {weather} weather with {promo_text}, "
        f"expected daily demand is {forecast_demand:.1f} units (90% interval: {range_min:.1f}–{range_max:.1f}). "
        f"Your planned order of {planned_qty:.0f} units is {comp_str} "
        f"(over-order ratio: {over_order_ratio:.2f}), creating a {predicted_waste_level} waste risk "
        f"({p_high_pct}% probability of High waste). "
        f"We recommend ordering {recommended_qty} units to sustain a 90% service level without excessive spoilage."
    )

    final_note = (
        "; ".join(confidence_notes)
        if confidence_notes
        else "All operational inputs supplied; high-confidence prediction using Poisson Demand v1.0 and LightGBM Classifier v1.0."
    )

    return PlanResponse(
        forecast_demand=forecast_demand,
        forecast_range=ForecastRange(min=range_min, max=range_max),
        over_order_ratio=over_order_ratio,
        predicted_waste_level=predicted_waste_level,
        waste_probabilities=waste_probs,
        recommended_quantity=recommended_qty,
        explanation=explanation,
        model_version="1.0.0-poisson-lightgbm",
        confidence_note=final_note,
    )


@app.get(
    "/v1/insights/dataset",
    dependencies=[Depends(verify_service_token)],
)
def get_dataset_insights() -> Dict[str, Any]:
    """Return precomputed aggregate facts and documentation card from the benchmark dataset.

    Strictly guarantees that no row-level records are ever returned.
    """
    return {
        "waste_rate_by_category": {
            "Prepared Food": {"waste_pct_of_remaining": 38.75, "waste_pct_of_purchase": 7.61},
            "Bakery": {"waste_pct_of_remaining": 28.17, "waste_pct_of_purchase": 4.83},
            "Meat": {"waste_pct_of_remaining": 25.33, "waste_pct_of_purchase": 4.49},
            "Fruits": {"waste_pct_of_remaining": 23.98, "waste_pct_of_purchase": 4.21},
            "Vegetables": {"waste_pct_of_remaining": 22.23, "waste_pct_of_purchase": 3.96},
            "Dairy": {"waste_pct_of_remaining": 21.14, "waste_pct_of_purchase": 3.82},
        },
        "waste_reasons_by_category": {
            "Prepared Food": {"Expired": 40.57, "No Waste": 38.07, "Overproduction": 10.82, "Storage Issue": 5.34, "Low Demand": 5.21},
            "Bakery": {"No Waste": 41.62, "Expired": 19.97, "Overproduction": 18.52, "Low Demand": 14.11, "Storage Issue": 5.77},
            "Meat": {"No Waste": 44.25, "Overproduction": 20.21, "Low Demand": 16.93, "Expired": 16.85, "Storage Issue": 1.76},
            "Fruits": {"No Waste": 43.47, "Overproduction": 21.94, "Low Demand": 20.48, "Expired": 10.06, "Storage Issue": 4.05},
            "Vegetables": {"No Waste": 44.30, "Overproduction": 21.83, "Low Demand": 20.64, "Expired": 8.12, "Storage Issue": 5.11},
            "Dairy": {"No Waste": 45.09, "Overproduction": 24.10, "Low Demand": 20.83, "Expired": 7.83, "Storage Issue": 2.15},
        },
        "demand_lift_promotion": {
            "percentage_lift": 33.06,
            "mean_demand_with_promo": 131.42,
            "mean_demand_without_promo": 98.77,
        },
        "demand_lift_weather": {
            "Sunny": {"multiplier": 1.0000, "relative_effect": "Baseline", "mean_demand": 114.83},
            "Hot": {"multiplier": 1.0385, "relative_effect": "+3.85%", "mean_demand": 119.25},
            "Cloudy": {"multiplier": 0.8921, "relative_effect": "-10.79%", "mean_demand": 102.44},
            "Rainy": {"multiplier": 0.6683, "relative_effect": "-33.17%", "mean_demand": 76.74},
        },
        "over_purchase_share": {
            "share_of_orders_over_purchased_pct": 64.08,
            "total_purchased_units": 946310,
            "total_sold_units": 775677,
            "total_excess_units": 170633,
        },
        "data_card": {
            "title": "Benchmark Commercial Food Waste Dataset",
            "records": 8000,
            "period": "2025-01-01 to 2025-12-31",
            "scope": "8,000 daily observations across 4 business segments (Restaurant, Supermarket, Cafeteria, Cloud Kitchen) and 6 food categories (Bakery, Dairy, Fruits, Meat, Prepared Food, Vegetables).",
            "provenance_placeholder": "Synthetically calibrated microdata benchmark simulating commercial food service and retail inventory operations.",
            "limitations": "Synthetic benchmark characteristics with deterministic sales-accounting constraints; population-level ratio binning creates minor label noise; single-day snapshots without persistent store IDs. This data serves as an empirical cross-sectional benchmark and does not represent live individual tenant operations.",
            "accounting_invariants": "All 5 accounting invariants verified with 0 discrepancies across 8,000 records.",
        },
    }
