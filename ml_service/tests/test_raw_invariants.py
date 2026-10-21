"""Tests for invariant properties of the raw food waste dataset.

Invariants to test:
1. Remaining = Purchase - Sold
2. Waste <= Remaining
3. Sold <= Purchase
4. Sold = min(Purchase, Daily_Demand) where demand is present
5. donation only when waste > 0
"""

import csv
from pathlib import Path
import pytest

DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "food_waste_dataset.csv"
DATA_DICT_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "data_dictionary.csv"


@pytest.fixture(scope="module")
def raw_dataset():
    """Load raw dataset records as a list of dicts."""
    assert DATASET_PATH.exists(), f"Dataset file not found at {DATASET_PATH}"
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def test_dataset_shape_and_columns(raw_dataset):
    """Verify row count (8,000) and expected 16 columns."""
    assert len(raw_dataset) == 8000, f"Expected 8000 rows, got {len(raw_dataset)}"
    expected_cols = {
        "Inventory_ID", "Date", "Business_Type", "Food_Category",
        "Purchase_Quantity", "Units_Sold", "Remaining_Stock",
        "Shelf_Life_Days", "Storage_Temperature", "Daily_Demand",
        "Promotion", "Weather", "Waste_Quantity", "Waste_Reason",
        "Donation_Made", "Waste_Level"
    }
    assert set(raw_dataset[0].keys()) == expected_cols


def test_invariant_remaining_equals_purchase_minus_sold(raw_dataset):
    """Invariant 1: Remaining_Stock = Purchase_Quantity - Units_Sold for all rows."""
    violations = []
    for row in raw_dataset:
        purchase = int(row["Purchase_Quantity"])
        sold = int(row["Units_Sold"])
        remaining = int(row["Remaining_Stock"])
        if remaining != (purchase - sold):
            violations.append((row["Inventory_ID"], purchase, sold, remaining))
    assert not violations, f"Remaining != Purchase - Sold in {len(violations)} rows: {violations[:5]}"


def test_invariant_waste_less_equal_remaining(raw_dataset):
    """Invariant 2: Waste_Quantity <= Remaining_Stock for all rows."""
    violations = []
    for row in raw_dataset:
        remaining = int(row["Remaining_Stock"])
        waste = int(row["Waste_Quantity"])
        if waste > remaining:
            violations.append((row["Inventory_ID"], waste, remaining))
    assert not violations, f"Waste > Remaining in {len(violations)} rows: {violations[:5]}"


def test_invariant_sold_less_equal_purchase(raw_dataset):
    """Invariant 3: Units_Sold <= Purchase_Quantity for all rows."""
    violations = []
    for row in raw_dataset:
        purchase = int(row["Purchase_Quantity"])
        sold = int(row["Units_Sold"])
        if sold > purchase:
            violations.append((row["Inventory_ID"], sold, purchase))
    assert not violations, f"Sold > Purchase in {len(violations)} rows: {violations[:5]}"


def test_invariant_sold_equals_min_purchase_demand_when_present(raw_dataset):
    """Invariant 4: Sold = min(Purchase, Daily_Demand) whenever Daily_Demand is present."""
    violations = []
    evaluated = 0
    for row in raw_dataset:
        if row["Daily_Demand"].strip():
            evaluated += 1
            purchase = int(row["Purchase_Quantity"])
            sold = int(row["Units_Sold"])
            demand = int(float(row["Daily_Demand"]))
            expected_sold = min(purchase, demand)
            if sold != expected_sold:
                violations.append((row["Inventory_ID"], purchase, demand, sold, expected_sold))
    assert evaluated > 0, "No rows with Daily_Demand evaluated"
    assert not violations, f"Sold != min(Purchase, Demand) in {len(violations)} rows: {violations[:5]}"


def test_invariant_donation_only_when_waste_positive(raw_dataset):
    """Invariant 5: Donation_Made == 'Yes' can only occur when Waste_Quantity > 0."""
    violations = []
    for row in raw_dataset:
        waste = int(row["Waste_Quantity"])
        donation = row["Donation_Made"].strip()
        if donation == "Yes" and waste <= 0:
            violations.append((row["Inventory_ID"], waste, donation))
    assert not violations, f"Donation with waste <= 0 in {len(violations)} rows: {violations[:5]}"
