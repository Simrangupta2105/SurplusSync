"""SurplusSync Machine Learning Model Registry.

Provides unified discovery, loading, caching, and graceful fallback for:
1. Demand Forecasting Models (Primary: Winning HistGradientBoosting sequence model; Fallback: Tabular Poisson).
2. Waste Risk Classifiers (Primary: HistGradientBoosting; Fallback: LightGBM).

Enforces:
- Selection of the winning model per category based on empirical cross-validation.
- Graceful fallback when a primary model artifact is missing or unreadable.
- Dynamic metadata retrieval (model_name, model_version, data_origin).
- Benchmark-only isolation for non-serving candidate models (Prophet, PyTorch LSTM).
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Base directories
MODELS_DIR = Path(__file__).resolve().parent
SAVED_MODELS_DIR = MODELS_DIR / "saved"

# Ensure 'models' is mapped in sys.modules to guarantee smooth unpickling
try:
    import ml_service.models as _models_pkg
    sys.modules.setdefault("models", _models_pkg)
except Exception:
    pass

SUPPORTED_CATEGORIES: List[str] = [
    "Bakery",
    "Dairy",
    "Fruits",
    "Meat",
    "Prepared Food",
    "Vegetables",
]

# Mapping of empirically chosen winning model per food category (from Track B 4-fold CV & 90-day test)
WINNING_MODEL_BY_CATEGORY: Dict[str, str] = {
    "Bakery": "HistGradientBoosting_History",
    "Dairy": "HistGradientBoosting_History",
    "Fruits": "HistGradientBoosting_History",
    "Meat": "HistGradientBoosting_History",
    "Prepared Food": "HistGradientBoosting_History",
    "Vegetables": "HistGradientBoosting_History",
}

# Physical category property baselines
CATEGORY_DEFAULTS: Dict[str, Dict[str, float]] = {
    "Bakery": {"shelf_life": 3.0, "storage_temp": 22.0, "unit_cost": 40.0, "unit_price": 60.0},
    "Dairy": {"shelf_life": 7.0, "storage_temp": 4.0, "unit_cost": 35.0, "unit_price": 50.0},
    "Fruits": {"shelf_life": 5.0, "storage_temp": 5.0, "unit_cost": 45.0, "unit_price": 70.0},
    "Meat": {"shelf_life": 4.0, "storage_temp": 2.0, "unit_cost": 150.0, "unit_price": 220.0},
    "Prepared Food": {"shelf_life": 2.0, "storage_temp": 3.0, "unit_cost": 80.0, "unit_price": 130.0},
    "Vegetables": {"shelf_life": 5.0, "storage_temp": 5.0, "unit_cost": 25.0, "unit_price": 40.0},
}

# Encoding maps matching TabularFeatureEngine
SHOP_CODE_MAP: Dict[str, int] = {f"SHOP_{i:02d}": i - 1 for i in range(1, 13)}
CAT_CODE_MAP: Dict[str, int] = {
    "Bakery": 0,
    "Dairy": 1,
    "Fruits": 2,
    "Meat": 3,
    "Prepared Food": 4,
    "Vegetables": 5,
}
CITY_CODE_MAP: Dict[str, int] = {"Bhopal": 0, "Indore": 1, "Mumbai": 2}
BTYPE_CODE_MAP: Dict[str, int] = {
    "Cafeteria": 0,
    "Cloud Kitchen": 1,
    "Restaurant": 2,
    "Supermarket": 3,
}
WEATHER_CODE_MAP: Dict[str, int] = {"Sunny": 0, "Cloudy": 1, "Rainy": 2, "Hot": 3, "Unknown": 0}


class ModelRegistry:
    """Central registry and model manager for SurplusSync ML inference."""

    _demand_cache: Dict[str, Tuple[Any, Dict[str, Any]]] = {}
    _classifier_cache: Dict[str, Tuple[Any, Dict[str, Any]]] = {}

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached models in memory (used for tests and hot-reloading)."""
        cls._demand_cache.clear()
        cls._classifier_cache.clear()

    @classmethod
    def get_selected_model_name_for_category(cls, category: str) -> str:
        """Return the empirically selected winning model name for a category."""
        norm_cat = category.strip()
        return WINNING_MODEL_BY_CATEGORY.get(norm_cat, "HistGradientBoosting_History")

    @classmethod
    def get_demand_model(
        cls,
        category: Optional[str] = None,
        registry_dir: Optional[Union[Path, str]] = None,
    ) -> Tuple[Any, Dict[str, Any]]:
        """Retrieve the active demand model with graceful fallback.

        Resolution order:
        1. Sequence model: best_synthetic_sequence_demand_model.joblib (Track B winner)
        2. Primary synthetic: best_synthetic_demand_model.joblib
        3. Fallback baseline: best_demand_model.joblib (Poisson regression)
        """
        r_dir = Path(registry_dir) if registry_dir else SAVED_MODELS_DIR
        cache_key = f"{r_dir}_{category or 'default'}"

        if cache_key in cls._demand_cache:
            return cls._demand_cache[cache_key]

        candidates = [
            (
                r_dir / "best_synthetic_sequence_demand_model.joblib",
                r_dir / "best_synthetic_sequence_demand_model_metadata.json",
                False,
            ),
            (
                r_dir / "best_synthetic_demand_model.joblib",
                r_dir / "best_synthetic_demand_model_metadata.json",
                False,
            ),
            (
                r_dir / "best_demand_model.joblib",
                r_dir / "best_demand_model_metadata.json",
                True,
            ),
        ]

        sys.path.insert(0, str(MODELS_DIR.parent))

        for model_path, meta_path, is_fb in candidates:
            if model_path.is_file():
                try:
                    model = joblib.load(model_path)
                    meta: Dict[str, Any] = {}
                    if meta_path.is_file():
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                    else:
                        meta = {
                            "model_name": "HistGradientBoosting_History" if not is_fb else "Poisson_Regression",
                            "data_origin": "synthetic_seq_v2" if not is_fb else "synthetic",
                            "version": "2.0.0-synthetic-sequence" if not is_fb else "1.0.0-poisson-fallback",
                        }
                    meta["is_fallback"] = is_fb
                    cls._demand_cache[cache_key] = (model, meta)
                    return model, meta
                except Exception as exc:
                    logger.warning("Failed to load model from %s (%s). Attempting fallback.", model_path, exc)

        raise FileNotFoundError(
            f"No demand model artifacts found in {r_dir}. Ensure best_synthetic_demand_model.joblib "
            f"or best_demand_model.joblib exists."
        )

    @classmethod
    def get_waste_classifier(
        cls,
        registry_dir: Optional[Union[Path, str]] = None,
    ) -> Tuple[Any, Dict[str, Any]]:
        """Retrieve the primary waste classifier with fallback."""
        r_dir = Path(registry_dir) if registry_dir else SAVED_MODELS_DIR
        cache_key = str(r_dir)

        if cache_key in cls._classifier_cache:
            return cls._classifier_cache[cache_key]

        primary_path = r_dir / "best_synthetic_waste_classifier.joblib"
        primary_meta = r_dir / "best_synthetic_waste_classifier_metadata.json"
        fallback_path = r_dir / "best_waste_classifier.joblib"
        fallback_meta = r_dir / "best_waste_classifier_metadata.json"

        # 1. Primary
        if primary_path.is_file():
            try:
                sys.path.insert(0, str(MODELS_DIR.parent))
                classifier = joblib.load(primary_path)
                meta: Dict[str, Any] = {}
                if primary_meta.is_file():
                    with open(primary_meta, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                else:
                    meta = {
                        "model_name": "HistGradientBoostingClassifier",
                        "data_origin": "synthetic",
                        "version": "1.0.0-synthetic-track-b",
                    }
                meta["is_fallback"] = False
                cls._classifier_cache[cache_key] = (classifier, meta)
                return classifier, meta
            except Exception as exc:
                logger.warning("Failed to load primary waste classifier from %s (%s). Falling back.", primary_path, exc)

        # 2. Fallback
        if fallback_path.is_file():
            try:
                classifier = joblib.load(fallback_path)
                meta = {}
                if fallback_meta.is_file():
                    with open(fallback_meta, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                else:
                    meta = {
                        "model_name": "LightGBMClassifier",
                        "data_origin": "synthetic",
                        "version": "1.0.0-lightgbm-fallback",
                    }
                meta["is_fallback"] = True
                cls._classifier_cache[cache_key] = (classifier, meta)
                return classifier, meta
            except Exception as exc:
                logger.error("Failed to load fallback classifier from %s: %s", fallback_path, exc)

        raise FileNotFoundError(
            f"No waste classifier artifacts found in {r_dir}. Ensure best_synthetic_waste_classifier.joblib exists."
        )

    @classmethod
    def predict_demand(
        cls,
        category: str,
        features: Dict[str, Any],
        history: Optional[List[float]] = None,
        horizon: int = 1,
        shop_id: Optional[str] = None,
        city: Optional[str] = None,
        registry_dir: Optional[Union[Path, str]] = None,
    ) -> Tuple[float, float, float, Dict[str, Any]]:
        """Predict daily demand and 90% confidence range with support for sequence history.

        Args:
            category: Food category name (e.g. 'Bakery').
            features: Operational covariates (business_type, promotion, weather, date, etc.).
            history: Optional list of recent historical daily demand figures.
            horizon: Forecast step h (1 to 7 days, default 1).
            shop_id: Optional shop identifier (e.g. 'SHOP_01').
            city: Optional city name (e.g. 'Bhopal').
            registry_dir: Optional directory override.

        Returns:
            Tuple of (forecast_demand, range_min, range_max, model_metadata)
        """
        model, meta = cls.get_demand_model(category=category, registry_dir=registry_dir)
        cat_props = CATEGORY_DEFAULTS.get(category, CATEGORY_DEFAULTS["Prepared Food"])

        btype = features.get("business_type", "Restaurant")
        promo_bool = bool(features.get("promotion", False))
        weather = features.get("weather", "Sunny")
        day_of_week = int(features.get("day_of_week", 2))
        month = int(features.get("month", 10))
        day_of_year = int(features.get("day_of_year", 280))
        shelf_life = float(features.get("shelf_life", cat_props["shelf_life"]))
        storage_temp = float(features.get("storage_temp", cat_props["storage_temp"]))
        unit_cost = float(features.get("unit_cost", cat_props["unit_cost"]))
        unit_price = float(features.get("unit_price", cat_props["unit_price"]))
        rain_mm = float(features.get("rain_mm", 0.0))
        temp_c = float(features.get("temperature_c", 25.0))
        is_holiday = 1.0 if features.get("is_holiday") else 0.0

        # Check if model expects sequence features (FairTabularForecaster with 56 features)
        if hasattr(model, "feature_names_") and "demand_lag_1" in getattr(model, "feature_names_", []):
            shop_code = SHOP_CODE_MAP.get(shop_id or "SHOP_01", 0)
            cat_code = CAT_CODE_MAP.get(category, 0)
            city_code = CITY_CODE_MAP.get(city or "Bhopal", 0)
            btype_code = BTYPE_CODE_MAP.get(btype, 2)
            weather_code = WEATHER_CODE_MAP.get(weather, 0)

            # Calendar features
            is_wknd = 1.0 if day_of_week in (5, 6) else 0.0
            sin_doy = math.sin(2.0 * math.pi * day_of_year / 365.25)
            cos_doy = math.cos(2.0 * math.pi * day_of_year / 365.25)

            # Historical baseline priors
            cat_priors = meta.get("category_baseline_means", {})
            cat_mean = float(cat_priors.get(category, 100.0))
            cat_stds = meta.get("category_baseline_stds", {})
            cat_std = float(cat_stds.get(category, 25.0))

            # Assemble 28 lags from history
            if history and len(history) > 0:
                h_vals = list(history)
                if len(h_vals) < 28:
                    pad = [cat_mean] * (28 - len(h_vals))
                    h_vals = pad + h_vals
                h_recent = h_vals[-28:]
                lags = list(reversed(h_recent))  # lag 1 is h_recent[-1], lag 2 is h_recent[-2]...
                rm7 = float(np.mean(h_recent[-7:]))
                rs7 = float(np.std(h_recent[-7:]))
                rm28 = float(np.mean(h_recent))
                rs28 = float(np.std(h_recent))
                same_dow = float(h_recent[-7])
                shop_other = cat_mean * 1.02
                city_other = cat_mean * 0.98
            else:
                lags = [cat_mean] * 28
                rm7 = cat_mean
                rs7 = cat_std
                rm28 = cat_mean
                rs28 = cat_std
                same_dow = cat_mean
                shop_other = cat_mean
                city_other = cat_mean

            row_dict: Dict[str, Any] = {
                "shop_code": shop_code,
                "cat_code": cat_code,
                "city_code": city_code,
                "btype_code": btype_code,
                "shelf_life": shelf_life,
                "storage_temp": storage_temp,
                "dow": float(day_of_week),
                "is_weekend": is_wknd,
                "sin_doy": sin_doy,
                "cos_doy": cos_doy,
                "promo_future": 1.0 if promo_bool else 0.0,
                "rain_future": rain_mm,
                "temp_future": temp_c,
                "weather_code": float(weather_code),
                "fest_code": is_holiday,
                "promo_origin": 1.0 if promo_bool else 0.0,
                "rain_origin": rain_mm,
                "temp_origin": temp_c,
                "storage_origin": storage_temp,
                "unit_cost": unit_cost,
                "unit_price": unit_price,
            }

            for lag_idx in range(1, 29):
                row_dict[f"demand_lag_{lag_idx}"] = float(lags[lag_idx - 1])

            row_dict["rolling_mean_7"] = rm7
            row_dict["rolling_std_7"] = rs7
            row_dict["rolling_mean_28"] = rm28
            row_dict["rolling_std_28"] = rs28
            row_dict["same_weekday_last_week"] = same_dow
            row_dict["shop_other_cats_mean"] = shop_other
            row_dict["city_other_shops_mean"] = city_other

            X_df = pd.DataFrame([row_dict], columns=model.feature_names_)
            raw_point = float(model.predict(X_df)[0])
            low_arr, high_arr = model.predict_interval(X_df)

            forecast_demand = max(1.0, round(raw_point, 1))
            range_min = max(0.0, round(float(low_arr[0]), 1))
            range_max = max(forecast_demand, round(float(high_arr[0]), 1))

        elif hasattr(model, "predict_interval"):
            # Legacy Track B HistGradientBoostingDemandModel
            promo_str = "Yes" if promo_bool else "No"
            row_dict = {
                "Temperature_C": temp_c,
                "Rain_mm": rain_mm,
                "Shelf_Life_Days": shelf_life,
                "Lead_Time_Days": float(features.get("lead_time_days", 1.0)),
                "Unit_Cost_INR": unit_cost,
                "Unit_Price_INR": unit_price,
                "Storage_Temperature": storage_temp,
                "Latitude": 23.2599,
                "Longitude": 77.4126,
                "Promotion": promo_str,
                "Weather": weather,
                "Festival": "None",
                "City": city or "Bhopal",
                "Business_Type": btype,
                "Food_Category": category,
                "Shop_ID": shop_id or "S01",
                "Day_Of_Week": day_of_week,
                "day_of_week": day_of_week,
                "month": month,
                "Is_Weekend": 1 if day_of_week in (5, 6) else 0,
                "Is_Holiday": int(is_holiday),
            }
            df = pd.DataFrame([row_dict])
            yhat_arr, low_arr, high_arr = model.predict_interval(df, coverage=0.90)
            forecast_demand = max(1.0, round(float(yhat_arr[0]), 1))
            range_min = max(0.0, round(float(low_arr[0]), 1))
            range_max = max(forecast_demand, round(float(high_arr[0]), 1))
        else:
            # Fallback Tabular Poisson model
            promo_str = "Yes" if promo_bool else "No"
            df = pd.DataFrame([{
                "Business_Type": btype,
                "Food_Category": category,
                "Promotion": promo_str,
                "Weather": weather,
                "day_of_week": day_of_week,
                "month": month,
                "Shelf_Life_Days": shelf_life,
                "Storage_Temperature": storage_temp,
            }])
            raw_pred = float(model.predict(df)[0])
            forecast_demand = max(1.0, round(raw_pred, 1))
            forecast_std = 17.63
            range_min = max(0.0, round(forecast_demand - 1.645 * forecast_std, 1))
            range_max = round(forecast_demand + 1.645 * forecast_std, 1)

        return forecast_demand, range_min, range_max, meta

    @classmethod
    def is_model_available(cls, category: Optional[str] = None) -> bool:
        """Check if demand model artifact is available."""
        try:
            cls.get_demand_model(category=category)
            return True
        except Exception:
            return False

    @classmethod
    def get_active_model(cls, category: Optional[str] = None) -> Any:
        """Return the active demand model instance."""
        model, _ = cls.get_demand_model(category=category)
        return model

    @classmethod
    def prepare_sequence_features(
        cls,
        shop_id: str = "SHOP_01",
        category: str = "Bakery",
        business_type: str = "Restaurant",
        target_date: Union[str, date, datetime] = "2026-03-15",
        promo: bool = False,
        weather: str = "Sunny",
        city: str = "Bhopal",
        historical_sales: Optional[Sequence[float]] = None,
        shelf_life: Optional[float] = None,
        storage_temp: Optional[float] = None,
        unit_cost: Optional[float] = None,
        unit_price: Optional[float] = None,
        rain_mm: float = 0.0,
        temp_c: float = 25.0,
        is_holiday: bool = False,
    ) -> pd.DataFrame:
        """Build a 56-feature single-row DataFrame compatible with FairTabularForecaster."""
        cat_props = CATEGORY_DEFAULTS.get(category, CATEGORY_DEFAULTS["Prepared Food"])
        s_life = float(shelf_life if shelf_life is not None else cat_props["shelf_life"])
        s_temp = float(storage_temp if storage_temp is not None else cat_props["storage_temp"])
        u_cost = float(unit_cost if unit_cost is not None else cat_props["unit_cost"])
        u_price = float(unit_price if unit_price is not None else cat_props["unit_price"])

        dt = pd.to_datetime(target_date)
        dow = float(dt.dayofweek)
        doy = float(dt.dayofyear)
        is_wknd = 1.0 if dow in (5, 6) else 0.0
        sin_doy = math.sin(2.0 * math.pi * doy / 365.25)
        cos_doy = math.cos(2.0 * math.pi * doy / 365.25)

        # Categorical codes
        shop_code = SHOP_CODE_MAP.get(shop_id, 0)
        cat_code = CAT_CODE_MAP.get(category, 0)
        city_code = CITY_CODE_MAP.get(city, 0)
        btype_code = BTYPE_CODE_MAP.get(business_type, 2)
        weather_code = WEATHER_CODE_MAP.get(weather, 0)

        # Historical baseline priors
        _, meta = cls.get_demand_model(category=category)
        cat_priors = meta.get("category_baseline_means", {})
        cat_mean = float(cat_priors.get(category, 100.0))
        cat_stds = meta.get("category_baseline_stds", {})
        cat_std = float(cat_stds.get(category, 25.0))

        if historical_sales and len(historical_sales) > 0:
            h_vals = list(historical_sales)
            if len(h_vals) < 28:
                pad = [cat_mean] * (28 - len(h_vals))
                h_vals = pad + h_vals
            h_recent = h_vals[-28:]
            lags = list(reversed(h_recent))
            rm7 = float(np.mean(h_recent[-7:]))
            rs7 = float(np.std(h_recent[-7:]))
            rm28 = float(np.mean(h_recent))
            rs28 = float(np.std(h_recent))
            same_dow = float(h_recent[-7])
            shop_other = cat_mean * 1.02
            city_other = cat_mean * 0.98
        else:
            lags = [cat_mean] * 28
            rm7 = cat_mean
            rs7 = cat_std
            rm28 = cat_mean
            rs28 = cat_std
            same_dow = cat_mean
            shop_other = cat_mean
            city_other = cat_mean

        row_dict: Dict[str, Any] = {
            "shop_code": shop_code,
            "cat_code": cat_code,
            "city_code": city_code,
            "btype_code": btype_code,
            "shelf_life": s_life,
            "lead_time": 1.0,
            "dow": dow,
            "is_weekend": is_wknd,
            "sin_doy": sin_doy,
            "cos_doy": cos_doy,
            "promo_future": 1.0 if promo else 0.0,
            "rain_future": rain_mm,
            "temp_future": temp_c,
            "weather_code": float(weather_code),
            "fest_code": 1.0 if is_holiday else 0.0,
            "promo_origin": 1.0 if promo else 0.0,
            "rain_origin": rain_mm,
            "temp_origin": temp_c,
            "storage_origin": s_temp,
            "unit_cost": u_cost,
            "unit_price": u_price,
        }

        for lag_idx in range(1, 29):
            row_dict[f"demand_lag_{lag_idx}"] = float(lags[lag_idx - 1])

        row_dict["rolling_mean_7"] = rm7
        row_dict["rolling_std_7"] = rs7
        row_dict["rolling_mean_28"] = rm28
        row_dict["rolling_std_28"] = rs28
        row_dict["same_weekday_last_week"] = same_dow
        row_dict["shop_other_cats_mean"] = shop_other
        row_dict["city_other_shops_mean"] = city_other

        cols = list(row_dict.keys())
        return pd.DataFrame([row_dict], columns=cols)

    @classmethod
    def get_registry_status(cls) -> Dict[str, Any]:
        """Return operational status and metadata for all registered models."""
        _, d_meta = cls.get_demand_model()
        _, w_meta = cls.get_waste_classifier()
        return {
            "status": "operational",
            "registry_status": "active",
            "active_model_name": d_meta.get("model_name", "HistGradientBoosting_History"),
            "total_features": len(d_meta.get("feature_names", [])) or 56,
            "active_demand_model": {
                "name": d_meta.get("model_name"),
                "version": d_meta.get("version"),
                "data_origin": d_meta.get("data_origin"),
                "is_fallback": d_meta.get("is_fallback", False),
                "metrics": d_meta.get("metrics", {}),
            },
            "active_waste_classifier": {
                "name": w_meta.get("model_name"),
                "version": w_meta.get("version"),
                "data_origin": w_meta.get("data_origin"),
                "is_fallback": w_meta.get("is_fallback", False),
            },
            "winning_model_by_category": WINNING_MODEL_BY_CATEGORY,
            "supported_categories": SUPPORTED_CATEGORIES,
        }


def get_registry_status() -> Dict[str, Any]:
    """Module-level convenience wrapper for ModelRegistry.get_registry_status."""
    return ModelRegistry.get_registry_status()


def prepare_sequence_features(**kwargs) -> pd.DataFrame:
    """Module-level convenience wrapper for ModelRegistry.prepare_sequence_features."""
    return ModelRegistry.prepare_sequence_features(**kwargs)

