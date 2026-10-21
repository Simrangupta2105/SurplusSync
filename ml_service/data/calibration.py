"""Empirical dataset calibration module for SurplusSync.

Extracts empirical operating ratios from food_waste_dataset.csv and generates
ml_service/config/calibration.yaml to calibrate synthetic ledger generation (Track B).

Extracted parameters:
1. Relative demand scale by business type (Restaurant, Supermarket, Cafeteria, Cloud Kitchen)
2. Promotion lift (mean/median ratio of demand with vs without promotion)
3. Weather multipliers (relative demand scaling by weather condition)
4. Per-category waste rates (waste / purchase and waste / remaining) and waste reason mix
5. Donation probability given waste (and zero donation when waste is 0)
6. Shelf-life and storage temperature distribution by category
7. Distribution of purchase/demand ratio
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import yaml

from ml_service.data.food_waste import (
    DEFAULT_DATASET_PATH,
    load_raw_data,
)

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEFAULT_CALIBRATION_PATH = DEFAULT_CONFIG_DIR / "calibration.yaml"


def compute_calibration_parameters(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute empirical calibration parameters directly from raw/cleaned dataset.

    All statistics are computed dynamically from the data with no hard-coded figures.
    """
    df_clean = df.copy()

    # Fill missing weather with Unknown for consistent grouping
    df_clean["Weather"] = df_clean["Weather"].fillna("Unknown")

    # Overall demand baseline
    known_demand_df = df_clean.dropna(subset=["Daily_Demand"])
    overall_mean_demand = float(known_demand_df["Daily_Demand"].mean())
    overall_median_demand = float(known_demand_df["Daily_Demand"].median())
    overall_std_demand = float(known_demand_df["Daily_Demand"].std())

    # 1. Relative Demand Scale by Business Type
    biz_stats: Dict[str, Dict[str, float]] = {}
    biz_group = known_demand_df.groupby("Business_Type")["Daily_Demand"]
    for biz_type, s in biz_group:
        mean_val = float(s.mean())
        biz_stats[str(biz_type)] = {
            "relative_scale": round(mean_val / overall_mean_demand, 4),
            "mean_demand": round(mean_val, 2),
            "median_demand": round(float(s.median()), 2),
            "std_demand": round(float(s.std()), 2),
            "sample_count": int(s.count()),
        }

    # 2. Promotion Lift
    promo_group = known_demand_df.groupby("Promotion")["Daily_Demand"]
    promo_yes_mean = float(promo_group.get_group("Yes").mean())
    promo_no_mean = float(promo_group.get_group("No").mean())
    promo_yes_median = float(promo_group.get_group("Yes").median())
    promo_no_median = float(promo_group.get_group("No").median())
    promo_lift_ratio = round(promo_yes_mean / promo_no_mean, 4)

    promotion_stats = {
        "lift_multiplier": promo_lift_ratio,
        "mean_demand_promo_yes": round(promo_yes_mean, 2),
        "mean_demand_promo_no": round(promo_no_mean, 2),
        "median_demand_promo_yes": round(promo_yes_median, 2),
        "median_demand_promo_no": round(promo_no_median, 2),
        "pct_increase": round((promo_lift_ratio - 1.0) * 100, 2),
    }

    # 3. Weather Multipliers
    weather_stats: Dict[str, Dict[str, float]] = {}
    weather_group = known_demand_df.groupby("Weather")["Daily_Demand"]
    for w_name, s in weather_group:
        w_mean = float(s.mean())
        weather_stats[str(w_name)] = {
            "multiplier": round(w_mean / overall_mean_demand, 4),
            "mean_demand": round(w_mean, 2),
            "sample_count": int(s.count()),
        }

    # 4. Category-level Waste Rates, Reason Mix, and Shelf Life
    categories_stats: Dict[str, Any] = {}
    cat_group = df_clean.groupby("Food_Category")
    for cat_name, sub in cat_group:
        total_purchase = float(sub["Purchase_Quantity"].sum())
        total_remaining = float(sub["Remaining_Stock"].sum())
        total_waste = float(sub["Waste_Quantity"].sum())

        waste_rate_purchase = round(total_waste / total_purchase, 4) if total_purchase > 0 else 0.0
        waste_rate_remaining = round(total_waste / total_remaining, 4) if total_remaining > 0 else 0.0

        # Reason mix
        reason_counts = sub["Waste_Reason"].value_counts(normalize=True).to_dict()
        reason_mix = {r: round(float(pct), 4) for r, pct in reason_counts.items()}

        # Shelf life stats
        sl = sub["Shelf_Life_Days"].dropna()
        shelf_life_stats = {
            "min": float(sl.min()),
            "p10": float(sl.quantile(0.10)),
            "p25": float(sl.quantile(0.25)),
            "median": float(sl.median()),
            "p75": float(sl.quantile(0.75)),
            "p90": float(sl.quantile(0.90)),
            "max": float(sl.max()),
            "mean": round(float(sl.mean()), 2),
            "std": round(float(sl.std()), 2),
        }

        # Storage temperature stats
        st = sub["Storage_Temperature"].dropna()
        temp_stats = {
            "min": float(st.min()),
            "p25": float(st.quantile(0.25)),
            "median": float(st.median()),
            "p75": float(st.quantile(0.75)),
            "max": float(st.max()),
            "mean": round(float(st.mean()), 2),
            "std": round(float(st.std()), 2),
        }

        # Category-level donation given waste
        cat_waste_rows = sub[sub["Waste_Quantity"] > 0]
        p_don_cat = float((cat_waste_rows["Donation_Made"] == "Yes").mean()) if len(cat_waste_rows) > 0 else 0.0

        categories_stats[str(cat_name)] = {
            "waste_rate_of_purchase": waste_rate_purchase,
            "waste_rate_of_remaining": waste_rate_remaining,
            "waste_reason_mix": reason_mix,
            "p_donation_given_waste": round(p_don_cat, 4),
            "shelf_life_days": shelf_life_stats,
            "storage_temperature": temp_stats,
        }

    # 5. Overall Donation Probability Given Waste
    waste_rows = df_clean[df_clean["Waste_Quantity"] > 0]
    p_donation_given_waste = float((waste_rows["Donation_Made"] == "Yes").mean())
    zero_waste_rows = df_clean[df_clean["Waste_Quantity"] == 0]
    p_donation_given_zero_waste = float((zero_waste_rows["Donation_Made"] == "Yes").mean())

    donation_stats = {
        "p_donation_given_waste": round(p_donation_given_waste, 4),
        "p_donation_given_zero_waste": round(p_donation_given_zero_waste, 4),
        "total_waste_records": int(len(waste_rows)),
        "donated_waste_records": int((waste_rows["Donation_Made"] == "Yes").sum()),
    }

    # 6. Purchase / Demand Ratio Distribution
    pd_ratio = (known_demand_df["Purchase_Quantity"] / known_demand_df["Daily_Demand"]).dropna()
    purchase_demand_stats = {
        "min": round(float(pd_ratio.min()), 4),
        "p10": round(float(pd_ratio.quantile(0.10)), 4),
        "p25": round(float(pd_ratio.quantile(0.25)), 4),
        "median": round(float(pd_ratio.median()), 4),
        "p75": round(float(pd_ratio.quantile(0.75)), 4),
        "p90": round(float(pd_ratio.quantile(0.90)), 4),
        "max": round(float(pd_ratio.max()), 4),
        "mean": round(float(pd_ratio.mean()), 4),
        "std": round(float(pd_ratio.std()), 4),
    }

    # Assembled Configuration Dictionary
    calibration_config = {
        "meta": {
            "generated_from": "ml_service/data/raw/food_waste_dataset.csv",
            "total_records": int(len(df_clean)),
            "dataset_overall_mean_demand": round(overall_mean_demand, 2),
            "dataset_overall_median_demand": round(overall_median_demand, 2),
            "dataset_overall_std_demand": round(overall_std_demand, 2),
        },
        "business_types": biz_stats,
        "promotion": promotion_stats,
        "weather": weather_stats,
        "categories": categories_stats,
        "donation": donation_stats,
        "purchase_demand_ratio": purchase_demand_stats,
    }

    return calibration_config


def generate_calibration_yaml(
    raw_dataset_path: Path | str = DEFAULT_DATASET_PATH,
    output_path: Optional[Path | str] = None,
) -> Path:
    """Read raw dataset, compute empirical calibration parameters, and write to YAML."""
    if output_path is None:
        output_path = DEFAULT_CALIBRATION_PATH
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    df_raw = load_raw_data(raw_dataset_path)
    config = compute_calibration_parameters(df_raw)

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, sort_keys=False, default_flow_style=False, indent=2)

    print(f"Successfully generated calibration configuration: {output_path}")
    return output_path


def load_calibration_config(path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Load and return calibration config YAML."""
    if path is None:
        path = DEFAULT_CALIBRATION_PATH
    else:
        path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Calibration file not found at {path}. Run generate_calibration_yaml() first.")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config


if __name__ == "__main__":
    generate_calibration_yaml()
