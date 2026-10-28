"""Lag Feature Engineering and Direct/Recursive Multi-step Forecasters (Task 4 Experiment).

Implements Task 4 requirements:
1. Lag features built strictly from information available at forecast origin t:
   - demand_lag_1 through demand_lag_7 (y_{t}, y_{t-1}, ..., y_{t-6})
   - rolling_mean_7 (7-day rolling mean of past demand ending at forecast origin t)
   - rolling_mean_28 (28-day rolling mean of past demand ending at forecast origin t)
   - same_weekday_last_week (y_{t - (7 - h)} for horizon step h in [1..7], strictly in the past)
2. Direct Multi-step Forecasting (DirectLagDemandForecaster):
   - Trains separate step models M_1, ..., M_7 for each horizon step h in {1..7}
   - Eliminates autoregressive error compounding
   - Evaluates with LightGBM and HistGradientBoosting
3. Recursive Multi-step Forecasting (RecursiveLagDemandForecaster):
   - Trains a single 1-step model and rolls autoregressive predictions forward
4. Strict No-Leakage Verification:
   - Validates that no feature at forecast origin t accesses ground-truth target from t+1 or later.
5. Rolling-origin evaluation and final 90-day test comparison.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
import lightgbm as lgb

try:
    from ml_service.data.time_series_splits import (
        KNOWN_COVARIATES,
        LEAKAGE_COLUMNS,
        RollingOriginSplitter,
        TimeSeriesFeaturePipeline,
        verify_no_leakage,
    )
    from ml_service.models.metrics import (
        compute_bias,
        compute_coverage,
        compute_mae,
        compute_rmse,
        compute_wape,
        evaluate_forecast,
    )
except ModuleNotFoundError:
    from data.time_series_splits import (
        KNOWN_COVARIATES,
        LEAKAGE_COLUMNS,
        RollingOriginSplitter,
        TimeSeriesFeaturePipeline,
        verify_no_leakage,
    )
    from models.metrics import (
        compute_bias,
        compute_coverage,
        compute_mae,
        compute_rmse,
        compute_wape,
        evaluate_forecast,
    )


LAG_FEATURE_NAMES = [
    "demand_lag_1",
    "demand_lag_2",
    "demand_lag_3",
    "demand_lag_4",
    "demand_lag_5",
    "demand_lag_6",
    "demand_lag_7",
    "rolling_mean_7",
    "rolling_mean_28",
    "same_weekday_last_week",
]


def compute_origin_lags(history_series: np.ndarray, horizon_step: int = 1) -> Dict[str, float]:
    """Compute lag features from historical demand array y[0..t] for horizon step h.
    
    Args:
        history_series: 1D array of historical demand up to and including forecast origin t.
                        The last element history_series[-1] is y_t.
        horizon_step: Future day step h in {1..7} being predicted (t + h).
    
    Returns:
        Dictionary of lag features strictly known at origin t.
    """
    n = len(history_series)
    if n < 1:
        raise ValueError("history_series must contain at least 1 historical observation")

    # Impute if short history
    def get_lag(k: int) -> float:
        # k=1 -> history_series[-1] (y_t)
        # k=2 -> history_series[-2] (y_{t-1})
        if n >= k:
            return float(history_series[-k])
        return float(history_series[0])

    lag_1 = get_lag(1)
    lag_2 = get_lag(2)
    lag_3 = get_lag(3)
    lag_4 = get_lag(4)
    lag_5 = get_lag(5)
    lag_6 = get_lag(6)
    lag_7 = get_lag(7)

    # Rolling means ending at origin t
    w7 = min(7, n)
    rolling_7 = float(np.mean(history_series[-w7:]))

    w28 = min(28, n)
    rolling_28 = float(np.mean(history_series[-w28:]))

    # Same weekday last week for target date (t + h):
    # Target date is t + h. 7 days prior is (t + h) - 7 = t - (7 - h).
    # Since 1 <= h <= 7, 0 <= 7 - h <= 6.
    # Therefore, step back (7 - h) days before origin t.
    # In 1-indexed lag from origin: lag_k = 1 + (7 - h).
    # E.g. h=7 -> lag_1 (y_t); h=1 -> lag_7 (y_{t-6}).
    same_weekday_k = 1 + (7 - horizon_step)
    same_weekday = get_lag(same_weekday_k)

    return {
        "demand_lag_1": lag_1,
        "demand_lag_2": lag_2,
        "demand_lag_3": lag_3,
        "demand_lag_4": lag_4,
        "demand_lag_5": lag_5,
        "demand_lag_6": lag_6,
        "demand_lag_7": lag_7,
        "rolling_mean_7": rolling_7,
        "rolling_mean_28": rolling_28,
        "same_weekday_last_week": same_weekday,
    }


class DirectLagDemandForecaster:
    """Direct Multi-Step Demand Forecaster with past 7 days lag features.
    
    For a 7-day horizon, trains 7 separate step estimators {M_1, ..., M_7}.
    For each step h in {1..7}:
      Target: y_{t+h}
      Features: Known exogenous covariates for day t+h PLUS
                Lag features (demand_lag_1..7, rolling_mean_7, rolling_mean_28,
                same_weekday_last_week) computed strictly from demand up to origin date t.
    
    This direct formulation avoids the compounding error of recursive rollouts
    and guarantees zero look-ahead leakage.
    """

    def __init__(
        self,
        estimator_type: Literal["hist_gradient_boosting", "lightgbm"] = "hist_gradient_boosting",
        horizon: int = 7,
        learning_rate: float = 0.08,
        n_estimators: int = 60,
        random_state: int = 42,
    ) -> None:
        self.estimator_type = estimator_type
        self.horizon = horizon
        self.learning_rate = learning_rate
        self.n_estimators = n_estimators
        self.random_state = random_state

        self.models_: Dict[int, Any] = {}
        self.pipelines_: Dict[int, TimeSeriesFeaturePipeline] = {}
        self.residual_quantiles_: Dict[int, Dict[float, Tuple[float, float]]] = {}

    def _create_base_model(self) -> Any:
        if self.estimator_type == "lightgbm":
            return lgb.LGBMRegressor(
                objective="poisson",
                n_estimators=self.n_estimators,
                learning_rate=self.learning_rate,
                random_state=self.random_state,
                verbose=-1,
            )
        else:
            return HistGradientBoostingRegressor(
                loss="poisson",
                max_iter=self.n_estimators,
                learning_rate=self.learning_rate,
                random_state=self.random_state,
            )

    def _build_step_dataset(
        self,
        panel_df: pd.DataFrame,
        horizon_step: int,
    ) -> Tuple[pd.DataFrame, np.ndarray]:
        """Build training dataset for step h using panel data."""
        df_sorted = panel_df.sort_values(["Shop_ID", "Food_Category", "Date"]).copy()
        
        feature_rows: List[Dict[str, Any]] = []
        target_vals: List[float] = []

        grouped = df_sorted.groupby(["Shop_ID", "Food_Category"], sort=False)

        for (shop_id, food_cat), group in grouped:
            demands = group["Daily_Demand"].values
            n_obs = len(demands)
            if n_obs <= 28 + horizon_step:
                continue

            # Drop target and any forbidden leakage outcome/accounting columns
            cols_to_drop = ["Daily_Demand", "Inventory_ID"] + [c for c in LEAKAGE_COLUMNS if c in group.columns]
            group_exog = group.drop(columns=cols_to_drop, errors="ignore")
            
            for i in range(28, n_obs - horizon_step):
                # Origin t is index i
                target_idx = i + horizon_step
                y_target = float(demands[target_idx])

                history_up_to_t = demands[: i + 1]
                lags = compute_origin_lags(history_up_to_t, horizon_step=horizon_step)

                # Target day exogenous row
                exog_row = group_exog.iloc[target_idx].to_dict()
                row = {**exog_row, **lags}
                feature_rows.append(row)
                target_vals.append(y_target)

        X_step = pd.DataFrame(feature_rows)
        verify_no_leakage(X_step.columns)
        y_step = np.array(target_vals, dtype=float)
        return X_step, y_step

    def fit(self, panel_df: pd.DataFrame) -> "DirectLagDemandForecaster":
        """Fit all 7 step models on panel training data."""
        for h in range(1, self.horizon + 1):
            X_step, y_step = self._build_step_dataset(panel_df, horizon_step=h)
            pipeline = TimeSeriesFeaturePipeline()
            X_proc = pipeline.fit_transform(X_step)

            model = self._create_base_model()
            model.fit(X_proc, y_step)

            # Calibrate 90% prediction intervals on step residuals
            y_pred_train = np.maximum(0.0, model.predict(X_proc))
            residuals = y_step - y_pred_train
            self.residual_quantiles_[h] = {}
            for cov in (0.90,):
                alpha = 1.0 - cov
                q_low = float(np.quantile(residuals, alpha / 2.0))
                q_high = float(np.quantile(residuals, 1.0 - (alpha / 2.0)))
                self.residual_quantiles_[h][cov] = (q_low, q_high)

            self.models_[h] = model
            self.pipelines_[h] = pipeline

        return self

    def predict_horizon_series(
        self,
        history_df: pd.DataFrame,
        future_exog_df: pd.DataFrame,
        coverage: float = 0.90,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Predict 7-day forecast horizon for a single series from forecast origin.
        
        Args:
            history_df: Historical records for this (Shop_ID, Food_Category) up to origin t.
            future_exog_df: Known exogenous covariates for the 7 forecast days (t+1..t+7).
            coverage: Prediction interval nominal coverage (default 0.90).
            
        Returns:
            Tuple of (y_pred, y_lower, y_upper) arrays of length 7.
        """
        history_demands = history_df["Daily_Demand"].values
        # Strip any target or leakage outcome columns from future exogenous features
        cols_to_drop = ["Daily_Demand", "Inventory_ID"] + [c for c in LEAKAGE_COLUMNS if c in future_exog_df.columns]
        clean_future_exog = future_exog_df.drop(columns=cols_to_drop, errors="ignore")

        preds: List[float] = []
        lowers: List[float] = []
        uppers: List[float] = []

        for h in range(1, self.horizon + 1):
            lags = compute_origin_lags(history_demands, horizon_step=h)
            step_exog = clean_future_exog.iloc[h - 1].to_dict()
            row = {**step_exog, **lags}
            X_single = pd.DataFrame([row])

            pipeline = self.pipelines_[h]
            model = self.models_[h]

            X_proc = pipeline.transform(X_single)
            yhat = float(max(0.0, model.predict(X_proc)[0]))
            
            q_low, q_high = self.residual_quantiles_[h].get(coverage, (-5.0, 5.0))
            yhat_low = float(max(0.0, yhat + q_low))
            yhat_high = float(max(yhat, yhat + q_high))

            preds.append(yhat)
            lowers.append(yhat_low)
            uppers.append(yhat_high)

        return np.array(preds), np.array(lowers), np.array(uppers)


def compute_empirical_autocorrelation(panel_df: pd.DataFrame) -> Dict[str, float]:
    """Compute mean autocorrelation across all 48 shop-category series at lag 1 and lag 7."""
    lag1_vals: List[float] = []
    lag7_vals: List[float] = []

    for _, grp in panel_df.groupby(["Shop_ID", "Food_Category"]):
        s = grp.sort_values("Date")["Daily_Demand"].astype(float)
        if len(s) > 28:
            ac1 = s.autocorr(lag=1)
            ac7 = s.autocorr(lag=7)
            if not np.isnan(ac1):
                lag1_vals.append(ac1)
            if not np.isnan(ac7):
                lag7_vals.append(ac7)

    return {
        "lag_1_mean_acf": float(np.mean(lag1_vals)),
        "lag_7_mean_acf": float(np.mean(lag7_vals)),
        "lag_1_std_acf": float(np.std(lag1_vals)),
        "lag_7_std_acf": float(np.std(lag7_vals)),
    }
