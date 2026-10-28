"""Time-series series construction, rolling-origin cross-validation splits, and feature pipeline.

Implements Task 1 requirements for Time-series Track B:
- Daily series construction per (Shop_ID, Food_Category) [48 series, 1,096 days each].
- Aggregated series per (Business_Type, Food_Category) [24 series] and per Food_Category [6 series].
- Target is strictly Daily_Demand (Units_Sold is strictly forbidden and rejected).
- Feature sets contain only known-in-advance covariates and strictly exclude leakage columns.
- Final test split isolation: last 90 calendar days (2025-10-03 to 2025-12-31) are strictly untouched.
- RollingOriginSplitter: generates at least 4 folds on pre-cutoff data (2023-01-01 to 2025-10-02),
  supporting 7-day and 28-day forecasting horizons with strict temporal ordering.
- TimeSeriesFeaturePipeline: scaler and categorical encoder that strictly fit on training data only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Sequence, Set, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from ml_service.data.synthetic_panel import (
        DEFAULT_SYNTHETIC_FULL_PATH,
        DEFAULT_SYNTHETIC_SEQ_PATH,
        load_synthetic_panel,
        validate_demand_target,
    )
except ModuleNotFoundError:
    from data.synthetic_panel import (
        DEFAULT_SYNTHETIC_FULL_PATH,
        DEFAULT_SYNTHETIC_SEQ_PATH,
        load_synthetic_panel,
        validate_demand_target,
    )


TARGET_COLUMN: str = "Daily_Demand"
TEST_CUTOFF_DATE: str = "2025-10-03"
FINAL_TEST_DAYS: int = 90

# Columns that represent post-demand outcomes or operational inventory accounting.
# Using any of these as feature inputs for demand forecasting introduces direct data leakage.
LEAKAGE_COLUMNS: List[str] = [
    "Units_Sold",
    "Remaining_Stock",
    "Waste_Quantity",
    "Waste_Reason",
    "Donation_Made",
    "Donated_Units",
    "Carried_Forward_Units",
    "Waste_Level",
]

# Exogenous covariates known in advance before daily demand realization
KNOWN_COVARIATES: List[str] = [
    "Promotion",
    "Weather",
    "Temperature_C",
    "Rain_mm",
    "Day_Of_Week",
    "Is_Weekend",
    "Is_Holiday",
    "Festival",
    "Shelf_Life_Days",
    "Lead_Time_Days",
    "Unit_Cost_INR",
    "Unit_Price_INR",
    "Storage_Temperature",
    "City",
    "Latitude",
    "Longitude",
    "Business_Type",
    "Food_Category",
    "Shop_ID",
]

NUMERICAL_COVARIATES: List[str] = [
    "Temperature_C",
    "Rain_mm",
    "Shelf_Life_Days",
    "Lead_Time_Days",
    "Unit_Cost_INR",
    "Unit_Price_INR",
    "Storage_Temperature",
    "Latitude",
    "Longitude",
]

CATEGORICAL_COVARIATES: List[str] = [
    "Promotion",
    "Weather",
    "Festival",
    "City",
    "Business_Type",
    "Food_Category",
    "Shop_ID",
]

CALENDAR_COVARIATES: List[str] = [
    "Day_Of_Week",
    "Is_Weekend",
    "Is_Holiday",
]


class LeakageError(ValueError):
    """Raised when data leakage columns are detected in feature inputs."""
    pass


class TemporalOrderViolationError(ValueError):
    """Raised when validation dates precede training dates or overlap occurs."""
    pass


@dataclass(frozen=True)
class CVFold:
    """Metadata representing a single rolling-origin cross-validation fold."""
    fold_idx: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    val_start: pd.Timestamp
    val_end: pd.Timestamp
    horizon: int
    train_dates: pd.DatetimeIndex
    val_dates: pd.DatetimeIndex

    def validate_invariants(self, test_cutoff: pd.Timestamp) -> None:
        """Enforce temporal integrity on this fold."""
        if len(self.train_dates) == 0:
            raise TemporalOrderViolationError(f"Fold {self.fold_idx}: Train dates are empty.")
        if len(self.val_dates) != self.horizon:
            raise TemporalOrderViolationError(
                f"Fold {self.fold_idx}: Expected {self.horizon} validation dates, got {len(self.val_dates)}."
            )
        if self.train_end >= self.val_start:
            raise TemporalOrderViolationError(
                f"Fold {self.fold_idx}: Train end ({self.train_end}) >= Val start ({self.val_start}). "
                "Validation must strictly succeed training."
            )
        if self.val_end >= test_cutoff:
            raise TemporalOrderViolationError(
                f"Fold {self.fold_idx}: Val end ({self.val_end}) reaches or exceeds test cutoff ({test_cutoff}). "
                "Final test set must remain untouched."
            )
        overlap = set(self.train_dates).intersection(set(self.val_dates))
        if overlap:
            raise TemporalOrderViolationError(
                f"Fold {self.fold_idx}: Found {len(overlap)} overlapping dates between train and validation."
            )


def verify_no_leakage(columns: Sequence[str]) -> None:
    """Verify that none of the forbidden outcome/accounting columns are present in features.

    Raises:
        LeakageError: If any leakage column is found.
    """
    found_leakage = [col for col in columns if col in LEAKAGE_COLUMNS]
    if found_leakage:
        raise LeakageError(
            f"DATA LEAKAGE DETECTED: Features contain forbidden outcome/accounting columns: {found_leakage}. "
            "These columns must never be used as inputs for demand forecasting."
        )


def build_shop_category_series(
    df: pd.DataFrame,
    target_col: str = TARGET_COLUMN,
    include_leakage: bool = False,
) -> Dict[Tuple[str, str], pd.DataFrame]:
    """Construct 48 daily time series for each (Shop_ID, Food_Category) pair.

    Args:
        df: Cleaned synthetic panel DataFrame (must contain Shop_ID and Food_Category).
        target_col: Target column name (defaults to 'Daily_Demand'). Rejects 'Units_Sold'.
        include_leakage: If False (default), drops all outcome/accounting leakage columns.

    Returns:
        Dict mapping (Shop_ID, Food_Category) tuple to a sorted, complete daily DataFrame
        indexed by Date.
    """
    validate_demand_target(target_col)

    if not include_leakage:
        cols_to_drop = [c for c in LEAKAGE_COLUMNS if c in df.columns and c != target_col]
        work_df = df.drop(columns=cols_to_drop)
    else:
        work_df = df.copy()

    # Ensure Date is datetime
    if not pd.api.types.is_datetime64_any_dtype(work_df["Date"]):
        work_df["Date"] = pd.to_datetime(work_df["Date"])

    series_dict: Dict[Tuple[str, str], pd.DataFrame] = {}
    grouped = work_df.groupby(["Shop_ID", "Food_Category"], sort=True)

    for (shop_id, food_cat), group in grouped:
        s_df = group.sort_values("Date").copy()
        s_df = s_df.set_index("Date", drop=False)
        series_dict[(str(shop_id), str(food_cat))] = s_df

    return series_dict


def build_business_type_category_series(
    df: pd.DataFrame,
    target_col: str = TARGET_COLUMN,
) -> Dict[Tuple[str, str], pd.DataFrame]:
    """Construct 24 aggregated daily series for each (Business_Type, Food_Category) pair.

    Aggregates:
    - Daily_Demand: sum across shops of the same business type
    - Weather / temperature / costs: mean across shops
    - Promotion / weekend / holiday / festival: representative daily values

    Returns:
        Dict mapping (Business_Type, Food_Category) to a daily DataFrame indexed by Date.
    """
    validate_demand_target(target_col)

    work_df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(work_df["Date"]):
        work_df["Date"] = pd.to_datetime(work_df["Date"])

    # Define aggregation spec
    agg_spec: Dict[str, Any] = {
        target_col: "sum",
        "Temperature_C": "mean",
        "Rain_mm": "mean",
        "Unit_Cost_INR": "mean",
        "Unit_Price_INR": "mean",
        "Shelf_Life_Days": "mean",
        "Lead_Time_Days": "mean",
        "Storage_Temperature": "mean",
        "Day_Of_Week": "first",
        "Is_Weekend": "first",
        "Is_Holiday": "first",
        "Festival": "first",
        "Promotion": lambda s: "Yes" if (s == "Yes").any() else "No",
        "Weather": lambda s: s.mode().iloc[0] if not s.mode().empty else s.iloc[0],
    }

    # Filter to columns that actually exist
    existing_spec = {k: v for k, v in agg_spec.items() if k in work_df.columns}

    grouped = work_df.groupby(["Business_Type", "Food_Category", "Date"], sort=True).agg(existing_spec)
    grouped = grouped.reset_index()

    series_dict: Dict[Tuple[str, str], pd.DataFrame] = {}
    for (b_type, f_cat), group in grouped.groupby(["Business_Type", "Food_Category"], sort=True):
        s_df = group.sort_values("Date").copy()
        s_df = s_df.set_index("Date", drop=False)
        series_dict[(str(b_type), str(f_cat))] = s_df

    return series_dict


def build_category_aggregate_series(
    df: pd.DataFrame,
    target_col: str = TARGET_COLUMN,
) -> Dict[str, pd.DataFrame]:
    """Construct 6 network-wide aggregated daily series, one per Food_Category.

    Aggregates:
    - Daily_Demand: sum across all 8 shops
    - Continuous covariates: mean across network
    - Calendar covariates: first/max

    Returns:
        Dict mapping Food_Category to a daily DataFrame indexed by Date.
    """
    validate_demand_target(target_col)

    work_df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(work_df["Date"]):
        work_df["Date"] = pd.to_datetime(work_df["Date"])

    agg_spec: Dict[str, Any] = {
        target_col: "sum",
        "Temperature_C": "mean",
        "Rain_mm": "mean",
        "Unit_Cost_INR": "mean",
        "Unit_Price_INR": "mean",
        "Shelf_Life_Days": "mean",
        "Lead_Time_Days": "mean",
        "Storage_Temperature": "mean",
        "Day_Of_Week": "first",
        "Is_Weekend": "first",
        "Is_Holiday": "first",
        "Festival": "first",
        "Promotion": lambda s: "Yes" if (s == "Yes").any() else "No",
        "Weather": lambda s: s.mode().iloc[0] if not s.mode().empty else s.iloc[0],
    }
    existing_spec = {k: v for k, v in agg_spec.items() if k in work_df.columns}

    grouped = work_df.groupby(["Food_Category", "Date"], sort=True).agg(existing_spec)
    grouped = grouped.reset_index()

    series_dict: Dict[str, pd.DataFrame] = {}
    for f_cat, group in grouped.groupby("Food_Category", sort=True):
        s_df = group.sort_values("Date").copy()
        s_df = s_df.set_index("Date", drop=False)
        series_dict[str(f_cat)] = s_df

    return series_dict


def split_train_test(
    df: pd.DataFrame,
    test_cutoff: Union[str, pd.Timestamp] = TEST_CUTOFF_DATE,
    test_days: int = FINAL_TEST_DAYS,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split panel or series data into pre-cutoff training pool and untouched final test set.

    Args:
        df: DataFrame containing a 'Date' column or DatetimeIndex.
        test_cutoff: Cutoff date string or Timestamp (defaults to '2025-10-03').
        test_days: Expected number of distinct calendar days in test set (default 90).

    Returns:
        Tuple of (train_pool_df, test_df).

    Raises:
        TemporalOrderViolationError: If cutoff invariants are violated.
    """
    cutoff_ts = pd.to_datetime(test_cutoff)

    if "Date" in df.columns:
        dates = pd.to_datetime(df["Date"])
    elif isinstance(df.index, pd.DatetimeIndex):
        dates = df.index
    else:
        raise ValueError("DataFrame must contain 'Date' column or DatetimeIndex.")

    train_mask = dates < cutoff_ts
    test_mask = dates >= cutoff_ts

    train_pool_df = df[train_mask].copy()
    test_df = df[test_mask].copy()

    # Validate split properties
    if len(train_pool_df) == 0:
        raise TemporalOrderViolationError("Train pool DataFrame is empty after split.")
    if len(test_df) == 0:
        raise TemporalOrderViolationError("Test DataFrame is empty after split.")

    train_dates = dates[train_mask]
    test_dates = dates[test_mask]

    if train_dates.max() >= test_dates.min():
        raise TemporalOrderViolationError(
            f"Train max date ({train_dates.max()}) >= Test min date ({test_dates.min()})."
        )

    n_test_unique = len(test_dates.unique())
    if test_days > 0 and n_test_unique != test_days:
        if not (n_test_unique in (90, 91) and test_days in (90, 91)):
            raise TemporalOrderViolationError(
                f"Expected exactly {test_days} distinct days in test set, but got {n_test_unique}."
            )

    return train_pool_df, test_df


