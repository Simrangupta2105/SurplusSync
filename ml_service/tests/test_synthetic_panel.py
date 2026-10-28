"""Tests for synthetic panel loader, schema validation, and invariant enforcement.

Covers Task 0 requirements:
- Dual schema support: accepts both core 16-column and full 33-column schema.
- Rejection of unexpected extra columns and missing required columns.
- Rejection of 'Units_Sold' as a demand target.
- Parsing of Date and Expiry_Date.
- Handling of blank Festival as 'no festival'.
- Verification of accounting, logic, and temporal invariants across all 52,608 rows:
    1. Remaining = Purchase - Sold
    2. Sold = min(Purchase, Demand)
    3. Waste <= Remaining
    4. Donated_Units <= Waste_Quantity
    5. Donation_Made = Yes only when waste > 0
    6. Carried_Forward = Remaining - Waste
    7. Expiry_Date = Date + Shelf_Life_Days
    8. Exactly one row per (Date, Shop_ID, Food_Category) and no missing days (48 series x 1,096 days).
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

try:
    from ml_service.data.synthetic_panel import (
        DEFAULT_SYNTHETIC_FULL_PATH,
        DEFAULT_SYNTHETIC_CORE16_PATH,
        DEFAULT_SYNTHETIC_DICT_PATH,
        DEFAULT_SYNTHETIC_SEQ_PATH,
        CORE16_COLUMNS,
        FULL33_COLUMNS,
        SchemaValidationError,
        InvariantViolationError,
        load_allow_list,
        load_synthetic_panel,
        validate_demand_target,
        validate_invariants,
        validate_schema,
    )
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from data.synthetic_panel import (
        DEFAULT_SYNTHETIC_FULL_PATH,
        DEFAULT_SYNTHETIC_CORE16_PATH,
        DEFAULT_SYNTHETIC_DICT_PATH,
        DEFAULT_SYNTHETIC_SEQ_PATH,
        CORE16_COLUMNS,
        FULL33_COLUMNS,
        SchemaValidationError,
        InvariantViolationError,
        load_allow_list,
        load_synthetic_panel,
        validate_demand_target,
        validate_invariants,
        validate_schema,
    )


@pytest.fixture(scope="module")
def sequence_panel() -> pd.DataFrame:
    """Load and validate the 33-column synthetic sequence panel (synthetic_seq_v2)."""
    assert DEFAULT_SYNTHETIC_SEQ_PATH.exists(), f"Sequence dataset missing: {DEFAULT_SYNTHETIC_SEQ_PATH}"
    return load_synthetic_panel(DEFAULT_SYNTHETIC_SEQ_PATH)


@pytest.fixture(scope="module")
def full_panel() -> pd.DataFrame:
    """Load and validate the full 33-column synthetic panel."""
    assert DEFAULT_SYNTHETIC_FULL_PATH.exists(), f"Full dataset missing: {DEFAULT_SYNTHETIC_FULL_PATH}"
    return load_synthetic_panel(DEFAULT_SYNTHETIC_FULL_PATH)


@pytest.fixture(scope="module")
def core16_panel() -> pd.DataFrame:
    """Load and validate the 16-column core synthetic panel."""
    assert DEFAULT_SYNTHETIC_CORE16_PATH.exists(), f"Core dataset missing: {DEFAULT_SYNTHETIC_CORE16_PATH}"
    return load_synthetic_panel(DEFAULT_SYNTHETIC_CORE16_PATH)


# --- 1. Schema & Allow-List Tests ---

def test_allow_list_matches_data_dictionary():
    """Verify allow-lists match data_dictionary_synthetic.csv."""
    core_cols, full_cols = load_allow_list(DEFAULT_SYNTHETIC_DICT_PATH)
    assert len(core_cols) == 16, f"Expected 16 core columns, got {len(core_cols)}"
    assert len(full_cols) == 33, f"Expected 33 full columns, got {len(full_cols)}"
    assert set(core_cols).issubset(set(full_cols))


def test_full_panel_shape_and_columns(full_panel):
    """Verify full synthetic panel has exactly 52,608 rows and 33 columns."""
    assert len(full_panel) == 52608, f"Expected 52608 rows, got {len(full_panel)}"
    assert full_panel.shape[1] == 33, f"Expected 33 columns, got {full_panel.shape[1]}"
    assert list(full_panel.columns) == FULL33_COLUMNS


def test_core16_panel_shape_and_columns(core16_panel):
    """Verify core16 synthetic panel has exactly 52,608 rows and 16 columns."""
    assert len(core16_panel) == 52608, f"Expected 52608 rows, got {len(core16_panel)}"
    assert core16_panel.shape[1] == 16, f"Expected 16 columns, got {core16_panel.shape[1]}"
    assert list(core16_panel.columns) == CORE16_COLUMNS


def test_schema_rejects_unexpected_column(full_panel):
    """Verify validate_schema fails loudly on unexpected extra columns."""
    bad_df = full_panel.copy()
    bad_df["leakage_feature_xyz"] = 123
    with pytest.raises(SchemaValidationError, match="Unexpected extra columns detected"):
        validate_schema(bad_df)


def test_schema_rejects_missing_column(full_panel):
    """Verify validate_schema fails loudly on missing required columns."""
    bad_df = full_panel.drop(columns=["Daily_Demand"])
    with pytest.raises(SchemaValidationError, match="Missing"):
        validate_schema(bad_df)


def test_schema_rejects_invalid_categorical(full_panel):
    """Verify validate_schema fails on invalid categorical levels."""
    bad_df = full_panel.copy()
    bad_df.iloc[0, bad_df.columns.get_loc("Business_Type")] = "FoodTruck"
    with pytest.raises(SchemaValidationError, match="Invalid values in categorical column"):
        validate_schema(bad_df)


def test_validate_demand_target_rejects_units_sold():
    """Verify critical rule: Units_Sold must never be used as a demand target."""
    with pytest.raises(ValueError, match="CRITICAL INVARIANT VIOLATION"):
        validate_demand_target("Units_Sold")
    with pytest.raises(ValueError, match="CRITICAL INVARIANT VIOLATION"):
        validate_demand_target("units_sold")
    with pytest.raises(ValueError, match="CRITICAL INVARIANT VIOLATION"):
        validate_demand_target("  UNITS_SOLD  ")

    # Allowed targets should pass without exception
    validate_demand_target("Daily_Demand")
    validate_demand_target("Waste_Level")


# --- 2. Invariant Tests on Full Panel ---

def test_invariant_remaining_equals_purchase_minus_sold(full_panel):
    """Invariant 1: Remaining_Stock == Purchase_Quantity - Units_Sold on every row."""
    assert (full_panel["Remaining_Stock"] == full_panel["Purchase_Quantity"] - full_panel["Units_Sold"]).all()


def test_invariant_sold_equals_min_purchase_and_demand(full_panel):
    """Invariant 2: Units_Sold == min(Purchase_Quantity, Daily_Demand) on every row."""
    expected_sold = np.minimum(full_panel["Purchase_Quantity"], full_panel["Daily_Demand"])
    assert (full_panel["Units_Sold"] == expected_sold).all()


def test_invariant_waste_less_or_equal_remaining(full_panel):
    """Invariant 3: Waste_Quantity <= Remaining_Stock on every row."""
    assert (full_panel["Waste_Quantity"] <= full_panel["Remaining_Stock"]).all()


def test_invariant_donated_less_or_equal_waste(full_panel):
    """Invariant 4: Donated_Units <= Waste_Quantity on every row."""
    assert (full_panel["Donated_Units"] <= full_panel["Waste_Quantity"]).all()


def test_invariant_donation_made_only_when_waste_positive(full_panel):
    """Invariant 5: Donation_Made == 'Yes' only when Waste_Quantity > 0."""
    donated_rows = full_panel[full_panel["Donation_Made"] == "Yes"]
    assert (donated_rows["Waste_Quantity"] > 0).all()
    # When waste is 0, Donation_Made must be 'No'
    zero_waste_rows = full_panel[full_panel["Waste_Quantity"] == 0]
    assert (zero_waste_rows["Donation_Made"] == "No").all()


def test_invariant_carried_forward_equals_remaining_minus_waste(full_panel):
    """Invariant 6: Carried_Forward_Units == Remaining_Stock - Waste_Quantity on every row."""
    expected_cf = full_panel["Remaining_Stock"] - full_panel["Waste_Quantity"]
    assert (full_panel["Carried_Forward_Units"] == expected_cf).all()


def test_invariant_expiry_date_equals_date_plus_shelf_life(full_panel):
    """Invariant 7: Expiry_Date == Date + Shelf_Life_Days on every row."""
    diff_days = (full_panel["Expiry_Date"] - full_panel["Date"]).dt.days
    assert (diff_days == full_panel["Shelf_Life_Days"]).all()


def test_invariant_no_duplicate_series_days(full_panel):
    """Invariant 8a: Exactly one row per (Date, Shop_ID, Food_Category)."""
    assert full_panel.duplicated(["Date", "Shop_ID", "Food_Category"]).sum() == 0


def test_invariant_no_missing_days_in_any_series(full_panel):
    """Invariant 8b: Exactly 48 series (8 shops x 6 categories), 1096 days each, no gaps."""
    series_groups = full_panel.groupby(["Shop_ID", "Food_Category"])
    assert series_groups.ngroups == 48, f"Expected 48 series, got {series_groups.ngroups}"

    total_unique_days = full_panel["Date"].nunique()
    assert total_unique_days == 1096, f"Expected 1096 days (2023-01-01 to 2025-12-31), got {total_unique_days}"

    for (shop_id, food_cat), g in series_groups:
        assert len(g) == 1096, f"Series ({shop_id}, {food_cat}) has {len(g)} rows, expected 1096."
        assert g["Date"].nunique() == 1096, f"Series ({shop_id}, {food_cat}) has missing calendar days."


# --- 3. Invariants on Core 16 Panel ---

def test_core16_panel_invariants(core16_panel):
    """Verify applicable invariants on core16 schema."""
    inv_results = validate_invariants(core16_panel)
    assert inv_results["Remaining = Purchase - Sold"] is True
    assert inv_results["Sold = min(Purchase, Demand)"] is True
    assert inv_results["Waste <= Remaining"] is True
    assert inv_results["Donation_Made = Yes only when waste > 0"] is True


# --- 4. Date Parsing and Festival Handling ---

def test_date_parsing_and_festival_handling(full_panel):
    """Verify Date is parsed to datetime and blank Festival is 'no festival'."""
    assert pd.api.types.is_datetime64_any_dtype(full_panel["Date"])
    assert pd.api.types.is_datetime64_any_dtype(full_panel["Expiry_Date"])

    assert not (full_panel["Festival"] == "").any()
    assert not full_panel["Festival"].isna().any()
    assert "no festival" in full_panel["Festival"].values


# --- 5. Rejection of Broken Invariants ---

def test_validate_invariants_raises_on_remaining_error(full_panel):
    """Verify validate_invariants raises when Remaining != Purchase - Sold."""
    bad_df = full_panel.head(50).copy()
    bad_df.iloc[0, bad_df.columns.get_loc("Remaining_Stock")] += 10
    with pytest.raises(InvariantViolationError, match="Remaining = Purchase - Sold"):
        validate_invariants(bad_df)


def test_validate_invariants_raises_on_sold_error(full_panel):
    """Verify validate_invariants raises when Sold != min(Purchase, Demand)."""
    bad_df = full_panel.head(50).copy()
    bad_df.iloc[0, bad_df.columns.get_loc("Units_Sold")] += 5
    bad_df.iloc[0, bad_df.columns.get_loc("Remaining_Stock")] -= 5
    with pytest.raises(InvariantViolationError, match="Sold = min\\(Purchase, Demand\\)"):
        validate_invariants(bad_df)


def test_validate_invariants_raises_on_waste_exceeding_remaining(full_panel):
    """Verify validate_invariants raises when Waste > Remaining."""
    bad_df = full_panel.head(50).copy()
    bad_df.iloc[0, bad_df.columns.get_loc("Waste_Quantity")] = bad_df.iloc[0]["Remaining_Stock"] + 1
    with pytest.raises(InvariantViolationError, match="Waste <= Remaining"):
        validate_invariants(bad_df)


def test_validate_invariants_raises_on_donated_exceeding_waste(full_panel):
    """Verify validate_invariants raises when Donated_Units > Waste_Quantity."""
    bad_df = full_panel.head(50).copy()
    bad_df.iloc[0, bad_df.columns.get_loc("Donated_Units")] = bad_df.iloc[0]["Waste_Quantity"] + 5
    with pytest.raises(InvariantViolationError, match="Donated_Units <= Waste_Quantity"):
        validate_invariants(bad_df)


# --- Sequence Panel (synthetic_seq_v2) Tests ---

def test_sequence_panel_shape_columns_and_invariants(sequence_panel):
    """Verify synthetic sequence panel has 78,912 rows (72 series x 1,096 days) and passes invariants."""
    assert len(sequence_panel) == 78912, f"Expected 78912 rows, got {len(sequence_panel)}"
    assert sequence_panel.shape[1] == 33, f"Expected 33 columns, got {sequence_panel.shape[1]}"
    assert list(sequence_panel.columns) == FULL33_COLUMNS
    assert sequence_panel["Data_Origin"].unique().tolist() == ["synthetic_seq_v2"]
    assert sequence_panel.groupby(["Shop_ID", "Food_Category"]).ngroups == 72
    assert sequence_panel["Date"].nunique() == 1096
    assert sequence_panel["Shop_ID"].nunique() == 12

    # Verify all invariants hold
    results = validate_invariants(sequence_panel)
    assert all(results.values()), f"Some invariants failed: {results}"

