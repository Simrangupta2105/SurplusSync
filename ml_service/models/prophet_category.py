"""Prophet Category-Level Demand Forecasting Models (Track B).

Implements Task 3 requirements:
1. Prophet models per Food Category (Bakery, Dairy, Fruits, Meat, Prepared Food, Vegetables).
2. Extra exogenous regressors: Temperature_C, Rain_mm, Is_Weekend, Is_Holiday, Promotion.
3. Native 90% prediction intervals via Prophet's Bayesian posterior sampling (interval_width=0.90).
4. Rolling-origin cross-validation on pre-cutoff data (Date < 2025-10-03) across 4 folds.
5. 7-day and 28-day forecasting horizons.
6. Honest comparison against category-level baselines (Global Mean, Trailing Mean 28, Seasonal Naive 7, Weekday Profile).
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from prophet import Prophet

# Suppress cmdstanpy verbose logs
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)

try:
    from ml_service.data.synthetic_panel import validate_demand_target
    from ml_service.data.time_series_splits import (
        RollingOriginSplitter,
        build_category_aggregate_series,
        split_train_test,
        verify_no_leakage,
    )
    from ml_service.models.baseline_and_tabular import (
        GlobalMeanForecaster,
        SeasonalNaiveForecaster,
        TrailingMeanForecaster,
        WeekdayProfileForecaster,
    )
    from ml_service.models.metrics import evaluate_forecast
except ModuleNotFoundError:
    from data.synthetic_panel import validate_demand_target
    from data.time_series_splits import (
        RollingOriginSplitter,
        build_category_aggregate_series,
        split_train_test,
        verify_no_leakage,
    )
    from models.baseline_and_tabular import (
        GlobalMeanForecaster,
        SeasonalNaiveForecaster,
        TrailingMeanForecaster,
        WeekdayProfileForecaster,
    )
    from models.metrics import evaluate_forecast


DEFAULT_PROPHET_REGRESSORS: List[str] = [
    "Temperature_C",
    "Rain_mm",
    "Is_Weekend",
    "Is_Holiday",
    "Promotion",
]


class ProphetCategoryForecaster:
    """Prophet forecaster designed for category-level aggregate daily demand.

    Supports:
    - Weekly and yearly seasonality.
    - Exogenous known-in-advance regressors (temperature, rain, holidays, weekends, promotions).
    - Built-in 90% uncertainty intervals via Bayesian posterior sampling.
    - Guaranteed non-negative point forecasts and lower bounds.
    - Strict leakage check and demand target validation.
    """

    def __init__(
        self,
        use_regressors: bool = True,
        regressor_cols: Optional[List[str]] = None,
        weekly_seasonality: bool = True,
        yearly_seasonality: bool = True,
        daily_seasonality: bool = False,
        interval_width: float = 0.90,
    ) -> None:
        self.use_regressors = use_regressors
        self.regressor_cols = regressor_cols if regressor_cols is not None else DEFAULT_PROPHET_REGRESSORS
        self.weekly_seasonality = weekly_seasonality
        self.yearly_seasonality = yearly_seasonality
        self.daily_seasonality = daily_seasonality
        self.interval_width = interval_width

        self.model: Optional[Prophet] = None
        self.active_regressors_: List[str] = []
        self.is_fitted_: bool = False

    def _prepare_dataframe(
        self,
        df: pd.DataFrame,
        is_training: bool = True,
        target_col: str = "Daily_Demand",
    ) -> pd.DataFrame:
        """Format input DataFrame into Prophet-compatible format (ds, y, regressors)."""
        if "Date" in df.columns:
            dates = pd.to_datetime(df["Date"])
        elif isinstance(df.index, pd.DatetimeIndex):
            dates = df.index
        else:
            raise ValueError("Input DataFrame must have 'Date' column or DatetimeIndex.")

        p_df = pd.DataFrame({"ds": dates}, index=df.index)

        if is_training:
            validate_demand_target(target_col)
            if target_col not in df.columns:
                raise ValueError(f"Target column '{target_col}' not found in training DataFrame.")
            p_df["y"] = df[target_col].astype(float).values

        if self.use_regressors:
            # Check for leakage
            verify_no_leakage([c for c in df.columns if c != target_col])

            for col in self.active_regressors_:
                if col not in df.columns:
                    # Impute with 0 if missing in future dataframe
                    p_df[col] = 0.0
                elif col == "Promotion":
                    # Convert 'Yes'/'No' to numeric 1.0/0.0
                    p_df[col] = (df[col].astype(str).str.lower() == "yes").astype(float).values
                else:
                    p_df[col] = df[col].astype(float).fillna(0.0).values

        return p_df

    def fit(
        self,
        df_train: pd.DataFrame,
        target_col: str = "Daily_Demand",
    ) -> "ProphetCategoryForecaster":
        """Fit Prophet model on historical training data."""
        validate_demand_target(target_col)

        # Determine which regressors are present in training data
        if self.use_regressors:
            verify_no_leakage(df_train.columns)
            self.active_regressors_ = [c for c in self.regressor_cols if c in df_train.columns]
        else:
            self.active_regressors_ = []

        self.model = Prophet(
            weekly_seasonality=self.weekly_seasonality,
            yearly_seasonality=self.yearly_seasonality,
            daily_seasonality=self.daily_seasonality,
            interval_width=self.interval_width,
        )

        for reg in self.active_regressors_:
            self.model.add_regressor(reg)

        p_train = self._prepare_dataframe(df_train, is_training=True, target_col=target_col)
        self.model.fit(p_train)
        self.is_fitted_ = True
        return self

    def predict(self, df_future: pd.DataFrame) -> np.ndarray:
        """Generate point forecasts for future dates."""
        if not self.is_fitted_ or self.model is None:
            raise RuntimeError("ProphetCategoryForecaster must be fit before predict()")

        p_future = self._prepare_dataframe(df_future, is_training=False)
        forecast = self.model.predict(p_future)
        yhat = np.asarray(forecast["yhat"].values, dtype=float)
        return np.maximum(0.0, yhat)

    def predict_interval(
        self,
        df_future: pd.DataFrame,
        coverage: float = 0.90,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate point forecasts and uncertainty intervals."""
        if not self.is_fitted_ or self.model is None:
            raise RuntimeError("ProphetCategoryForecaster must be fit before predict_interval()")

        p_future = self._prepare_dataframe(df_future, is_training=False)
        forecast = self.model.predict(p_future)

        yhat = np.asarray(forecast["yhat"].values, dtype=float)
        yhat_lower = np.asarray(forecast["yhat_lower"].values, dtype=float)
        yhat_upper = np.asarray(forecast["yhat_upper"].values, dtype=float)

        # Enforce non-negativity and valid ordering
        yhat = np.maximum(0.0, yhat)
        yhat_lower = np.maximum(0.0, yhat_lower)
        yhat_upper = np.maximum(yhat, yhat_upper)

        return yhat, yhat_lower, yhat_upper


