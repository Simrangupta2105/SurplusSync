"""Tests for TASK 1: CLEANING AND CENSORING RULES (data/food_waste.py).

Verifies:
1. Schema validation against data dictionary; loud failure on unexpected/missing columns or invalid values.
2. Date parsing to datetime format.
3. Missing Daily_Demand rules:
   - Case A: Units_Sold < Purchase_Quantity -> demand recovered as Units_Sold (147 rows).
   - Case B: Units_Sold == Purchase_Quantity -> demand_censored=True (63 rows).
4. Missing Weather becomes explicit 'Unknown' category.
5. Shelf_Life_Days and Storage_Temperature imputed with category medians + flags.
6. Imputation uses training data only (no data leakage).
7. Rule enforcement: Units_Sold must never be used as a demand target.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from ml_service.data.food_waste import (
    CategoryMedianImputer,
    SchemaValidationError,
    clean_food_waste_data,
    get_censoring_counts,
    get_time_splits,
    load_raw_data,
    validate_demand_target,
    validate_schema,
)

DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "food_waste_dataset.csv"


@pytest.fixture
def raw_df():
    """Load raw dataset as DataFrame."""
    return pd.read_csv(DATASET_PATH)


# --- 1. Schema Validation Tests ---

def test_schema_validation_passes_on_raw_data(raw_df):
    """Schema validation should pass cleanly on the raw food waste dataset."""
    validate_schema(raw_df)


def test_schema_validation_fails_on_missing_column(raw_df):
    """Schema validation must fail loudly when an expected column is missing."""
    df_missing = raw_df.drop(columns=["Purchase_Quantity"])
    with pytest.raises(SchemaValidationError, match="Missing expected columns"):
        validate_schema(df_missing)


def test_schema_validation_fails_on_unexpected_column(raw_df):
    """Schema validation must fail loudly when an unexpected extra column exists."""
    df_extra = raw_df.copy()
    df_extra["Arbitrary_Extra_Col"] = 123
    with pytest.raises(SchemaValidationError, match="Unexpected extra columns"):
        validate_schema(df_extra)


def test_schema_validation_fails_on_invalid_categorical_value(raw_df):
    """Schema validation must fail loudly if invalid categorical values appear."""
    df_invalid = raw_df.copy()
    df_invalid.loc[0, "Business_Type"] = "Boutique Hotel"
    with pytest.raises(SchemaValidationError, match="Column 'Business_Type' contains unexpected"):
        validate_schema(df_invalid)

    df_invalid2 = raw_df.copy()
    df_invalid2.loc[0, "Food_Category"] = "Seafood"
    with pytest.raises(SchemaValidationError, match="Column 'Food_Category' contains unexpected"):
        validate_schema(df_invalid2)


def test_schema_validation_fails_on_negative_quantities(raw_df):
    """Schema validation must fail loudly on negative quantities."""
    df_neg = raw_df.copy()
    df_neg.loc[0, "Units_Sold"] = -5
    with pytest.raises(SchemaValidationError, match="contains negative values"):
        validate_schema(df_neg)


# --- 2. Date Parsing Tests ---

def test_load_raw_data_parses_dates():
    """load_raw_data should parse Date into datetime64[ns]."""
    df = load_raw_data(DATASET_PATH)
    assert pd.api.types.is_datetime64_any_dtype(df["Date"])
    assert df["Date"].min() == pd.Timestamp("2025-01-01")
    assert df["Date"].max() == pd.Timestamp("2025-12-31")
    assert df["Date"].nunique() == 365


# --- 3. Missing Daily_Demand & Censoring Rules ---

def test_missing_demand_censoring_breakdown_counts(raw_df):
    """Verify exact counts of missing demand recovery and censoring.

    Total missing Daily_Demand: 210 rows
    Case A (Units_Sold < Purchase_Quantity, Recovered): 147 rows
    Case B (Units_Sold == Purchase_Quantity, Censored): 63 rows
    """
    counts = get_censoring_counts(raw_df)
    assert counts["total_rows"] == 8000
    assert counts["missing_demand_total"] == 210
    assert counts["case_a_recovered"] == 147
    assert counts["case_b_censored"] == 63
    assert counts["initially_present_demand"] == 7790


def test_clean_data_recovers_case_a_demand(raw_df):
    """Case A: When Daily_Demand is missing and Units_Sold < Purchase_Quantity,
    demand equals Units_Sold (recovered, demand_recovered=True, demand_censored=False).
    """
    cleaned_df, _ = clean_food_waste_data(raw_df)

    # Check recovered rows
    recovered = cleaned_df[cleaned_df["demand_recovered"]]
    assert len(recovered) == 147
    # For every recovered row, Daily_Demand must equal Units_Sold
    assert (recovered["Daily_Demand"] == recovered["Units_Sold"]).all()
    assert (~recovered["demand_censored"]).all()


def test_clean_data_censors_case_b_demand(raw_df):
    """Case B: When Daily_Demand is missing and Units_Sold == Purchase_Quantity,
    demand is censored (demand_censored=True, demand_recovered=False).
    """
    cleaned_df, _ = clean_food_waste_data(raw_df)

    censored = cleaned_df[cleaned_df["demand_censored"]]
    assert len(censored) == 63
    # For censored rows, stock sold out completely
    assert (censored["Units_Sold"] == censored["Purchase_Quantity"]).all()
    assert (~censored["demand_recovered"]).all()
    assert censored["stockout_flag"].all()


def test_non_missing_demand_rows_remain_uncensored(raw_df):
    """Rows with non-missing Daily_Demand should not be flagged as demand_censored or demand_recovered."""
    cleaned_df, _ = clean_food_waste_data(raw_df)

    initial_known_mask = raw_df["Daily_Demand"].notna()
    known_subset = cleaned_df[initial_known_mask]
    assert (~known_subset["demand_censored"]).all()
    assert (~known_subset["demand_recovered"]).all()


# --- 4. Weather Imputation Tests ---

def test_missing_weather_becomes_unknown(raw_df):
    """Missing Weather values must become 'Unknown' (explicit category)."""
    missing_weather_count = int(raw_df["Weather"].isna().sum())
    assert missing_weather_count == 203

    cleaned_df, _ = clean_food_waste_data(raw_df)
    assert cleaned_df["Weather"].isna().sum() == 0
    assert (cleaned_df["Weather"] == "Unknown").sum() == 203


# --- 5. Category Median Imputation & Leakage Prevention ---

def test_category_median_imputation_and_flags(raw_df):
    """Missing Shelf_Life_Days and Storage_Temperature are imputed with category medians and flagged."""
    cleaned_df, imputer = clean_food_waste_data(raw_df)

    # Imputed flag columns exist and match original null count
    assert "Shelf_Life_Days_imputed" in cleaned_df.columns
    assert "Storage_Temperature_imputed" in cleaned_df.columns

    assert cleaned_df["Shelf_Life_Days_imputed"].sum() == 235
    assert cleaned_df["Storage_Temperature_imputed"].sum() == 186

    # No nulls remain in either column
    assert cleaned_df["Shelf_Life_Days"].isna().sum() == 0
    assert cleaned_df["Storage_Temperature"].isna().sum() == 0

    # Verify fitted medians match category medians
    expected_shelf_medians = {
        "Bakery": 3.0, "Dairy": 7.0, "Fruits": 5.0,
        "Meat": 4.0, "Prepared Food": 1.0, "Vegetables": 6.0
    }
    for cat, expected_val in expected_shelf_medians.items():
        assert imputer.shelf_life_medians_[cat] == expected_val


def test_no_data_leakage_in_time_splits(raw_df):
    """Imputation parameters must be computed strictly on training set (Jan-Oct)."""
    train_df, val_df, test_df, imputer = get_time_splits(raw_df, train_end="2025-10-31", val_end="2025-11-30")

    # Time partition sizes
    assert len(train_df) + len(val_df) + len(test_df) == 8000
    assert train_df["Date"].max() <= pd.Timestamp("2025-10-31")
    assert val_df["Date"].min() >= pd.Timestamp("2025-11-01")
    assert val_df["Date"].max() <= pd.Timestamp("2025-11-30")
    assert test_df["Date"].min() >= pd.Timestamp("2025-12-01")

    # Imputer was fitted on train_df
    # Let's verify test set missing values are filled with train_df medians
    test_missing_shelf = test_df[test_df["Shelf_Life_Days_imputed"]]
    if not test_missing_shelf.empty:
        sample_row = test_missing_shelf.iloc[0]
        cat = sample_row["Food_Category"]
        assert sample_row["Shelf_Life_Days"] == imputer.shelf_life_medians_[cat]


# --- 6. Never Use Units_Sold as Demand Target Rule ---

def test_never_use_units_sold_as_demand_target():
    """Rule: validate_demand_target must raise ValueError if 'Units_Sold' is used."""
    with pytest.raises(ValueError, match="CRITICAL RULE VIOLATION: 'Units_Sold' must never be used"):
        validate_demand_target("Units_Sold")

    with pytest.raises(ValueError, match="CRITICAL RULE VIOLATION"):
        validate_demand_target("units_sold")

    with pytest.raises(ValueError, match="CRITICAL RULE VIOLATION"):
        validate_demand_target(" UNITS_SOLD ")

    # Valid demand target passes without error
    validate_demand_target("Daily_Demand")