class RollingOriginSplitter:
    """Rolling-origin cross-validation splitter for time series and panel data.

    Enforces:
    1. Operates strictly on pre-cutoff training pool (never touches the final test set).
    2. Every validation window is strictly after its corresponding training window.
    3. No future data leakage into the training window.
    4. Configurable number of folds (default 4) and horizons (e.g. 7-day and 28-day).
    5. Disjoint train and validation sets per fold.
    """

    def __init__(
        self,
        n_splits: int = 4,
        horizon: int = 7,
        step: Optional[int] = None,
        min_train_days: int = 180,
        test_cutoff: Union[str, pd.Timestamp] = TEST_CUTOFF_DATE,
    ):
        if n_splits < 1:
            raise ValueError(f"n_splits must be at least 1, got {n_splits}")
        if horizon < 1:
            raise ValueError(f"horizon must be at least 1, got {horizon}")

        self.n_splits = n_splits
        self.horizon = horizon
        # Default step to 28 days for 7-day horizon, or horizon itself if step not specified
        if step is None:
            self.step = 28 if horizon == 7 else horizon
        else:
            self.step = step
        self.min_train_days = min_train_days
        self.test_cutoff = pd.to_datetime(test_cutoff)

    def get_folds(self, unique_dates: Sequence[pd.Timestamp]) -> List[CVFold]:
        """Compute fold boundaries from a sorted sequence of distinct calendar dates.

        Folds are generated by stepping backwards from the final pre-cutoff date,
        ensuring the validation windows sit immediately adjacent to the test period.
        """
        all_dates = pd.DatetimeIndex(sorted(pd.to_datetime(unique_dates)))
        # Pre-cutoff dates only
        pre_cutoff_dates = all_dates[all_dates < self.test_cutoff]
        n_dates = len(pre_cutoff_dates)

        if n_dates < self.min_train_days + self.horizon:
            raise ValueError(
                f"Insufficient pre-cutoff days ({n_dates}) for min_train_days ({self.min_train_days}) "
                f"and horizon ({self.horizon})."
            )

        folds: List[CVFold] = []
        end_idx = n_dates - 1  # Last day of pre-cutoff data

        for i in range(self.n_splits - 1, -1, -1):
            val_end_idx = end_idx - (self.n_splits - 1 - i) * self.step
            val_start_idx = val_end_idx - self.horizon + 1
            train_end_idx = val_start_idx - 1
            train_start_idx = 0

            if train_start_idx > train_end_idx or (train_end_idx - train_start_idx + 1) < self.min_train_days:
                raise ValueError(
                    f"Fold {i} requires training window starting at {train_start_idx} and ending at {train_end_idx}, "
                    f"which has fewer than {self.min_train_days} days."
                )

            t_dates = pre_cutoff_dates[train_start_idx : train_end_idx + 1]
            v_dates = pre_cutoff_dates[val_start_idx : val_end_idx + 1]

            fold = CVFold(
                fold_idx=i,
                train_start=t_dates[0],
                train_end=t_dates[-1],
                val_start=v_dates[0],
                val_end=v_dates[-1],
                horizon=self.horizon,
                train_dates=t_dates,
                val_dates=v_dates,
            )
            fold.validate_invariants(self.test_cutoff)
            folds.append(fold)

        folds.sort(key=lambda f: f.fold_idx)
        return folds

    def split_series(
        self,
        series_df: pd.DataFrame,
    ) -> Generator[Tuple[pd.DataFrame, pd.DataFrame, CVFold], None, None]:
        """Yield (train_df, val_df, fold_meta) for a single time series DataFrame."""
        if "Date" in series_df.columns:
            dates = pd.to_datetime(series_df["Date"])
        elif isinstance(series_df.index, pd.DatetimeIndex):
            dates = series_df.index
        else:
            raise ValueError("Series DataFrame must have 'Date' column or DatetimeIndex.")

        folds = self.get_folds(dates.unique())
        for fold in folds:
            train_mask = (dates >= fold.train_start) & (dates <= fold.train_end)
            val_mask = (dates >= fold.val_start) & (dates <= fold.val_end)

            train_df = series_df[train_mask].copy()
            val_df = series_df[val_mask].copy()

            yield train_df, val_df, fold

    def split_panel(
        self,
        panel_df: pd.DataFrame,
    ) -> Generator[Tuple[pd.DataFrame, pd.DataFrame, CVFold], None, None]:
        """Yield (train_panel_df, val_panel_df, fold_meta) for the full panel DataFrame."""
        if "Date" in panel_df.columns:
            dates = pd.to_datetime(panel_df["Date"])
        elif isinstance(panel_df.index, pd.DatetimeIndex):
            dates = panel_df.index
        else:
            raise ValueError("Panel DataFrame must have 'Date' column or DatetimeIndex.")

        folds = self.get_folds(dates.unique())
        for fold in folds:
            train_mask = (dates >= fold.train_start) & (dates <= fold.train_end)
            val_mask = (dates >= fold.val_start) & (dates <= fold.val_end)

            train_df = panel_df[train_mask].copy()
            val_df = panel_df[val_mask].copy()

            yield train_df, val_df, fold