def evaluate_category_models_across_folds(
    category_series: Dict[str, pd.DataFrame],
    horizons: Sequence[int] = (7, 28),
    n_splits: int = 4,
    step: int = 28,
) -> pd.DataFrame:
    """Evaluate Prophet (with and without regressors) against baselines on each Food Category.

    Runs rolling-origin cross-validation on pre-cutoff data (Date < 2025-10-03).
    """
    records: List[Dict[str, Any]] = []

    for h in horizons:
        splitter = RollingOriginSplitter(n_splits=n_splits, horizon=h, step=step)

        for cat_name, s_df in category_series.items():
            for train_df, val_df, fold in splitter.split_series(s_df):
                y_train = train_df["Daily_Demand"].values
                y_val = val_df["Daily_Demand"].values
                val_dates = val_df["Date"].values

                # 1. Prophet with extra regressors
                p_reg = ProphetCategoryForecaster(use_regressors=True).fit(train_df)
                p_reg_hat, p_reg_low, p_reg_high = p_reg.predict_interval(val_df)
                p_reg_eval = evaluate_forecast(y_val, p_reg_hat, p_reg_low, p_reg_high)
                records.append({
                    "model": "Prophet_With_Regressors",
                    "category": cat_name,
                    "horizon": h,
                    "fold_idx": fold.fold_idx,
                    **p_reg_eval,
                })

                # 2. Pure Prophet (univariate, no exogenous regressors)
                p_pure = ProphetCategoryForecaster(use_regressors=False).fit(train_df)
                p_pure_hat, p_pure_low, p_pure_high = p_pure.predict_interval(val_df)
                p_pure_eval = evaluate_forecast(y_val, p_pure_hat, p_pure_low, p_pure_high)
                records.append({
                    "model": "Prophet_Pure",
                    "category": cat_name,
                    "horizon": h,
                    "fold_idx": fold.fold_idx,
                    **p_pure_eval,
                })

                # 3. Category Weekday Profile
                wp = WeekdayProfileForecaster().fit(y_train, train_df["Date"])
                wp_hat, wp_low, wp_high = wp.predict_interval(val_dates)
                wp_eval = evaluate_forecast(y_val, wp_hat, wp_low, wp_high)
                records.append({
                    "model": "Category_Weekday_Profile",
                    "category": cat_name,
                    "horizon": h,
                    "fold_idx": fold.fold_idx,
                    **wp_eval,
                })

                # 4. Category Trailing Mean 28
                tm = TrailingMeanForecaster(window=28).fit(y_train)
                tm_hat, tm_low, tm_high = tm.predict_interval(h)
                tm_eval = evaluate_forecast(y_val, tm_hat, tm_low, tm_high)
                records.append({
                    "model": "Category_Trailing_Mean_28",
                    "category": cat_name,
                    "horizon": h,
                    "fold_idx": fold.fold_idx,
                    **tm_eval,
                })

                # 5. Category Global Mean
                gm = GlobalMeanForecaster().fit(y_train)
                gm_hat, gm_low, gm_high = gm.predict_interval(h)
                gm_eval = evaluate_forecast(y_val, gm_hat, gm_low, gm_high)
                records.append({
                    "model": "Category_Global_Mean",
                    "category": cat_name,
                    "horizon": h,
                    "fold_idx": fold.fold_idx,
                    **gm_eval,
                })

                # 6. Category Seasonal Naive 7
                sn = SeasonalNaiveForecaster(seasonality=7).fit(y_train)
                sn_hat, sn_low, sn_high = sn.predict_interval(h)
                sn_eval = evaluate_forecast(y_val, sn_hat, sn_low, sn_high)
                records.append({
                    "model": "Category_Seasonal_Naive_7",
                    "category": cat_name,
                    "horizon": h,
                    "fold_idx": fold.fold_idx,
                    **sn_eval,
                })

    return pd.DataFrame(records)


