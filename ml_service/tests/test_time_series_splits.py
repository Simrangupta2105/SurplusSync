"""Unit tests for TASK 1: SERIES AND SPLITS (Time-series Track B).

Verifies:
1. Daily series construction per (Shop_ID, Food_Category) [48 series, 1,096 days each].
2. Aggregated series per (Business_Type, Food_Category) [24 series] and per Food_Category [6 series].
3. Rejection of Units_Sold as demand target.
4. Detection and rejection of data leakage columns.
5. Isolation of final untouched 90-day test set (2025-10-03 to 2025-12-31).
6. Rolling-origin cross-validation splitter (at least 4 folds, 7-day and 28-day horizons, strict temporal order).
7. Feature pipeline fitting strictly on training data without future snooping.
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

# Ensure parent path is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
PARENT_DIR = BASE_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

try:
    from ml_service.data.synthetic_panel import DEFAULT_SYNTHETIC_SEQ_PATH, load_synthetic_panel
    from ml_service.data.time_series_splits import (
        FINAL_TEST_DAYS,
        KNOWN_COVARIATES,
        LEAKAGE_COLUMNS,
        TARGET_COLUMN,
        TEST_CUTOFF_DATE,
        CVFold,
        LeakageError,
        RollingOriginSplitter,
        TemporalOrderViolationError,
        TimeSeriesFeaturePipeline,
        build_business_type_category_series,
        build_category_aggregate_series,
        build_shop_category_series,
        get_target_and_covariates,
        split_train_test,
        verify_no_leakage,
    )
except ModuleNotFoundError:
    from data.synthetic_panel import DEFAULT_SYNTHETIC_SEQ_PATH, load_synthetic_panel
    from data.time_series_splits import (
        FINAL_TEST_DAYS,
        KNOWN_COVARIATES,
        LEAKAGE_COLUMNS,
        TARGET_COLUMN,
        TEST_CUTOFF_DATE,
        CVFold,
        LeakageError,
        RollingOriginSplitter,
        TemporalOrderViolationError,
        TimeSeriesFeaturePipeline,
        build_business_type_category_series,
        build_category_aggregate_series,
        build_shop_category_series,
        get_target_and_covariates,
        split_train_test,
        verify_no_leakage,
    )


@pytest.fixture(scope="module")
def panel_df() -> pd.DataFrame:
    """Load cleaned full synthetic panel DataFrame (v1, 48 series)."""
    return load_synthetic_panel()


@pytest.fixture(scope="module")
def sequence_panel_df() -> pd.DataFrame:
    """Load cleaned full synthetic sequence panel DataFrame (v2, 72 series)."""
    assert DEFAULT_SYNTHETIC_SEQ_PATH.exists(), f"Sequence dataset missing: {DEFAULT_SYNTHETIC_SEQ_PATH}"
    return load_synthetic_panel(DEFAULT_SYNTHETIC_SEQ_PATH)



# --- 1. Series Construction Tests ---

def test_build_shop_category_series_count_and_length(panel_df: pd.DataFrame):
    """Verify exactly 48 series are built, each having exactly 1,096 consecutive days."""
    series_dict = build_shop_category_series(panel_df)
    assert len(series_dict) == 48, f"Expected 48 series, got {len(series_dict)}"

    expected_shops = {f"S0{i}" for i in range(1, 9)}
    expected_categories = {"Bakery", "Dairy", "Fruits", "Meat", "Prepared Food", "Vegetables"}

    actual_shops = {s for s, c in series_dict.keys()}
    actual_categories = {c for s, c in series_dict.keys()}

    assert actual_shops == expected_shops
    assert actual_categories == expected_categories

    for (shop_id, cat), s_df in series_dict.items():
        assert len(s_df) == 1096, f"Series ({shop_id}, {cat}) has {len(s_df)} days, expected 1096"
        assert s_df["Date"].min() == pd.Timestamp("2023-01-01")
        assert s_df["Date"].max() == pd.Timestamp("2025-12-31")
        assert s_df["Date"].nunique() == 1096
        assert TARGET_COLUMN in s_df.columns
        # Target must be non-negative
        assert (s_df[TARGET_COLUMN] >= 0).all()
        # Verify leakage columns are removed
        for col in LEAKAGE_COLUMNS:
            assert col not in s_df.columns


def test_build_business_type_category_series_aggregation(panel_df: pd.DataFrame):
    """Verify exactly 24 series are built for (Business_Type, Food_Category) with summed demand."""
    bt_series = build_business_type_category_series(panel_df)
    assert len(bt_series) == 24, f"Expected 24 series, got {len(bt_series)}"

    expected_btypes = {"Restaurant", "Supermarket", "Cafeteria", "Cloud Kitchen"}
    actual_btypes = {bt for bt, cat in bt_series.keys()}
    assert actual_btypes == expected_btypes

    # Hand-verify demand sum on a single slice
    restaurant_bakery = bt_series[("Restaurant", "Bakery")]
    assert len(restaurant_bakery) == 1096

    # Verify demand on 2023-01-01 matches raw panel sum for Restaurant Bakery
    test_date = pd.Timestamp("2023-01-01")
    raw_slice = panel_df[
        (panel_df["Business_Type"] == "Restaurant")
        & (panel_df["Food_Category"] == "Bakery")
        & (panel_df["Date"] == test_date)
    ]
    raw_demand_sum = raw_slice["Daily_Demand"].sum()
    agg_demand = restaurant_bakery.loc[test_date, "Daily_Demand"]
    assert agg_demand == raw_demand_sum


def test_build_category_aggregate_series_network(panel_df: pd.DataFrame):
    """Verify exactly 6 network-wide category aggregate series, summing across all 8 shops."""
    cat_series = build_category_aggregate_series(panel_df)
    assert len(cat_series) == 6

    expected_categories = {"Bakery", "Dairy", "Fruits", "Meat", "Prepared Food", "Vegetables"}
    assert set(cat_series.keys()) == expected_categories

    dairy_series = cat_series["Dairy"]
    assert len(dairy_series) == 1096

    test_date = pd.Timestamp("2024-05-15")
    raw_dairy_sum = panel_df[
        (panel_df["Food_Category"] == "Dairy")
        & (panel_df["Date"] == test_date)
    ]["Daily_Demand"].sum()
    assert dairy_series.loc[test_date, "Daily_Demand"] == raw_dairy_sum


# --- 2. Invariant and Leakage Tests ---

def test_reject_units_sold_as_demand_target(panel_df: pd.DataFrame):
    """Verify that using Units_Sold as a demand target raises ValueError immediately."""
    with pytest.raises(ValueError, match="CRITICAL INVARIANT VIOLATION"):
        build_shop_category_series(panel_df, target_col="Units_Sold")

    with pytest.raises(ValueError, match="CRITICAL INVARIANT VIOLATION"):
        build_business_type_category_series(panel_df, target_col="Units_Sold")

    with pytest.raises(ValueError, match="CRITICAL INVARIANT VIOLATION"):
        build_category_aggregate_series(panel_df, target_col="Units_Sold")

    with pytest.raises(ValueError, match="CRITICAL INVARIANT VIOLATION"):
        get_target_and_covariates(panel_df, target_col="Units_Sold")


def test_leakage_columns_detection():
    """Verify that verify_no_leakage detects any outcome/accounting columns."""
    for leak_col in LEAKAGE_COLUMNS:
        with pytest.raises(LeakageError, match="DATA LEAKAGE DETECTED"):
            verify_no_leakage(["Promotion", "Temperature_C", leak_col])

    # Clean covariates pass without error
    verify_no_leakage(["Promotion", "Temperature_C", "Rain_mm", "Day_Of_Week"])


def test_get_target_and_covariates_drops_leakage(panel_df: pd.DataFrame):
    """Verify get_target_and_covariates isolates y and clean X without leakage."""
    y, X = get_target_and_covariates(panel_df, target_col="Daily_Demand", drop_leakage=True)
    assert len(y) == len(panel_df)
    assert len(X) == len(panel_df)
    assert "Daily_Demand" not in X.columns

    for leak_col in LEAKAGE_COLUMNS:
        assert leak_col not in X.columns


# --- 3. Final Untouched Test Set Splitting Tests ---

def test_split_train_test_untouched_final_90_days(panel_df: pd.DataFrame):
    """Verify the final 90 calendar days are isolated with strict temporal separation."""
    train_pool_df, test_df = split_train_test(
        panel_df,
        test_cutoff=TEST_CUTOFF_DATE,
        test_days=FINAL_TEST_DAYS,
    )

    train_dates = pd.to_datetime(train_pool_df["Date"])
    test_dates = pd.to_datetime(test_df["Date"])

    # 1. Date counts
    assert train_dates.nunique() == 1006
    assert test_dates.nunique() == 90
    assert len(train_dates.unique()) + len(test_dates.unique()) == 1096

    # 2. Strict temporal ordering: max(train) < min(test)
    assert train_dates.max() == pd.Timestamp("2025-10-02")
    assert test_dates.min() == pd.Timestamp("2025-10-03")
    assert test_dates.max() == pd.Timestamp("2025-12-31")
    assert train_dates.max() < test_dates.min()

    # 3. Disjoint date sets
    overlap = set(train_dates.unique()).intersection(set(test_dates.unique()))
    assert len(overlap) == 0

    # 4. Total rows check (48 series * 90 days = 4,320 test rows)
    assert len(test_df) == 48 * 90
    assert len(train_pool_df) == 48 * 1006


def test_split_train_test_temporal_violation_error():
    """Verify that an invalid cutoff raises TemporalOrderViolationError."""
    df_mini = pd.DataFrame({
        "Date": pd.date_range("2025-01-01", periods=10),
        "Daily_Demand": range(10),
    })
    # Cutoff after all data
    with pytest.raises(TemporalOrderViolationError):
        split_train_test(df_mini, test_cutoff="2025-02-01", test_days=5)


# --- 4. Rolling-Origin Cross-Validation Splitter Tests ---

def test_rolling_origin_splitter_7day_horizon(panel_df: pd.DataFrame):
    """Verify 4 rolling folds with 7-day horizon on pre-cutoff data."""
    dates = pd.to_datetime(panel_df["Date"].drop_duplicates().sort_values())
    splitter = RollingOriginSplitter(n_splits=4, horizon=7, step=28, test_cutoff=TEST_CUTOFF_DATE)
    folds = splitter.get_folds(dates)

    assert len(folds) == 4
    cutoff_ts = pd.Timestamp(TEST_CUTOFF_DATE)

    for i, fold in enumerate(folds):
        assert fold.fold_idx == i
        assert fold.horizon == 7
        assert len(fold.val_dates) == 7
        assert fold.train_end < fold.val_start
        assert fold.val_end < cutoff_ts
        assert set(fold.train_dates).isdisjoint(set(fold.val_dates))
        assert fold.train_start == pd.Timestamp("2023-01-01")

    # Last fold (Fold 3) validation must end on the day immediately preceding test cutoff
    last_fold = folds[-1]
    assert last_fold.val_end == pd.Timestamp("2025-10-02")
    assert last_fold.val_start == pd.Timestamp("2025-09-26")


def test_rolling_origin_splitter_28day_horizon(panel_df: pd.DataFrame):
    """Verify 4 rolling folds with 28-day horizon on pre-cutoff data."""
    dates = pd.to_datetime(panel_df["Date"].drop_duplicates().sort_values())
    splitter = RollingOriginSplitter(n_splits=4, horizon=28, step=28, test_cutoff=TEST_CUTOFF_DATE)
    folds = splitter.get_folds(dates)

    assert len(folds) == 4
    cutoff_ts = pd.Timestamp(TEST_CUTOFF_DATE)

    for i, fold in enumerate(folds):
        assert fold.fold_idx == i
        assert fold.horizon == 28
        assert len(fold.val_dates) == 28
        assert fold.train_end < fold.val_start
        assert fold.val_end < cutoff_ts
        assert set(fold.train_dates).isdisjoint(set(fold.val_dates))

    last_fold = folds[-1]
    assert last_fold.val_end == pd.Timestamp("2025-10-02")
    assert last_fold.val_start == pd.Timestamp("2025-09-05")


def test_rolling_origin_split_series_generator(panel_df: pd.DataFrame):
    """Verify split_series generator splits a single series correctly."""
    series_dict = build_shop_category_series(panel_df)
    s_df = series_dict[("S01", "Bakery")]

    splitter = RollingOriginSplitter(n_splits=4, horizon=7, step=28)
    splits = list(splitter.split_series(s_df))

    assert len(splits) == 4
    for train_df, val_df, fold in splits:
        assert len(val_df) == 7
        assert len(train_df) > 900
        assert train_df["Date"].max() < val_df["Date"].min()
        assert val_df["Date"].max() < pd.Timestamp(TEST_CUTOFF_DATE)


def test_rolling_origin_split_panel_generator(panel_df: pd.DataFrame):
    """Verify split_panel generator produces synchronized slices across all 48 series."""
    splitter = RollingOriginSplitter(n_splits=4, horizon=7, step=28)
    splits = list(splitter.split_panel(panel_df))

    assert len(splits) == 4
    for train_panel, val_panel, fold in splits:
        # 48 series * 7 days = 336 rows in validation
        assert len(val_panel) == 48 * 7
        assert val_panel["Shop_ID"].nunique() == 8
        assert val_panel["Food_Category"].nunique() == 6
        assert val_panel["Date"].max() < pd.Timestamp(TEST_CUTOFF_DATE)


# --- 5. Feature Pipeline Preprocessing Tests ---

def test_time_series_feature_pipeline_fit_and_transform(panel_df: pd.DataFrame):
    """Verify feature pipeline fits strictly on training split and transforms val/test."""
    train_pool_df, test_df = split_train_test(panel_df)

    splitter = RollingOriginSplitter(n_splits=4, horizon=7, step=28)
    train_df, val_df, fold = next(splitter.split_panel(train_pool_df))

    _, X_train = get_target_and_covariates(train_df, target_col="Daily_Demand")
    _, X_val = get_target_and_covariates(val_df, target_col="Daily_Demand")
    _, X_test = get_target_and_covariates(test_df, target_col="Daily_Demand")

    pipeline = TimeSeriesFeaturePipeline()
    pipeline.fit(X_train)

    X_train_trans = pipeline.transform(X_train)
    X_val_trans = pipeline.transform(X_val)
    X_test_trans = pipeline.transform(X_test)

    # 1. Output shapes
    assert len(X_train_trans) == len(X_train)
    assert len(X_val_trans) == len(X_val)
    assert len(X_test_trans) == len(X_test)
    assert X_train_trans.shape[1] == X_val_trans.shape[1] == X_test_trans.shape[1]

    # 2. No NaNs in transformed output
    assert X_train_trans.isna().sum().sum() == 0
    assert X_val_trans.isna().sum().sum() == 0
    assert X_test_trans.isna().sum().sum() == 0

    # 3. Scaler was fitted strictly on X_train (Temperature_C mean in train ~ 0)
    temp_train_mean = X_train_trans["Temperature_C"].mean()
    assert abs(temp_train_mean) < 1e-6


def test_feature_pipeline_rejects_leakage_columns(panel_df: pd.DataFrame):
    """Verify feature pipeline raises LeakageError if any leakage column is in features."""
    pipeline = TimeSeriesFeaturePipeline()

    bad_X = panel_df[["Temperature_C", "Promotion", "Units_Sold"]].copy()
    with pytest.raises(LeakageError, match="DATA LEAKAGE DETECTED"):
        pipeline.fit(bad_X)

    good_X = panel_df[["Temperature_C", "Promotion", "Rain_mm"]].copy()
    pipeline.fit(good_X)

    bad_val = panel_df[["Temperature_C", "Promotion", "Remaining_Stock"]].copy()
    with pytest.raises(LeakageError, match="DATA LEAKAGE DETECTED"):
        pipeline.transform(bad_val)


def test_feature_pipeline_unseen_categories_gracefully_encoded():
    """Verify that unseen categorical levels in validation or test do not crash."""
    train_data = pd.DataFrame({
        "Temperature_C": [20.0, 25.0, 30.0],
        "Promotion": ["Yes", "No", "Yes"],
        "Weather": ["Sunny", "Rainy", "Sunny"],
        "Day_Of_Week": [1, 2, 3],
        "Is_Weekend": [0, 0, 0],
        "Is_Holiday": [0, 0, 0],
    })

    test_data_with_unseen = pd.DataFrame({
        "Temperature_C": [22.0, 28.0],
        "Promotion": ["Yes", "UnknownPromo"],  # Unseen category
        "Weather": ["Snowy", "Rainy"],         # Unseen category
        "Day_Of_Week": [4, 5],
        "Is_Weekend": [0, 0],
        "Is_Holiday": [0, 0],
    })

    pipeline = TimeSeriesFeaturePipeline(
        numerical_cols=["Temperature_C"],
        categorical_cols=["Promotion", "Weather"],
        calendar_cols=["Day_Of_Week", "Is_Weekend", "Is_Holiday"],
    )

    pipeline.fit(train_data)
    transformed = pipeline.transform(test_data_with_unseen)

    assert len(transformed) == 2
    assert transformed.isna().sum().sum() == 0


# --- 5. Task 1 Sequence Panel Tests (72 Series, Horizons 1 and 7) ---

def test_sequence_panel_split_train_test_isolation(sequence_panel_df: pd.DataFrame):
    """Verify that for 72 series, final 90 days are strictly isolated with zero leakage into training."""
    train_pool_df, test_df = split_train_test(
        sequence_panel_df,
        test_cutoff=TEST_CUTOFF_DATE,
        test_days=FINAL_TEST_DAYS,
    )

    train_dates = pd.to_datetime(train_pool_df["Date"])
    test_dates = pd.to_datetime(test_df["Date"])

    assert train_dates.nunique() == 1006
    assert test_dates.nunique() == 90
    assert len(train_dates.unique()) + len(test_dates.unique()) == 1096

    # Temporal bounds: max(train) < min(test)
    assert train_dates.max() == pd.Timestamp("2025-10-02")
    assert test_dates.min() == pd.Timestamp("2025-10-03")
    assert test_dates.max() == pd.Timestamp("2025-12-31")
    assert train_dates.max() < test_dates.min()

    # Exact row counts: 72 series * 90 days = 6,480 test rows
    assert len(test_df) == 72 * 90
    assert len(train_pool_df) == 72 * 1006

    # Disjoint date sets
    overlap = set(train_dates.unique()).intersection(set(test_dates.unique()))
    assert len(overlap) == 0


@pytest.mark.parametrize("horizon", [1, 7])
def test_sequence_panel_rolling_origin_cv_horizons(sequence_panel_df: pd.DataFrame, horizon: int):
    """Verify rolling-origin CV on earlier data: at least 4 folds, strict temporal ordering, no future leaks."""
    dates = pd.to_datetime(sequence_panel_df["Date"].drop_duplicates().sort_values())
    splitter = RollingOriginSplitter(n_splits=4, horizon=horizon, step=28, test_cutoff=TEST_CUTOFF_DATE)
    folds = splitter.get_folds(dates)

    assert len(folds) >= 4
    cutoff_ts = pd.Timestamp(TEST_CUTOFF_DATE)

    for fold in folds:
        assert fold.horizon == horizon
        assert len(fold.val_dates) == horizon
        # 1. Train strictly before validation
        assert fold.train_end < fold.val_start
        assert max(fold.train_dates) < min(fold.val_dates)
        # 2. Validation strictly before untouched test cutoff
        assert fold.val_end < cutoff_ts
        assert max(fold.val_dates) < cutoff_ts
        # 3. Disjoint date sets
        assert set(fold.train_dates).isdisjoint(set(fold.val_dates))
        # 4. Training start remains fixed at earliest date
        assert fold.train_start == pd.Timestamp("2023-01-01")


def test_forecast_information_boundary_and_pipeline_fit_train_only(sequence_panel_df: pd.DataFrame):
    """Verify that feature scalers and encoders are fitted STRICTLY on training data without snooping.

    Also proves that NO validation date or test date appears in the training set,
    and only known-in-advance covariates and historical demand are available.
    """
    splitter = RollingOriginSplitter(n_splits=4, horizon=7, step=28, test_cutoff=TEST_CUTOFF_DATE)
    folds = splitter.get_folds(sequence_panel_df["Date"].unique())
    last_fold = folds[-1]

    train_mask = (sequence_panel_df["Date"] >= last_fold.train_start) & (sequence_panel_df["Date"] <= last_fold.train_end)
    val_mask = (sequence_panel_df["Date"] >= last_fold.val_start) & (sequence_panel_df["Date"] <= last_fold.val_end)

    train_df = sequence_panel_df[train_mask]
    val_df = sequence_panel_df[val_mask]

    # Verify no validation date is present in train
    assert not any(d in train_df["Date"].values for d in last_fold.val_dates)
    # Verify no test date is present in train
    test_dates = pd.date_range("2025-10-03", "2025-12-31")
    assert not any(d in train_df["Date"].values for d in test_dates)

    # Isolate target and clean covariates (dropping leakage)
    y_train, X_train = get_target_and_covariates(train_df, drop_leakage=True)
    y_val, X_val = get_target_and_covariates(val_df, drop_leakage=True)

    # Fit pipeline strictly on train covariates
    pipeline = TimeSeriesFeaturePipeline()
    pipeline.fit(X_train)

    # Check fitted parameters reflect ONLY X_train
    for i, col in enumerate(pipeline.active_num_cols_):
        expected_mean = X_train[col].mean()
        fitted_mean = pipeline.scaler.mean_[i]
        assert np.isclose(expected_mean, fitted_mean, rtol=1e-4)

    # Transform validation features
    val_transformed = pipeline.transform(X_val)
    assert len(val_transformed) == len(val_df)
    assert val_transformed.isna().sum().sum() == 0

