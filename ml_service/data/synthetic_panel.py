"""Synthetic panel dataset loading, schema validation, and invariant verification.

Implements Task 0 requirements for Time-series Track B:
- Loader data/synthetic_panel.py that accepts both the 16-column and the full 33-column schema.
- Schema allow-list loaded from data_dictionary_synthetic.csv (with strict fail-loud behavior on unexpected columns).
- Parse Date and Expiry_Date.
- Blank Festival converted to "no festival".
- Invariant tests on every row:
    1. Remaining = Purchase - Sold
    2. Sold = min(Purchase, Demand)
    3. Waste <= Remaining
    4. Donated_Units <= Waste_Quantity (when column present)
    5. Donation_Made = Yes only when waste > 0
    6. Carried_Forward = Remaining - Waste (when column present)
    7. Expiry_Date = Date + Shelf_Life_Days (when column present)
    8. Exactly one row per (Date, Shop_ID, Food_Category) and no missing days (when series columns present).
- Enforce invariant: Never use Units_Sold as a demand target.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

DEFAULT_RAW_DIR = Path(__file__).resolve().parent / "raw"
DEFAULT_SYNTHETIC_FULL_PATH = DEFAULT_RAW_DIR / "synthetic_panel_full.csv"
DEFAULT_SYNTHETIC_CORE16_PATH = DEFAULT_RAW_DIR / "synthetic_panel_core16.csv"
DEFAULT_SYNTHETIC_DICT_PATH = DEFAULT_RAW_DIR / "data_dictionary_synthetic.csv"

DEFAULT_SYNTHETIC_SEQ_PATH = DEFAULT_RAW_DIR / "synthetic_sequence_panel_full.csv"
DEFAULT_SYNTHETIC_SEQ_EVENTS_PATH = DEFAULT_RAW_DIR / "synthetic_sequence_events_log.csv"

# Core 16 columns matching the benchmark CSV schema

CORE16_COLUMNS: List[str] = [
    "Inventory_ID",
    "Date",
    "Business_Type",
    "Food_Category",
    "Purchase_Quantity",
    "Units_Sold",
    "Remaining_Stock",
    "Shelf_Life_Days",
    "Storage_Temperature",
    "Daily_Demand",
    "Promotion",
    "Weather",
    "Waste_Quantity",
    "Waste_Reason",
    "Donation_Made",
    "Waste_Level",
]

# Full 33 columns from data_dictionary_synthetic.csv
FULL33_COLUMNS: List[str] = [
    "Inventory_ID",
    "Date",
    "Business_Type",
    "Food_Category",
    "Purchase_Quantity",
    "Units_Sold",
    "Remaining_Stock",
    "Shelf_Life_Days",
    "Storage_Temperature",
    "Daily_Demand",
    "Promotion",
    "Weather",
    "Waste_Quantity",
    "Waste_Reason",
    "Donation_Made",
    "Waste_Level",
    "Shop_ID",
    "City",
    "Latitude",
    "Longitude",
    "Temperature_C",
    "Rain_mm",
    "Day_Of_Week",
    "Is_Weekend",
    "Is_Holiday",
    "Festival",
    "Expiry_Date",
    "Donated_Units",
    "Carried_Forward_Units",
    "Unit_Cost_INR",
    "Unit_Price_INR",
    "Lead_Time_Days",
    "Data_Origin",
]

ALLOWED_CATEGORIES: Dict[str, Set[str]] = {
    "Business_Type": {"Restaurant", "Supermarket", "Cafeteria", "Cloud Kitchen"},
    "Food_Category": {"Fruits", "Vegetables", "Dairy", "Bakery", "Meat", "Prepared Food"},
    "Promotion": {"Yes", "No"},
    "Weather": {"Sunny", "Rainy", "Cloudy", "Hot"},
    "Waste_Reason": {"Expired", "Overproduction", "Low Demand", "Storage Issue", "No Waste"},
    "Donation_Made": {"Yes", "No"},
    "Waste_Level": {"Low", "Medium", "High"},
    "City": {"Bhopal", "Mumbai", "Delhi", "Bengaluru"},
    "Shop_ID": {
        "S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08",
        "S09", "S10", "S11", "S12",
    },
    "Data_Origin": {"synthetic_v1", "synthetic_seq_v2"},
}

NON_NEGATIVE_COLUMNS: List[str] = [
    "Purchase_Quantity",
    "Units_Sold",
    "Remaining_Stock",
    "Daily_Demand",
    "Waste_Quantity",
    "Shelf_Life_Days",
    "Donated_Units",
    "Carried_Forward_Units",
    "Unit_Cost_INR",
    "Unit_Price_INR",
    "Lead_Time_Days",
]


class SchemaValidationError(ValueError):
    """Raised when synthetic dataset fails schema or domain value validation."""
    pass


class InvariantViolationError(ValueError):
    """Raised when an accounting, logic, or temporal invariant is violated."""
    pass


def load_allow_list(data_dict_path: Optional[Path | str] = None) -> Tuple[List[str], List[str]]:
    """Load core16 and full column allow-lists from data_dictionary_synthetic.csv.

    Returns:
        Tuple of (core16_columns, full_columns).
    """
    dict_path = Path(data_dict_path) if data_dict_path else DEFAULT_SYNTHETIC_DICT_PATH
    if not dict_path.exists():
        return CORE16_COLUMNS, FULL33_COLUMNS

    core16_cols: List[str] = []
    full_cols: List[str] = []
    with open(dict_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",", 3)
        if len(parts) >= 3:
            col_name = parts[0].strip()
            in_core = parts[2].strip().lower()
            full_cols.append(col_name)
            if in_core == "yes":
                core16_cols.append(col_name)

    return core16_cols if core16_cols else CORE16_COLUMNS, full_cols if full_cols else FULL33_COLUMNS


def validate_demand_target(target_col: str) -> None:
    """Enforce critical invariant: Units_Sold must NEVER be used as a demand target.

    Raises:
        ValueError: If target_col is 'Units_Sold' or case-insensitive equivalent.
    """
    if str(target_col).strip().lower() == "units_sold":
        raise ValueError(
            "CRITICAL INVARIANT VIOLATION: 'Units_Sold' must never be used as a demand target. "
            "Units_Sold is capped by Purchase_Quantity (Units_Sold = min(Purchase, Demand)) "
            "on stock-out days and does not reflect latent customer demand."
        )


def validate_schema(
    df: pd.DataFrame,
    data_dict_path: Optional[Path | str] = None,
) -> str:
    """Validate dataframe columns and values against the synthetic allow-list.

    Accepts:
    - 16-column core benchmark schema
    - 33-column full synthetic panel schema

    Fails loudly on:
    - Unexpected columns outside the allow-list
    - Missing required columns for the detected schema
    - Invalid categorical levels
    - Negative numeric quantities

    Returns:
        "core16" or "full" schema type string.

    Raises:
        SchemaValidationError: If validation fails.
    """
    core16_cols, full_cols = load_allow_list(data_dict_path)
    actual_cols = list(df.columns)
    actual_set = set(actual_cols)

    # Determine schema type
    if actual_set == set(core16_cols):
        schema_type = "core16"
        expected_cols = core16_cols
    elif actual_set == set(full_cols):
        schema_type = "full"
        expected_cols = full_cols
    else:
        # Detailed error diagnosing what went wrong
        unexpected = actual_set - set(full_cols)
        if unexpected:
            raise SchemaValidationError(
                f"Unexpected extra columns detected outside allow-list: {sorted(list(unexpected))}"
            )
        missing_core = set(core16_cols) - actual_set
        if missing_core:
            raise SchemaValidationError(
                f"Missing mandatory core columns: {sorted(list(missing_core))}"
            )
        missing_full = set(full_cols) - actual_set
        raise SchemaValidationError(
            f"Columns do not match either core16 (16 cols) or full (33 cols) schema. "
            f"Missing full columns: {sorted(list(missing_full))}"
        )

    # Validate categorical column values
    for col, allowed in ALLOWED_CATEGORIES.items():
        if col in df.columns:
            # For Festival, blank is converted to "no festival" prior to or during load
            series = df[col].dropna()
            invalid_vals = set(series.unique()) - allowed
            if invalid_vals:
                raise SchemaValidationError(
                    f"Invalid values in categorical column '{col}': {invalid_vals}. "
                    f"Allowed: {allowed}"
                )

    # Validate non-negative quantity and price columns
    for col in NON_NEGATIVE_COLUMNS:
        if col in df.columns:
            neg_count = (df[col].dropna() < 0).sum()
            if neg_count > 0:
                raise SchemaValidationError(
                    f"Column '{col}' has {neg_count} negative values; non-negative quantities required."
                )

    return schema_type


def validate_invariants(df: pd.DataFrame) -> Dict[str, bool]:
    """Test accounting, logic, and temporal invariants across all rows.

    Invariants checked:
    1. Remaining = Purchase - Sold
    2. Sold = min(Purchase, Demand)
    3. Waste <= Remaining
    4. Donated_Units <= Waste_Quantity (when column present)
    5. Donation_Made = Yes only when waste > 0
    6. Carried_Forward = Remaining - Waste (when column present)
    7. Expiry_Date = Date + Shelf_Life_Days (when column present)
    8. Exactly one row per (Date, Shop_ID, Food_Category) and no missing days (when columns present)

    Returns:
        Dict of invariant name -> boolean (True if passed).

    Raises:
        InvariantViolationError: If any invariant fails.
    """
    results: Dict[str, bool] = {}

    # 1. Remaining = Purchase - Sold
    cond1 = (df["Remaining_Stock"] == df["Purchase_Quantity"] - df["Units_Sold"]).all()
    results["Remaining = Purchase - Sold"] = bool(cond1)
    if not cond1:
        bad = df[df["Remaining_Stock"] != df["Purchase_Quantity"] - df["Units_Sold"]]
        raise InvariantViolationError(
            f"Invariant 'Remaining = Purchase - Sold' failed on {len(bad)} rows."
        )

    # 2. Sold = min(Purchase, Demand)
    cond2 = (df["Units_Sold"] == np.minimum(df["Purchase_Quantity"], df["Daily_Demand"])).all()
    results["Sold = min(Purchase, Demand)"] = bool(cond2)
    if not cond2:
        bad = df[df["Units_Sold"] != np.minimum(df["Purchase_Quantity"], df["Daily_Demand"])]
        raise InvariantViolationError(
            f"Invariant 'Sold = min(Purchase, Demand)' failed on {len(bad)} rows."
        )

    # 3. Waste <= Remaining
    cond3 = (df["Waste_Quantity"] <= df["Remaining_Stock"]).all()
    results["Waste <= Remaining"] = bool(cond3)
    if not cond3:
        bad = df[df["Waste_Quantity"] > df["Remaining_Stock"]]
        raise InvariantViolationError(
            f"Invariant 'Waste <= Remaining' failed on {len(bad)} rows."
        )

    # 4. Donated_Units <= Waste_Quantity (full schema)
    if "Donated_Units" in df.columns:
        cond4 = (df["Donated_Units"] <= df["Waste_Quantity"]).all()
        results["Donated_Units <= Waste_Quantity"] = bool(cond4)
        if not cond4:
            bad = df[df["Donated_Units"] > df["Waste_Quantity"]]
            raise InvariantViolationError(
                f"Invariant 'Donated_Units <= Waste_Quantity' failed on {len(bad)} rows."
            )

    # 5. Donation_Made = Yes only when waste > 0
    donation_yes = df[df["Donation_Made"] == "Yes"]
    cond5 = (donation_yes["Waste_Quantity"] > 0).all()
    results["Donation_Made = Yes only when waste > 0"] = bool(cond5)
    if not cond5:
        bad = donation_yes[donation_yes["Waste_Quantity"] <= 0]
        raise InvariantViolationError(
            f"Invariant 'Donation_Made = Yes only when waste > 0' failed on {len(bad)} rows."
        )

    # 6. Carried_Forward = Remaining - Waste (full schema)
    if "Carried_Forward_Units" in df.columns:
        cond6 = (df["Carried_Forward_Units"] == df["Remaining_Stock"] - df["Waste_Quantity"]).all()
        results["Carried_Forward = Remaining - Waste"] = bool(cond6)
        if not cond6:
            bad = df[df["Carried_Forward_Units"] != df["Remaining_Stock"] - df["Waste_Quantity"]]
            raise InvariantViolationError(
                f"Invariant 'Carried_Forward = Remaining - Waste' failed on {len(bad)} rows."
            )

    # 7. Expiry_Date = Date + Shelf_Life_Days (full schema)
    if "Expiry_Date" in df.columns and "Date" in df.columns and "Shelf_Life_Days" in df.columns:
        dt_expiry = pd.to_datetime(df["Expiry_Date"])
        dt_date = pd.to_datetime(df["Date"])
        diff_days = (dt_expiry - dt_date).dt.days
        cond7 = (diff_days == df["Shelf_Life_Days"]).all()
        results["Expiry_Date = Date + Shelf_Life_Days"] = bool(cond7)
        if not cond7:
            bad = df[diff_days != df["Shelf_Life_Days"]]
            raise InvariantViolationError(
                f"Invariant 'Expiry_Date = Date + Shelf_Life_Days' failed on {len(bad)} rows."
            )

    # 8. Exactly one row per (Date, Shop_ID, Food_Category) and no missing days
    if "Shop_ID" in df.columns and "Date" in df.columns and "Food_Category" in df.columns:
        dup_count = df.duplicated(["Date", "Shop_ID", "Food_Category"]).sum()
        cond8_dup = dup_count == 0
        results["No duplicates (Date, Shop_ID, Food_Category)"] = bool(cond8_dup)
        if not cond8_dup:
            raise InvariantViolationError(
                f"Found {dup_count} duplicate (Date, Shop_ID, Food_Category) combinations."
            )

        total_days = df["Date"].nunique()
        series_day_counts = df.groupby(["Shop_ID", "Food_Category"])["Date"].nunique()
        cond8_days = (series_day_counts == total_days).all()
        results["No missing days in any series"] = bool(cond8_days)
        if not cond8_days:
            missing_series = series_day_counts[series_day_counts != total_days]
            raise InvariantViolationError(
                f"Missing days detected in {len(missing_series)} series out of {len(series_day_counts)}."
            )

    return results


def load_synthetic_panel(
    path: Optional[Path | str] = None,
    validate: bool = True,
    enforce_invariants: bool = True,
    data_dict_path: Optional[Path | str] = None,
) -> pd.DataFrame:
    """Load, parse, validate, and clean synthetic panel dataset.

    Args:
        path: Path to synthetic CSV file (defaults to synthetic_panel_full.csv).
        validate: If True, validate columns and domain values against allow-list.
        enforce_invariants: If True, verify all logical and temporal invariants.
        data_dict_path: Optional custom path to data dictionary CSV.

    Returns:
        Cleaned pd.DataFrame with parsed Date, Expiry_Date, and "no festival" for blanks.

    Raises:
        FileNotFoundError: If dataset path does not exist.
        SchemaValidationError: If unexpected columns or invalid values are found.
        InvariantViolationError: If an accounting or logic invariant fails.
    """
    file_path = Path(path) if path else DEFAULT_SYNTHETIC_FULL_PATH
    if not file_path.exists():
        raise FileNotFoundError(f"Synthetic dataset not found at {file_path}")

    # Read CSV
    df = pd.read_csv(file_path)

    # Validate schema against allow-list before transformations
    if validate:
        validate_schema(df, data_dict_path=data_dict_path)

    # Parse dates
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    if "Expiry_Date" in df.columns:
        df["Expiry_Date"] = pd.to_datetime(df["Expiry_Date"])

    # Blank Festival means "no festival"
    if "Festival" in df.columns:
        df["Festival"] = df["Festival"].fillna("").astype(str).str.strip()
        df["Festival"] = df["Festival"].replace("", "no festival")

    # Invariant checks
    if enforce_invariants:
        validate_invariants(df)

    return df