class TimeSeriesFeaturePipeline:
    """Preprocesses exogenous features strictly on training folds with zero data leakage.

    Features handled:
    - Numerical: Standardized using mean and standard deviation learned strictly on X_train.
    - Categorical: One-hot encoded using categories observed strictly in X_train
      (unseen categories in validation/test are gracefully encoded as zeros).
    - Calendar: Day_Of_Week, Is_Weekend, Is_Holiday passed as numeric indicators.

    Strictly forbids:
    - Target column Units_Sold (validated via validate_demand_target).
    - Any leakage outcome column (Units_Sold, Remaining_Stock, Waste_Quantity, etc.).
    """

    def __init__(
        self,
        numerical_cols: Optional[List[str]] = None,
        categorical_cols: Optional[List[str]] = None,
        calendar_cols: Optional[List[str]] = None,
    ):
        self.numerical_cols = numerical_cols if numerical_cols is not None else NUMERICAL_COVARIATES
        self.categorical_cols = categorical_cols if categorical_cols is not None else CATEGORICAL_COVARIATES
        self.calendar_cols = calendar_cols if calendar_cols is not None else CALENDAR_COVARIATES

        self.scaler = StandardScaler()
        self.encoder = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
        self.fitted_: bool = False

        self.active_num_cols_: List[str] = []
        self.active_cat_cols_: List[str] = []
        self.active_cal_cols_: List[str] = []
        self.encoded_feature_names_: List[str] = []

    def fit(self, X_train: pd.DataFrame) -> "TimeSeriesFeaturePipeline":
        """Fit scaler and categorical encoder strictly on training data."""
        verify_no_leakage(X_train.columns)

        self.active_num_cols_ = [c for c in self.numerical_cols if c in X_train.columns]
        self.active_cat_cols_ = [c for c in self.categorical_cols if c in X_train.columns]
        self.active_cal_cols_ = [c for c in self.calendar_cols if c in X_train.columns]

        # Fit numerical scaler
        if self.active_num_cols_:
            self.scaler.fit(X_train[self.active_num_cols_].fillna(0.0))

        # Fit categorical encoder
        if self.active_cat_cols_:
            self.encoder.fit(X_train[self.active_cat_cols_].astype(str).fillna("missing"))

        # Determine output feature names
        feature_names: List[str] = list(self.active_num_cols_)
        if self.active_cat_cols_:
            cat_names = self.encoder.get_feature_names_out(self.active_cat_cols_)
            feature_names.extend(list(cat_names))
        feature_names.extend(list(self.active_cal_cols_))

        self.encoded_feature_names_ = feature_names
        self.fitted_ = True
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Transform input features using parameters fitted strictly on training data."""
        if not self.fitted_:
            raise RuntimeError("Pipeline must be fitted before calling transform().")

        verify_no_leakage(X.columns)

        parts: List[pd.DataFrame] = []

        # Numerical transform
        if self.active_num_cols_:
            num_scaled = self.scaler.transform(X[self.active_num_cols_].fillna(0.0))
            df_num = pd.DataFrame(
                num_scaled,
                columns=self.active_num_cols_,
                index=X.index,
            )
            parts.append(df_num)

        # Categorical transform
        if self.active_cat_cols_:
            cat_encoded = self.encoder.transform(X[self.active_cat_cols_].astype(str).fillna("missing"))
            cat_cols = self.encoder.get_feature_names_out(self.active_cat_cols_)
            df_cat = pd.DataFrame(
                cat_encoded,
                columns=cat_cols,
                index=X.index,
            )
            parts.append(df_cat)

        # Calendar transform (pass through as numeric indicators)
        if self.active_cal_cols_:
            df_cal = X[self.active_cal_cols_].astype(float).fillna(0.0).copy()
            parts.append(df_cal)

        if not parts:
            return pd.DataFrame(index=X.index)

        transformed_df = pd.concat(parts, axis=1)
        return transformed_df

    def fit_transform(self, X_train: pd.DataFrame) -> pd.DataFrame:
        """Fit strictly on training data and return transformed DataFrame."""
        return self.fit(X_train).transform(X_train)


def get_target_and_covariates(
    df: pd.DataFrame,
    target_col: str = TARGET_COLUMN,
    drop_leakage: bool = True,
) -> Tuple[pd.Series, pd.DataFrame]:
    """Isolate target series and exogenous covariates while enforcing all invariants.

    Args:
        df: Input DataFrame.
        target_col: Target column name (defaults to 'Daily_Demand').
        drop_leakage: If True, removes all leakage columns from covariates.

    Returns:
        Tuple of (y_target_series, X_covariates_df).

    Raises:
        ValueError: If target_col is 'Units_Sold' or if leakage columns remain when drop_leakage=False.
    """
    validate_demand_target(target_col)

    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in DataFrame.")

    y = df[target_col].copy()

    # Drop target and metadata/identifiers that are not covariates
    cols_to_drop = [target_col]
    if "Inventory_ID" in df.columns:
        cols_to_drop.append("Inventory_ID")
    if "Data_Origin" in df.columns:
        cols_to_drop.append("Data_Origin")
    if "Expiry_Date" in df.columns:
        cols_to_drop.append("Expiry_Date")

    if drop_leakage:
        for c in LEAKAGE_COLUMNS:
            if c in df.columns and c not in cols_to_drop:
                cols_to_drop.append(c)

    X = df.drop(columns=cols_to_drop).copy()

    # If drop_leakage was False, this verifies whether leakage exists
    verify_no_leakage(X.columns)

    return y, X