def run_task3_category_evaluation(
    panel_df: pd.DataFrame,
    horizons: Sequence[int] = (7, 28),
    n_splits: int = 4,
    step: int = 28,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Execute complete Task 3 evaluation across all 6 categories.

    Returns:
        Tuple of:
        - raw_fold_records_df
        - summary_overall_df (averaged over categories and folds)
        - summary_by_category_df (averaged over folds per category)
    """
    train_pool_df, _ = split_train_test(panel_df)
    cat_series = build_category_aggregate_series(train_pool_df)

    raw_df = evaluate_category_models_across_folds(
        category_series=cat_series,
        horizons=horizons,
        n_splits=n_splits,
        step=step,
    )

    # 1. Summary overall (averaged across categories and folds)
    summary_overall = raw_df.groupby(["model", "horizon"])[
        ["wape", "mae", "rmse", "bias", "coverage"]
    ].mean().reset_index()
    summary_overall = summary_overall.sort_values(["horizon", "wape"]).reset_index(drop=True)

    # 2. Summary by category
    summary_by_cat = raw_df.groupby(["model", "category", "horizon"])[
        ["wape", "mae", "rmse", "bias", "coverage"]
    ].mean().reset_index()
    summary_by_cat = summary_by_cat.sort_values(["category", "horizon", "wape"]).reset_index(drop=True)

    return raw_df, summary_overall, summary_by_cat
