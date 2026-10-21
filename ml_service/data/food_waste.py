"""Food waste dataset loading, schema validation, censoring, and cleaning rules.

Implements Task 1 requirements:
- Parse dates and validate schema against data dictionary; fail loudly on unexpected columns or values.
- Missing Daily_Demand:
    - If Units_Sold < Purchase_Quantity: recover demand = Units_Sold (demand_recovered=True, demand_censored=False).
    - If Units_Sold == Purchase_Quantity: demand is censored (demand_censored=True, demand_recovered=False).
    - Report counts for each case.
- Missing Weather becomes "Unknown" (an explicit categorical level).
- Missing Shelf_Life_Days and Storage_Temperature are imputed with category medians
  and flagged with *_imputed columns; imputation parameters are fitted strictly on
  training data (no data leakage).
- Enforce invariant: Never use Units_Sold as a demand target.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

DEFAULT_RAW_DIR = Path(__file__).resolve().parent / "raw"
DEFAULT_DATASET_PATH = DEFAULT_RAW_DIR / "food_waste_dataset.csv"
DEFAULT_DATA_DICT_PATH = DEFAULT_RAW_DIR / "data_dictionary.csv"

EXPECTED_COLUMNS: List[str] = [
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

ALLOWED_CATEGORIES: Dict[str, Set[str]] = {
    "Business_Type": {"Restaurant", "Supermarket", "Cafeteria", "Cloud Kitchen"},
    "Food_Category": {"Fruits", "Vegetables", "Dairy", "Bakery", "Meat", "Prepared Food"},
    "Promotion": {"Yes", "No"},
    "Weather": {"Sunny", "Rainy", "Cloudy", "Hot"},
    "Waste_Reason": {"Expired", "Overproduction", "Low Demand", "Storage Issue", "No Waste"},
    "Donation_Made": {"Yes", "No"},
    "Waste_Level": {"Low", "Medium", "High"},
}

NUMERIC_COLUMNS: List[str] = [
    "Purchase_Quantity",
    "Units_Sold",
    "Remaining_Stock",
    "Shelf_Life_Days",
    "Storage_Temperature",
    "Daily_Demand",
    "Waste_Quantity",
]


class SchemaValidationError(ValueError):
    """Raised when dataset fails schema or domain value validation."""
    pass


def validate_demand_target(target_col: str) -> None:
    """Enforce rule: Units_Sold must never be used as a demand target.

    Raises:
        ValueError: If target_col is 'Units_Sold' or case-insensitive equivalent.
    """
    if str(target_col).strip().lower() == "units_sold":
        raise ValueError(
            "CRITICAL RULE VIOLATION: 'Units_Sold' must never be used as a demand target. "
            "Units_Sold is constrained by Purchase_Quantity and reflects truncated demand, "
            "not latent customer demand."
        )


def validate_schema(
    df: pd.DataFrame,
    data_dict_path: Optional[Path | str] = None,
) -> None:
    """Validate dataframe structure, columns, and categorical domains against data dictionary.

    Fails loudly on:
    - Missing expected columns
    - Unexpected extra columns
    - Unknown/invalid categorical values
    - Negative numeric quantities
    - Invalid date formats

    Raises:
        SchemaValidationError: If any rule is violated.
    """
    # 1. Validate columns
    actual_cols = list(df.columns)
    missing_cols = set(EXPECTED_COLUMNS) - set(actual_cols)
    extra_cols = set(actual_cols) - set(EXPECTED_COLUMNS)

    if missing_cols:
        raise SchemaValidationError(f"Missing expected columns from schema: {sorted(missing_cols)}")
    if extra_cols:
        raise SchemaValidationError(f"Unexpected extra columns found in dataset: {sorted(extra_cols)}")

    # 2. Validate categorical domains
    for col, allowed in ALLOWED_CATEGORIES.items():
        if col not in df.columns:
            continue
        # Drop nulls before checking categorical membership
        series_clean = df[col].dropna()
        invalid_mask = ~series_clean.isin(allowed)
        if invalid_mask.any():
            invalid_vals = series_clean[invalid_mask].unique().tolist()
            raise SchemaValidationError(
                f"Column '{col}' contains unexpected/unallowed categorical values: {invalid_vals}. "
                f"Allowed values are: {sorted(allowed)}"
            )

    # 3. Validate numeric columns
    for num_col in ["Purchase_Quantity", "Units_Sold", "Remaining_Stock", "Waste_Quantity"]:
        if num_col in df.columns:
            negative_mask = df[num_col].dropna() < 0
            if negative_mask.any():
                raise SchemaValidationError(f"Column '{num_col}' contains negative values.")

    # 4. Validate Date format (must be parseable YYYY-MM-DD)
    if "Date" in df.columns:
        try:
            pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="raise")
        except Exception as e:
            raise SchemaValidationError(f"Invalid date format in 'Date' column: {e}") from e


class CategoryMedianImputer:
    """Imputes missing Shelf_Life_Days and Storage_Temperature using category medians.

    Learns medians strictly on training data to prevent data leakage into
    validation/test sets.
    """

    def __init__(self) -> None:
        self.shelf_life_medians_: Dict[str, float] = {}
        self.storage_temp_medians_: Dict[str, float] = {}
        self.global_shelf_life_median_: float = 4.0
        self.global_storage_temp_median_: float = 5.0
        self.is_fitted_: bool = False

    def fit(self, df: pd.DataFrame) -> "CategoryMedianImputer":
        """Compute category medians on the provided dataframe (training set only)."""
        if "Food_Category" not in df.columns:
            raise ValueError("Dataframe must contain 'Food_Category' to compute category medians.")

        if "Shelf_Life_Days" in df.columns:
            self.shelf_life_medians_ = (
                df.groupby("Food_Category")["Shelf_Life_Days"]
                .median()
                .dropna()
                .to_dict()
            )
            self.global_shelf_life_median_ = float(df["Shelf_Life_Days"].dropna().median())

        if "Storage_Temperature" in df.columns:
            self.storage_temp_medians_ = (
                df.groupby("Food_Category")["Storage_Temperature"]
                .median()
                .dropna()
                .to_dict()
            )
            self.global_storage_temp_median_ = float(df["Storage_Temperature"].dropna().median())

        self.is_fitted_ = True
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Impute missing values using fitted category medians and add *_imputed flags."""
        if not self.is_fitted_:
            raise ValueError("Imputer has not been fitted. Call fit() on training data first.")

        df_out = df.copy()

        # Shelf_Life_Days
        if "Shelf_Life_Days" in df_out.columns:
            imputed_flag = df_out["Shelf_Life_Days"].isna()
            df_out["Shelf_Life_Days_imputed"] = imputed_flag
            imputed_values = df_out["Food_Category"].map(self.shelf_life_medians_).fillna(self.global_shelf_life_median_)
            df_out["Shelf_Life_Days"] = df_out["Shelf_Life_Days"].fillna(imputed_values)

        # Storage_Temperature
        if "Storage_Temperature" in df_out.columns:
            imputed_flag = df_out["Storage_Temperature"].isna()
            df_out["Storage_Temperature_imputed"] = imputed_flag
            imputed_values = df_out["Food_Category"].map(self.storage_temp_medians_).fillna(self.global_storage_temp_median_)
            df_out["Storage_Temperature"] = df_out["Storage_Temperature"].fillna(imputed_values)

        return df_out

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fit imputer on df and return transformed dataframe."""
        return self.fit(df).transform(df)


def handle_missing_demand_and_censoring(df: pd.DataFrame) -> pd.DataFrame:
    """Apply Task 1 demand recovery and censoring rules.

    Rules:
    - If Daily_Demand is missing (NaN):
        - If Units_Sold < Purchase_Quantity: demand equals Units_Sold (recovered, demand_censored=False, demand_recovered=True)
        - If Units_Sold == Purchase_Quantity: demand is right-censored (demand_censored=True, demand_recovered=False)
    - If Daily_Demand is present:
        - demand_censored=False, demand_recovered=False
    - stockout_flag is set to True whenever Units_Sold == Purchase_Quantity.
    """
    df_out = df.copy()

    # Pre-existing demand indicators
    missing_demand_mask = df_out["Daily_Demand"].isna()
    stockout_mask = df_out["Units_Sold"] >= df_out["Purchase_Quantity"]

    # Initialize tracking flags
    df_out["demand_censored"] = False
    df_out["demand_recovered"] = False
    df_out["stockout_flag"] = stockout_mask

    # Case A: Missing Daily_Demand AND Units_Sold < Purchase_Quantity -> Recover demand
    case_a_mask = missing_demand_mask & (~stockout_mask)
    df_out.loc[case_a_mask, "Daily_Demand"] = df_out.loc[case_a_mask, "Units_Sold"].astype(float)
    df_out.loc[case_a_mask, "demand_recovered"] = True
    df_out.loc[case_a_mask, "demand_censored"] = False

    # Case B: Missing Daily_Demand AND Units_Sold == Purchase_Quantity -> Censored
    case_b_mask = missing_demand_mask & stockout_mask
    df_out.loc[case_b_mask, "demand_censored"] = True
    df_out.loc[case_b_mask, "demand_recovered"] = False
    # Daily_Demand remains NaN for censored rows so models don't train on truncated values

    return df_out


def get_censoring_counts(df: pd.DataFrame) -> Dict[str, int]:
    """Calculate and return breakdown of missing demand recovery and censoring.

    Returns:
        Dict with keys:
            - total_rows: total number of records
            - missing_demand_total: total rows where Daily_Demand was initially missing
            - case_a_recovered: count where Units_Sold < Purchase_Quantity (recovered)
            - case_b_censored: count where Units_Sold == Purchase_Quantity (censored)
            - initially_present_demand: count where Daily_Demand was already present
            - total_censored: count of rows marked demand_censored
    """
    # If the flags already exist, use them; otherwise compute
    if "demand_censored" in df.columns and "demand_recovered" in df.columns:
        case_a = int(df["demand_recovered"].sum())
        case_b = int(df["demand_censored"].sum())
        missing_total = case_a + case_b
        present_count = len(df) - missing_total
    else:
        missing_mask = df["Daily_Demand"].isna()
        stockout_mask = df["Units_Sold"] >= df["Purchase_Quantity"]
        case_a = int((missing_mask & (~stockout_mask)).sum())
        case_b = int((missing_mask & stockout_mask).sum())
        missing_total = int(missing_mask.sum())
        present_count = len(df) - missing_total

    return {
        "total_rows": len(df),
        "missing_demand_total": missing_total,
        "case_a_recovered": case_a,
        "case_b_censored": case_b,
        "initially_present_demand": present_count,
        "total_censored": case_b,
    }


def load_raw_data(
    filepath: Optional[Path | str] = None,
    data_dict_path: Optional[Path | str] = None,
) -> pd.DataFrame:
    """Load raw dataset from CSV, parse dates, and validate schema.

    Fails loudly if unexpected columns, missing columns, or invalid values exist.
    """
    path = Path(filepath) if filepath else DEFAULT_DATASET_PATH
    if not path.exists():
        raise FileNotFoundError(f"Raw dataset file not found at: {path}")

    # Read CSV treating empty strings as NaN
    df = pd.read_csv(path, dtype={"Inventory_ID": str, "Date": str})

    # Validate schema
    validate_schema(df, data_dict_path=data_dict_path)

    # Parse date
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d")

    return df


def clean_food_waste_data(
    df: pd.DataFrame,
    imputer: Optional[CategoryMedianImputer] = None,
    fit_imputer: bool = True,
) -> Tuple[pd.DataFrame, CategoryMedianImputer]:
    """Clean food waste data applying all Task 1 cleaning and censoring rules.

    Rules applied:
    1. Schema validation against data dictionary (fails loudly on errors).
    2. Missing Weather imputed with 'Unknown'.
    3. Missing Daily_Demand processed:
       - Recovered if Units_Sold < Purchase_Quantity
       - Censored if Units_Sold == Purchase_Quantity (flagged with demand_censored)
    4. Category median imputation for Shelf_Life_Days and Storage_Temperature
       with *_imputed flag columns (leakage-free).

    Args:
        df: Input raw or semi-processed DataFrame.
        imputer: Optional CategoryMedianImputer instance. If None and fit_imputer=True,
                 a new imputer is created and fitted on df.
        fit_imputer: Whether to fit the imputer on df (should be False on val/test sets).

    Returns:
        Tuple of (cleaned_dataframe, fitted_imputer).
    """
    # 1. Schema check
    validate_schema(df)

    df_clean = df.copy()

    # 2. Parse Date
    if not pd.api.types.is_datetime64_any_dtype(df_clean["Date"]):
        df_clean["Date"] = pd.to_datetime(df_clean["Date"], format="%Y-%m-%d")

    # 3. Missing Weather becomes "Unknown"
    df_clean["Weather"] = df_clean["Weather"].fillna("Unknown")

    # 4. Handle missing Daily_Demand & censoring
    df_clean = handle_missing_demand_and_censoring(df_clean)

    # 5. Impute Shelf_Life_Days and Storage_Temperature using category medians
    if imputer is None:
        imputer = CategoryMedianImputer()
        if fit_imputer:
            df_clean = imputer.fit_transform(df_clean)
        else:
            raise ValueError("imputer is None but fit_imputer is False. Provide a fitted imputer.")
    else:
        if fit_imputer:
            df_clean = imputer.fit_transform(df_clean)
        else:
            df_clean = imputer.transform(df_clean)

    return df_clean, imputer


def get_time_splits(
    df: pd.DataFrame,
    train_end: str = "2025-10-31",
    val_end: str = "2025-11-30",
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, CategoryMedianImputer]:
    """Partition dataset into time-based splits (Train Jan-Oct, Val Nov, Test Dec)
    and clean each partition without data leakage.

    The CategoryMedianImputer is fitted strictly on the training partition.

    Returns:
        Tuple of (train_df, val_df, test_df, fitted_imputer).
    """
    df_raw = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_raw["Date"]):
        df_raw["Date"] = pd.to_datetime(df_raw["Date"], format="%Y-%m-%d")

    train_dt = pd.to_datetime(train_end)
    val_dt = pd.to_datetime(val_end)

    raw_train = df_raw[df_raw["Date"] <= train_dt].copy()
    raw_val = df_raw[(df_raw["Date"] > train_dt) & (df_raw["Date"] <= val_dt)].copy()
    raw_test = df_raw[df_raw["Date"] > val_dt].copy()

    # Fit imputer strictly on training set
    train_clean, imputer = clean_food_waste_data(raw_train, imputer=None, fit_imputer=True)
    val_clean, _ = clean_food_waste_data(raw_val, imputer=imputer, fit_imputer=False)
    test_clean, _ = clean_food_waste_data(raw_test, imputer=imputer, fit_imputer=False)

    return train_clean, val_clean, test_clean, imputer
