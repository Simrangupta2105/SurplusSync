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

import json
import os
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

import sys
from pathlib import Path

# Ensure both workspace root and ml_service folder are on python path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BASE_DIR.parent))

try:
    from ml_service.models.registry import ModelRegistry
    from ml_service.scoring.reorder import compute_recommended_reorder
except ModuleNotFoundError:
    from models.registry import ModelRegistry
    from scoring.reorder import compute_recommended_reorder
MODELS_DIR = BASE_DIR / "models" / "saved"
DEMAND_MODEL_PATH = MODELS_DIR / "best_synthetic_demand_model.joblib"
WASTE_CLASSIFIER_PATH = MODELS_DIR / "best_synthetic_waste_classifier.joblib"

DEFAULT_SERVICE_TOKEN = "surplussync-service-token-dev"

# Category baseline defaults for shelf life, storage temp, cost and price
CATEGORY_DEFAULTS = {
    "Bakery": {"shelf_life": 3.0, "storage_temp": 22.0, "unit_cost": 40.0, "unit_price": 60.0},
    "Dairy": {"shelf_life": 7.0, "storage_temp": 4.0, "unit_cost": 35.0, "unit_price": 50.0},
    "Fruits": {"shelf_life": 5.0, "storage_temp": 5.0, "unit_cost": 45.0, "unit_price": 70.0},
    "Meat": {"shelf_life": 4.0, "storage_temp": 2.0, "unit_cost": 150.0, "unit_price": 220.0},
    "Prepared Food": {"shelf_life": 2.0, "storage_temp": 3.0, "unit_cost": 80.0, "unit_price": 130.0},
    "Vegetables": {"shelf_life": 5.0, "storage_temp": 5.0, "unit_cost": 25.0, "unit_price": 40.0},
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


class ForecastRange(BaseModel):
    min: float
    max: float


class PlanRequest(BaseModel):
    org_id: Union[int, str]
    category: str
    planned_quantity: float = Field(..., gt=0, description="Planned order quantity in units")
    promotion: Optional[bool] = False
    weather: Optional[str] = None
    date: Optional[str] = None
    business_type: Optional[str] = None


class PlanResponse(BaseModel):
    forecast_demand: float
    forecast_range: ForecastRange
    over_order_ratio: float
    predicted_waste_level: str
    waste_probabilities: Dict[str, float]
    recommended_quantity: int
    explanation: str
    model_name: str
    model_version: str
    confidence_note: str
    data_origin: str = "synthetic"
    training_data_note: Optional[str] = None
    generated_at: str


class StepPrediction(BaseModel):
    step: int
    date: Optional[str] = None
    forecast_demand: float
    forecast_range: ForecastRange
    confidence_std: float


class DemandPredictionRequest(BaseModel):
    category: str
    shop_id: Optional[str] = "SHOP_01"
    city: Optional[str] = "Bhopal"
    business_type: Optional[str] = "Restaurant"
    date: Optional[str] = None
    horizon: Optional[int] = Field(1, ge=1, le=14, description="Forecast horizon in days (1 to 14)")
    promotion: Optional[bool] = False
    weather: Optional[str] = "Sunny"
    temperature_c: Optional[float] = 25.0
    rain_mm: Optional[float] = 0.0
    is_holiday: Optional[bool] = False
    history: Optional[List[float]] = None
    historical_sales: Optional[List[float]] = None


class DemandPredictionResponse(BaseModel):
    category: str
    shop_id: Optional[str] = None
    forecast_demand: float
    forecast_range: ForecastRange
    horizon: int
    horizon_days: int
    predictions: List[StepPrediction]
    model_name: str
    model_version: str
    data_origin: str
    notes: List[str]
    generated_at: str


class InventoryPlanRequest(BaseModel):
    category: str
    shop_id: Optional[str] = "SHOP_01"
    city: Optional[str] = "Bhopal"
    business_type: Optional[str] = "Restaurant"
    date: Optional[str] = None
    current_stock: float = Field(0.0, ge=0.0, description="Sellable on-hand inventory")
    sellable_on_hand: Optional[float] = None
    on_order: Optional[float] = 0.0
    planned_quantity: Optional[float] = Field(None, gt=0, description="Operator planned order quantity")
    service_level: float = Field(0.90, ge=0.50, le=0.99, description="Target cycle service level")
    lead_time_days: float = Field(1.0, gt=0, description="Replenishment lead time in days")
    shelf_life_days: Optional[float] = None
    shelf_life_cap_ratio: float = 0.70
    pack_size: Optional[int] = None
    storage_capacity_available: Optional[float] = None
    promotion: Optional[bool] = False
    weather: Optional[str] = "Sunny"
    temperature_c: Optional[float] = 25.0
    rain_mm: Optional[float] = 0.0
    is_holiday: Optional[bool] = False
    history: Optional[List[float]] = None
    historical_sales: Optional[List[float]] = None


class InventoryPlanResponse(BaseModel):
    category: str
    forecast_demand: float
    forecast_range: ForecastRange
    recommended_quantity: int
    recommended_order_quantity: int
    safety_stock: float
    shelf_life_cap: float
    shelf_cap_applied: bool
    storage_cap_applied: bool
    service_level: float
    over_order_ratio: Optional[float] = None
    predicted_waste_risk: str
    waste_risk: str
    waste_probabilities: Dict[str, float]
    operational_explanation: str
    explanation: str
    model_name: str
    model_version: str
    data_origin: str
    generated_at: str


# --- Model Loading & Caching ---

def get_models() -> Tuple[Any, Any]:
    """Retrieve active demand model and waste classifier from ModelRegistry."""
    demand_model, _ = ModelRegistry.get_demand_model()
    waste_classifier, _ = ModelRegistry.get_waste_classifier()
    return demand_model, waste_classifier


def clear_model_cache() -> None:
    """Clear cached model instances (used in testing)."""
    ModelRegistry.clear_cache()


# --- FastAPI Application ---

app = FastAPI(
    title="SurplusSync ML Service",
    description="Internal machine learning microservice for demand forecasting and waste-risk scoring.",
    version="1.0.0",
)


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """Public health probe."""
    try:
        ModelRegistry.get_demand_model()
        ModelRegistry.get_waste_classifier()
        models_ready = True
    except Exception:
        models_ready = False
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

    # 7. Predict Demand using Selected Model from ModelRegistry
    forecast_demand, range_min, range_max, demand_meta = ModelRegistry.predict_demand(
        category=model_cat,
        features={
            "business_type": btype,
            "promotion": promo_bool,
            "weather": weather,
            "day_of_week": day_of_week,
            "month": month,
            "shelf_life": shelf_life,
            "storage_temp": storage_temp,
        },
    )

    # 8. Compute Over-Order Ratio
    planned_qty = float(payload.planned_quantity)
    over_order_ratio = round(planned_qty / (forecast_demand + 1.0), 2)

    # 9. Predict Waste Risk Level using Waste Classifier
    waste_classifier, waste_meta = ModelRegistry.get_waste_classifier()
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
        "Day_Of_Week": day_of_week,
        "Temperature_C": 25.0,
        "Is_Holiday": 0,
        "Lead_Time_Days": 1.0,
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
    forecast_std = (range_max - forecast_demand) / 1.645 if range_max > forecast_demand else 17.63
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
        f"expected daily demand is {forecast_demand:.1f} units (90% interval: {range_min:.1f} to {range_max:.1f}). "
        f"Your planned order of {planned_qty:.0f} units is {comp_str} "
        f"(over-order ratio: {over_order_ratio:.2f}), creating a {predicted_waste_level} waste risk "
        f"({p_high_pct}% probability of High waste). "
        f"We recommend ordering {recommended_qty} units to sustain a 90% service level without excessive spoilage."
    )

    if demand_meta.get("is_fallback"):
        confidence_notes.append("Serving fallback demand model due to missing primary artifact.")

    final_note = (
        "; ".join(confidence_notes)
        if confidence_notes
        else f"All operational inputs supplied; high-confidence prediction using {demand_meta.get('model_name', 'HistGradientBoostingDemandModel')}."
    )

    data_origin = str(demand_meta.get("data_origin", "synthetic"))
    model_name = str(demand_meta.get("model_name", "HistGradientBoostingDemandModel"))
    model_version = str(demand_meta.get("version", "1.0.0-synthetic-track-b"))
    generated_at = datetime.now(timezone.utc).isoformat()
    training_note = (
        "Trained on synthetic demonstration data"
        if data_origin.lower().startswith("synthetic")
        else None
    )

    return PlanResponse(
        forecast_demand=forecast_demand,
        forecast_range=ForecastRange(min=range_min, max=range_max),
        over_order_ratio=over_order_ratio,
        predicted_waste_level=predicted_waste_level,
        waste_probabilities=waste_probs,
        recommended_quantity=recommended_qty,
        explanation=explanation,
        model_name=model_name,
        model_version=model_version,
        confidence_note=final_note,
        data_origin=data_origin,
        training_data_note=training_note,
        generated_at=generated_at,
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


@app.post(
    "/predict/demand",
    response_model=DemandPredictionResponse,
    dependencies=[Depends(verify_service_token)],
)
def predict_demand_endpoint(payload: DemandPredictionRequest) -> DemandPredictionResponse:
    """Predict point customer demand and 90% confidence interval for specified horizons (1-7 days)."""
    notes: List[str] = []

    # 1. Parse date
    target_date = date.today()
    if payload.date:
        try:
            target_date = datetime.strptime(payload.date.strip(), "%Y-%m-%d").date()
        except ValueError:
            notes.append(f"Invalid date '{payload.date}'; defaulted to today ({target_date})")

    # 2. Normalize category
    raw_cat = (payload.category or "").strip()
    norm_cat = CATEGORY_ALIASES.get(raw_cat.lower(), raw_cat)
    if norm_cat not in CATEGORY_DEFAULTS:
        notes.append(f"Category '{raw_cat}' unrecognized; defaulted to 'Prepared Food'")
        model_cat = "Prepared Food"
    else:
        model_cat = norm_cat
        if raw_cat.lower() in CATEGORY_ALIASES:
            notes.append(f"Category '{raw_cat}' mapped to benchmark category '{model_cat}'")

    # 3. Normalize business type
    btype = (payload.business_type or "Restaurant").strip()
    if btype not in VALID_BUSINESS_TYPES:
        notes.append(f"Business type '{btype}' unrecognized; defaulted to 'Restaurant'")
        btype = "Restaurant"

    # 4. Normalize weather
    weather = (payload.weather or "Sunny").strip()
    if weather not in VALID_WEATHERS:
        notes.append(f"Weather '{weather}' unrecognized; defaulted to 'Sunny'")
        weather = "Sunny"

    cat_props = CATEGORY_DEFAULTS[model_cat]
    horizon = int(payload.horizon or 1)
    hist = payload.historical_sales if payload.historical_sales is not None else payload.history
    curr_history = list(hist) if hist else []
    curr_date = target_date

    # 5. Predict demand (recursive rollout across horizon steps)
    predictions: List[StepPrediction] = []
    meta: Dict[str, Any] = {}
    for h_step in range(1, horizon + 1):
        step_demand, step_min, step_max, step_meta = ModelRegistry.predict_demand(
            category=model_cat,
            features={
                "business_type": btype,
                "promotion": bool(payload.promotion) if h_step == 1 else False,
                "weather": weather,
                "temperature_c": float(payload.temperature_c if payload.temperature_c is not None else 25.0),
                "rain_mm": float(payload.rain_mm if payload.rain_mm is not None else 0.0),
                "is_holiday": bool(payload.is_holiday) if h_step == 1 else False,
                "day_of_week": curr_date.weekday(),
                "month": curr_date.month,
                "day_of_year": curr_date.timetuple().tm_yday,
                "shelf_life": cat_props["shelf_life"],
                "storage_temp": cat_props["storage_temp"],
                "unit_cost": cat_props["unit_cost"],
                "unit_price": cat_props["unit_price"],
            },
            history=curr_history,
            horizon=h_step,
            shop_id=payload.shop_id or "SHOP_01",
            city=payload.city or "Bhopal",
        )
        meta = step_meta
        conf_std = round((step_max - step_demand) / 1.645, 2) if step_max > step_demand else 17.63
        predictions.append(StepPrediction(
            step=h_step,
            date=curr_date.isoformat(),
            forecast_demand=step_demand,
            forecast_range=ForecastRange(min=step_min, max=step_max),
            confidence_std=conf_std,
        ))
        curr_history.append(step_demand)
        curr_date += timedelta(days=1)

    p1 = predictions[0]
    return DemandPredictionResponse(
        category=model_cat,
        shop_id=payload.shop_id or "SHOP_01",
        forecast_demand=p1.forecast_demand,
        forecast_range=p1.forecast_range,
        horizon=horizon,
        horizon_days=horizon,
        predictions=predictions,
        model_name=str(meta.get("model_name", "HistGradientBoosting_History")),
        model_version=str(meta.get("version", "2.0.0-synthetic-sequence")),
        data_origin=str(meta.get("data_origin", "synthetic_seq_v2")),
        notes=notes,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@app.post(
    "/predict/inventory-plan",
    response_model=InventoryPlanResponse,
    dependencies=[Depends(verify_service_token)],
)
def predict_inventory_plan_endpoint(payload: InventoryPlanRequest) -> InventoryPlanResponse:
    """Compute optimal inventory purchase order recommendation with safety stock and shelf-life cap."""
    # 1. Parse date
    target_date = date.today()
    if payload.date:
        try:
            target_date = datetime.strptime(payload.date.strip(), "%Y-%m-%d").date()
        except ValueError:
            pass

    # 2. Normalize category
    raw_cat = (payload.category or "").strip()
    norm_cat = CATEGORY_ALIASES.get(raw_cat.lower(), raw_cat)
    model_cat = norm_cat if norm_cat in CATEGORY_DEFAULTS else "Prepared Food"
    cat_props = CATEGORY_DEFAULTS[model_cat]

    # 3. Normalize business type & weather
    btype = payload.business_type if payload.business_type in VALID_BUSINESS_TYPES else "Restaurant"
    weather = payload.weather if payload.weather in VALID_WEATHERS else "Sunny"

    shelf_life = float(payload.shelf_life_days if payload.shelf_life_days is not None else cat_props["shelf_life"])
    storage_temp = cat_props["storage_temp"]
    promo_bool = bool(payload.promotion)
    promo_str = "Yes" if promo_bool else "No"

    hist = payload.historical_sales if payload.historical_sales is not None else payload.history
    current_inv = float(payload.sellable_on_hand if payload.sellable_on_hand is not None else payload.current_stock)
    on_ord = float(payload.on_order or 0.0)

    # 4. Predict demand
    forecast_demand, range_min, range_max, meta = ModelRegistry.predict_demand(
        category=model_cat,
        features={
            "business_type": btype,
            "promotion": promo_bool,
            "weather": weather,
            "temperature_c": float(payload.temperature_c if payload.temperature_c is not None else 25.0),
            "rain_mm": float(payload.rain_mm if payload.rain_mm is not None else 0.0),
            "is_holiday": bool(payload.is_holiday),
            "day_of_week": target_date.weekday(),
            "month": target_date.month,
            "day_of_year": target_date.timetuple().tm_yday,
            "shelf_life": shelf_life,
            "storage_temp": storage_temp,
            "unit_cost": cat_props["unit_cost"],
            "unit_price": cat_props["unit_price"],
        },
        history=hist,
        horizon=1,
        shop_id=payload.shop_id or "SHOP_01",
        city=payload.city or "Bhopal",
    )

    # 5. Compute recommended reorder quantity
    forecast_std = (range_max - forecast_demand) / 1.645 if range_max > forecast_demand else 17.63
    reorder_rec = compute_recommended_reorder(
        forecast_demand=forecast_demand,
        forecast_residual_std=forecast_std,
        shelf_life_days=shelf_life,
        service_level=payload.service_level,
        lead_time_days=payload.lead_time_days,
        shelf_life_cap_ratio=payload.shelf_life_cap_ratio,
        current_on_hand=current_inv,
        on_order=on_ord,
        storage_capacity_available=payload.storage_capacity_available,
        pack_size=payload.pack_size,
        product_name=model_cat,
    )
    recommended_qty = int(reorder_rec.suggested_qty)

    # 6. Evaluate Waste Risk
    eval_qty = float(payload.planned_quantity if payload.planned_quantity is not None else recommended_qty)
    over_order_ratio = round(eval_qty / (forecast_demand + 1.0), 2)

    waste_classifier, _ = ModelRegistry.get_waste_classifier()
    waste_features_df = pd.DataFrame([{
        "Food_Category": model_cat,
        "Business_Type": btype,
        "Promotion": promo_str,
        "Weather": weather,
        "Purchase_Quantity": eval_qty,
        "forecast_demand": forecast_demand,
        "over_order_ratio": over_order_ratio,
        "Shelf_Life_Days": shelf_life,
        "Storage_Temperature": storage_temp,
        "day_of_week": target_date.weekday(),
        "Day_Of_Week": target_date.weekday(),
        "Temperature_C": float(payload.temperature_c if payload.temperature_c is not None else 25.0),
        "Is_Holiday": 1 if payload.is_holiday else 0,
        "Lead_Time_Days": float(payload.lead_time_days),
    }])

    probs = waste_classifier.predict_proba(waste_features_df)[0]
    classes = list(waste_classifier.classes_)
    waste_probs: Dict[str, float] = {}
    for cls_name in ["Low", "Medium", "High"]:
        waste_probs[cls_name] = round(float(probs[classes.index(cls_name)]), 4) if cls_name in classes else 0.0
    predicted_waste_level = str(waste_classifier.predict(waste_features_df)[0])

    # 7. Operational explanation
    if payload.planned_quantity is not None:
        pct_diff = round((eval_qty - forecast_demand) / forecast_demand * 100, 1)
        comp_str = f"{abs(pct_diff):.1f}% above forecast" if pct_diff > 0 else f"{abs(pct_diff):.1f}% below forecast"
        op_explanation = (
            f"Planned order of {eval_qty:.0f} units is {comp_str} (over-order ratio: {over_order_ratio:.2f}). "
            f"Waste risk is classified as {predicted_waste_level} ({waste_probs.get('High', 0.0)*100:.1f}% High risk). "
            f"Recommended order is {recommended_qty} units (safety stock: {reorder_rec.safety_stock:.1f}, "
            f"shelf-life cap: {reorder_rec.shelf_life_cap:.1f})."
        )
    else:
        op_explanation = (
            f"Recommended order is {recommended_qty} units (safety stock: {reorder_rec.safety_stock:.1f}, "
            f"service level: {payload.service_level*100:.0f}%, shelf-life cap: {reorder_rec.shelf_life_cap:.1f}). "
            f"Expected waste risk: {predicted_waste_level}."
        )

    return InventoryPlanResponse(
        category=model_cat,
        forecast_demand=forecast_demand,
        forecast_range=ForecastRange(min=range_min, max=range_max),
        recommended_quantity=recommended_qty,
        recommended_order_quantity=recommended_qty,
        safety_stock=round(reorder_rec.safety_stock, 1),
        shelf_life_cap=round(reorder_rec.shelf_life_cap, 1),
        shelf_cap_applied=reorder_rec.shelf_cap_applied,
        storage_cap_applied=reorder_rec.storage_cap_applied,
        service_level=payload.service_level,
        over_order_ratio=over_order_ratio if payload.planned_quantity is not None else None,
        predicted_waste_risk=predicted_waste_level,
        waste_risk=predicted_waste_level,
        waste_probabilities=waste_probs,
        operational_explanation=op_explanation,
        explanation=op_explanation,
        model_name=str(meta.get("model_name", "HistGradientBoosting_History")),
        model_version=str(meta.get("version", "2.0.0-synthetic-sequence")),
        data_origin=str(meta.get("data_origin", "synthetic_seq_v2")),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@app.get(
    "/registry/status",
    dependencies=[Depends(verify_service_token)],
)
def get_registry_status() -> Dict[str, Any]:
    """Return live status, active artifacts, versions, and category mappings from ModelRegistry."""
    return ModelRegistry.get_registry_status()

