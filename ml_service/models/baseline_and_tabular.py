"""Baselines and Tabular Demand Forecasting Models (Track B).

Implements Task 2 requirements:
1. Baselines:
   - Global Mean (expanding history mean)
   - 28-day Trailing Mean (moving average of the last 28 days)
   - Seasonal Naive 7-day (repeats the last 7 days of demand, y_{t-7})
   - Weekday Profile (historical mean demand per day-of-week)
2. Tabular Models:
   - Poisson Regression (regularized log-linear with Poisson loss)
   - LightGBM Regressor (gradient boosting with Poisson objective)
   - HistGradientBoostingRegressor (scikit-learn fallback gradient booster)
3. 90% Prediction Intervals:
   - Calibrated using empirical residual quantiles (alpha=0.10 -> [q_0.05, q_0.95])
   - Guaranteed non-negative lower bounds
4. Metrics & Evaluation:
   - Evaluated across rolling-origin cross-validation folds on pre-cutoff data (Date < 2025-10-03)
   - 7-day and 28-day forecasting horizons
   - Metrics computed: WAPE, MAE, RMSE, Bias, and 90% Coverage
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor

try:
    import lightgbm as lgb
except ImportError:
    lgb = None

try:
    from ml_service.data.synthetic_panel import validate_demand_target
    from ml_service.data.time_series_splits import (
        RollingOriginSplitter,
        TimeSeriesFeaturePipeline,
        get_target_and_covariates,
        split_train_test,
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
    from data.synthetic_panel import validate_demand_target
    from data.time_series_splits import (
        RollingOriginSplitter,
        TimeSeriesFeaturePipeline,
        get_target_and_covariates,
        split_train_test,
    )
    from models.metrics import (
        compute_bias,
        compute_coverage,
        compute_mae,
        compute_rmse,
        compute_wape,
        evaluate_forecast,
    )


# --- 1. Baseline Forecasters ---

class GlobalMeanForecaster(BaseEstimator, RegressorMixin):
    """Predicts the expanding historical mean of the training target."""

    def __init__(self) -> None:
        self.mean_: float = 0.0
        self.residual_quantiles_: Dict[float, Tuple[float, float]] = {}

    def fit(self, y_train: Union[np.ndarray, Sequence[float], pd.Series]) -> "GlobalMeanForecaster":
        y_arr = np.asarray(y_train, dtype=float)
        self.mean_ = float(np.mean(y_arr))

        # Calibrate 90% residual interval
        residuals = y_arr - self.mean_
        self._calibrate_intervals(residuals)
        return self

    def _calibrate_intervals(self, residuals: np.ndarray, coverages: Sequence[float] = (0.90,)) -> None:
        for cov in coverages:
            alpha = 1.0 - cov
            q_low = float(np.quantile(residuals, alpha / 2.0))
            q_high = float(np.quantile(residuals, 1.0 - (alpha / 2.0)))
            self.residual_quantiles_[cov] = (q_low, q_high)

    def predict(self, horizon: int) -> np.ndarray:
        return np.full(horizon, self.mean_, dtype=float)

    def predict_interval(
        self,
        horizon: int,
        coverage: float = 0.90,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        yhat = self.predict(horizon)
        q_low, q_high = self.residual_quantiles_.get(coverage, (-5.0, 5.0))
        yhat_lower = np.maximum(0.0, yhat + q_low)
        yhat_upper = np.maximum(yhat, yhat + q_high)
        return yhat, yhat_lower, yhat_upper


class TrailingMeanForecaster(BaseEstimator, RegressorMixin):
    """Predicts the mean demand of the last `window` days (default 28 days)."""

    def __init__(self, window: int = 28) -> None:
        self.window = window
        self.trailing_mean_: float = 0.0
        self.residual_quantiles_: Dict[float, Tuple[float, float]] = {}

    def fit(self, y_train: Union[np.ndarray, Sequence[float], pd.Series]) -> "TrailingMeanForecaster":
        y_arr = np.asarray(y_train, dtype=float)
        if len(y_arr) == 0:
            raise ValueError("y_train is empty")

        effective_w = min(self.window, len(y_arr))
        self.trailing_mean_ = float(np.mean(y_arr[-effective_w:]))

        # Residuals computed against trailing mean over recent history
        residuals = y_arr[-effective_w:] - self.trailing_mean_
        for cov in (0.90,):
            alpha = 1.0 - cov
            q_low = float(np.quantile(residuals, alpha / 2.0))
            q_high = float(np.quantile(residuals, 1.0 - (alpha / 2.0)))
            self.residual_quantiles_[cov] = (q_low, q_high)
        return self

    def predict(self, horizon: int) -> np.ndarray:
        return np.full(horizon, self.trailing_mean_, dtype=float)

    def predict_interval(
        self,
        horizon: int,
        coverage: float = 0.90,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        yhat = self.predict(horizon)
        q_low, q_high = self.residual_quantiles_.get(coverage, (-5.0, 5.0))
        yhat_lower = np.maximum(0.0, yhat + q_low)
        yhat_upper = np.maximum(yhat, yhat + q_high)
        return yhat, yhat_lower, yhat_upper


class SeasonalNaiveForecaster(BaseEstimator, RegressorMixin):
    """Repeats the last `seasonality` (default 7) days of demand into the forecast horizon."""

    def __init__(self, seasonality: int = 7) -> None:
        self.seasonality = seasonality
        self.last_season_: np.ndarray = np.array([])
        self.residual_quantiles_: Dict[float, Tuple[float, float]] = {}

    def fit(self, y_train: Union[np.ndarray, Sequence[float], pd.Series]) -> "SeasonalNaiveForecaster":
        y_arr = np.asarray(y_train, dtype=float)
        if len(y_arr) < self.seasonality:
            raise ValueError(f"y_train has {len(y_arr)} elements, need at least {self.seasonality}")

        self.last_season_ = y_arr[-self.seasonality:].copy()

        # Compute seasonal naive lag residuals: y_t - y_{t-seasonality}
        diffs = y_arr[self.seasonality:] - y_arr[:-self.seasonality]
        for cov in (0.90,):
            alpha = 1.0 - cov
            q_low = float(np.quantile(diffs, alpha / 2.0))
            q_high = float(np.quantile(diffs, 1.0 - (alpha / 2.0)))
            self.residual_quantiles_[cov] = (q_low, q_high)
        return self

    def predict(self, horizon: int) -> np.ndarray:
        if len(self.last_season_) == 0:
            raise RuntimeError("Forecaster must be fit before predict()")

        # Tile last season pattern to fill horizon
        reps = int(math.ceil(horizon / self.seasonality))
        tiled = np.tile(self.last_season_, reps)
        return tiled[:horizon]

    def predict_interval(
        self,
        horizon: int,
        coverage: float = 0.90,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        yhat = self.predict(horizon)
        q_low, q_high = self.residual_quantiles_.get(coverage, (-5.0, 5.0))
        yhat_lower = np.maximum(0.0, yhat + q_low)
        yhat_upper = np.maximum(yhat, yhat + q_high)
        return yhat, yhat_lower, yhat_upper


class WeekdayProfileForecaster(BaseEstimator, RegressorMixin):
    """Predicts historical mean demand conditioned on day-of-week (Monday through Sunday)."""

    def __init__(self) -> None:
        self.dow_means_: Dict[int, float] = {}
        self.global_mean_: float = 0.0
        self.residual_quantiles_: Dict[float, Tuple[float, float]] = {}

    def fit(
        self,
        y_train: Union[np.ndarray, Sequence[float], pd.Series],
        dates_train: Union[pd.DatetimeIndex, Sequence[pd.Timestamp], pd.Series],
    ) -> "WeekdayProfileForecaster":
        y_arr = np.asarray(y_train, dtype=float)
        dt_idx = pd.DatetimeIndex(pd.to_datetime(dates_train))

        if len(y_arr) != len(dt_idx):
            raise ValueError("y_train and dates_train must have identical length")

        self.global_mean_ = float(np.mean(y_arr))
        dow_series = dt_idx.dayofweek

        for d in range(7):
            mask = dow_series == d
            if np.any(mask):
                self.dow_means_[d] = float(np.mean(y_arr[mask]))
            else:
                self.dow_means_[d] = self.global_mean_

        # Residuals against fitted weekday profiles
        fitted = np.array([self.dow_means_[d] for d in dow_series])
        residuals = y_arr - fitted
        for cov in (0.90,):
            alpha = 1.0 - cov
            q_low = float(np.quantile(residuals, alpha / 2.0))
            q_high = float(np.quantile(residuals, 1.0 - (alpha / 2.0)))
            self.residual_quantiles_[cov] = (q_low, q_high)
        return self

    def predict(self, dates_future: Union[pd.DatetimeIndex, Sequence[pd.Timestamp], pd.Series]) -> np.ndarray:
        dt_idx = pd.DatetimeIndex(pd.to_datetime(dates_future))
        preds = [self.dow_means_.get(d, self.global_mean_) for d in dt_idx.dayofweek]
        return np.array(preds, dtype=float)

    def predict_interval(
        self,
        dates_future: Union[pd.DatetimeIndex, Sequence[pd.Timestamp]],
        coverage: float = 0.90,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        yhat = self.predict(dates_future)
        q_low, q_high = self.residual_quantiles_.get(coverage, (-5.0, 5.0))
        yhat_lower = np.maximum(0.0, yhat + q_low)
        yhat_upper = np.maximum(yhat, yhat + q_high)
        return yhat, yhat_lower, yhat_upper


# --- 2. Tabular Forecasters ---

class PoissonRegressionForecaster:
    """Regularized log-linear Poisson regression forecaster with zero-leakage preprocessing."""

    def __init__(self, alpha: float = 1e-3, max_iter: int = 400) -> None:
        self.alpha = alpha
        self.max_iter = max_iter
        self.model = PoissonRegressor(alpha=self.alpha, max_iter=self.max_iter)
        self.pipeline: Optional[TimeSeriesFeaturePipeline] = None
        self.residual_quantiles_: Dict[float, Tuple[float, float]] = {}

    def fit(self, X_train: pd.DataFrame, y_train: Union[np.ndarray, pd.Series]) -> "PoissonRegressionForecaster":
        y_arr = np.asarray(y_train, dtype=float)
        self.pipeline = TimeSeriesFeaturePipeline()
        X_proc = self.pipeline.fit_transform(X_train)

        self.model.fit(X_proc, y_arr)

        # Calibrate 90% prediction interval from training residuals
        y_pred_train = np.maximum(0.0, self.model.predict(X_proc))
        residuals = y_arr - y_pred_train
        for cov in (0.90,):
            alpha_val = 1.0 - cov
            q_low = float(np.quantile(residuals, alpha_val / 2.0))
            q_high = float(np.quantile(residuals, 1.0 - (alpha_val / 2.0)))
            self.residual_quantiles_[cov] = (q_low, q_high)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.pipeline is None:
            raise RuntimeError("Model must be fit before predict()")
        X_proc = self.pipeline.transform(X)
        preds = np.asarray(self.model.predict(X_proc), dtype=float)
        return np.maximum(0.0, preds)

    def predict_interval(
        self,
        X: pd.DataFrame,
        coverage: float = 0.90,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        yhat = self.predict(X)
        q_low, q_high = self.residual_quantiles_.get(coverage, (-5.0, 5.0))
        yhat_lower = np.maximum(0.0, yhat + q_low)
        yhat_upper = np.maximum(yhat, yhat + q_high)
        return yhat, yhat_lower, yhat_upper


class LightGBMRegressionForecaster:
    """Gradient boosted tree forecaster with Poisson objective and zero-leakage preprocessing."""

    def __init__(
        self,
        objective: str = "poisson",
        n_estimators: int = 80,
        learning_rate: float = 0.08,
        random_state: int = 42,
    ) -> None:
        self.objective = objective
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.random_state = random_state

        self.model = lgb.LGBMRegressor(
            objective=self.objective,
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            random_state=self.random_state,
            verbose=-1,
        )
        self.pipeline: Optional[TimeSeriesFeaturePipeline] = None
        self.residual_quantiles_: Dict[float, Tuple[float, float]] = {}

    def fit(self, X_train: pd.DataFrame, y_train: Union[np.ndarray, pd.Series]) -> "LightGBMRegressionForecaster":
        y_arr = np.asarray(y_train, dtype=float)
        self.pipeline = TimeSeriesFeaturePipeline()
        X_proc = self.pipeline.fit_transform(X_train)

        self.model.fit(X_proc, y_arr)

        # Calibrate 90% prediction interval
        y_pred_train = np.maximum(0.0, self.model.predict(X_proc))
        residuals = y_arr - y_pred_train
        for cov in (0.90,):
            alpha_val = 1.0 - cov
            q_low = float(np.quantile(residuals, alpha_val / 2.0))
            q_high = float(np.quantile(residuals, 1.0 - (alpha_val / 2.0)))
            self.residual_quantiles_[cov] = (q_low, q_high)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.pipeline is None:
            raise RuntimeError("Model must be fit before predict()")
        X_proc = self.pipeline.transform(X)
        preds = np.asarray(self.model.predict(X_proc), dtype=float)
        return np.maximum(0.0, preds)

    def predict_interval(
        self,
        X: pd.DataFrame,
        coverage: float = 0.90,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        yhat = self.predict(X)
        q_low, q_high = self.residual_quantiles_.get(coverage, (-5.0, 5.0))
        yhat_lower = np.maximum(0.0, yhat + q_low)
        yhat_upper = np.maximum(yhat, yhat + q_high)
        return yhat, yhat_lower, yhat_upper


class HistGradientBoostingDemandModel:
    """Scikit-learn HistGradientBoostingRegressor demand model (fallback gradient booster)."""

    def __init__(
        self,
        loss: str = "poisson",
        max_iter: int = 80,
        learning_rate: float = 0.08,
        random_state: int = 42,
    ) -> None:
        self.loss = loss
        self.max_iter = max_iter
        self.learning_rate = learning_rate
        self.random_state = random_state

        self.model = HistGradientBoostingRegressor(
            loss=self.loss,
            max_iter=self.max_iter,
            learning_rate=self.learning_rate,
            random_state=self.random_state,
        )
        self.pipeline: Optional[TimeSeriesFeaturePipeline] = None
        self.residual_quantiles_: Dict[float, Tuple[float, float]] = {}

    def fit(self, X_train: pd.DataFrame, y_train: Union[np.ndarray, pd.Series]) -> "HistGradientBoostingDemandModel":
        y_arr = np.asarray(y_train, dtype=float)
        self.pipeline = TimeSeriesFeaturePipeline()
        X_proc = self.pipeline.fit_transform(X_train)

        self.model.fit(X_proc, y_arr)

        y_pred_train = np.maximum(0.0, self.model.predict(X_proc))
        residuals = y_arr - y_pred_train
        for cov in (0.90,):
            alpha_val = 1.0 - cov
            q_low = float(np.quantile(residuals, alpha_val / 2.0))
            q_high = float(np.quantile(residuals, 1.0 - (alpha_val / 2.0)))
            self.residual_quantiles_[cov] = (q_low, q_high)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.pipeline is None:
            raise RuntimeError("Model must be fit before predict()")
        X_proc = self.pipeline.transform(X)
        preds = np.asarray(self.model.predict(X_proc), dtype=float)
        return np.maximum(0.0, preds)

    def predict_interval(
        self,
        X: pd.DataFrame,
        coverage: float = 0.90,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        yhat = self.predict(X)
        q_low, q_high = self.residual_quantiles_.get(coverage, (-5.0, 5.0))
        yhat_lower = np.maximum(0.0, yhat + q_low)
        yhat_upper = np.maximum(yhat, yhat + q_high)
        return yhat, yhat_lower, yhat_upper


# --- 3. Evaluation Runners across Rolling-Origin Cross-Validation ---

def evaluate_baselines_across_folds(
    series_dict: Dict[Tuple[str, str], pd.DataFrame],
    horizon: int = 7,
    n_splits: int = 4,
    step: int = 28,
) -> pd.DataFrame:
    """Evaluate Global Mean, Trailing 28-day Mean, Seasonal Naive 7, and Weekday Profile.

    Evaluated across all series and rolling-origin folds on pre-cutoff data.
    """
    records: List[Dict[str, Any]] = []
    splitter = RollingOriginSplitter(n_splits=n_splits, horizon=horizon, step=step)

    # Evaluate across sample of representative series or all series
    for (shop_id, food_cat), s_df in series_dict.items():
        for train_df, val_df, fold in splitter.split_series(s_df):
            y_train = train_df["Daily_Demand"].values
            y_val = val_df["Daily_Demand"].values
            val_dates = val_df["Date"].values

            # 1. Global Mean
            gm = GlobalMeanForecaster().fit(y_train)
            gm_pred, gm_low, gm_high = gm.predict_interval(horizon)
            gm_eval = evaluate_forecast(y_val, gm_pred, gm_low, gm_high)

            records.append({
                "model": "Global_Mean",
                "shop_id": shop_id,
                "food_category": food_cat,
                "fold_idx": fold.fold_idx,
                "horizon": horizon,
                **gm_eval,
            })

            # 2. Trailing Mean 28
            tm = TrailingMeanForecaster(window=28).fit(y_train)
            tm_pred, tm_low, tm_high = tm.predict_interval(horizon)
            tm_eval = evaluate_forecast(y_val, tm_pred, tm_low, tm_high)

            records.append({
                "model": "Trailing_Mean_28",
                "shop_id": shop_id,
                "food_category": food_cat,
                "fold_idx": fold.fold_idx,
                "horizon": horizon,
                **tm_eval,
            })

            # 3. Seasonal Naive 7
            sn = SeasonalNaiveForecaster(seasonality=7).fit(y_train)
            sn_pred, sn_low, sn_high = sn.predict_interval(horizon)
            sn_eval = evaluate_forecast(y_val, sn_pred, sn_low, sn_high)

            records.append({
                "model": "Seasonal_Naive_7",
                "shop_id": shop_id,
                "food_category": food_cat,
                "fold_idx": fold.fold_idx,
                "horizon": horizon,
                **sn_eval,
            })

            # 4. Weekday Profile
            wp = WeekdayProfileForecaster().fit(y_train, train_df["Date"])
            wp_pred, wp_low, wp_high = wp.predict_interval(val_dates)
            wp_eval = evaluate_forecast(y_val, wp_pred, wp_low, wp_high)

            records.append({
                "model": "Weekday_Profile",
                "shop_id": shop_id,
                "food_category": food_cat,
                "fold_idx": fold.fold_idx,
                "horizon": horizon,
                **wp_eval,
            })

    return pd.DataFrame(records)


def evaluate_tabular_models_across_folds(
    panel_df: pd.DataFrame,
    horizon: int = 7,
    n_splits: int = 4,
    step: int = 28,
) -> pd.DataFrame:
    """Evaluate Poisson Regression, LightGBM, and HistGradientBoosting on the panel."""
    records: List[Dict[str, Any]] = []
    splitter = RollingOriginSplitter(n_splits=n_splits, horizon=horizon, step=step)

    for train_df, val_df, fold in splitter.split_panel(panel_df):
        y_train, X_train = get_target_and_covariates(train_df)
        y_val, X_val = get_target_and_covariates(val_df)

        # 1. Poisson Regressor
        poisson = PoissonRegressionForecaster().fit(X_train, y_train)
        p_pred, p_low, p_high = poisson.predict_interval(X_val)
        p_eval = evaluate_forecast(y_val.values, p_pred, p_low, p_high)

        records.append({
            "model": "Poisson_Regression",
            "fold_idx": fold.fold_idx,
            "horizon": horizon,
            **p_eval,
        })

        # 2. LightGBM Regressor
        lgbm = LightGBMRegressionForecaster().fit(X_train, y_train)
        lgb_pred, lgb_low, lgb_high = lgbm.predict_interval(X_val)
        lgb_eval = evaluate_forecast(y_val.values, lgb_pred, lgb_low, lgb_high)

        records.append({
            "model": "LightGBM",
            "fold_idx": fold.fold_idx,
            "horizon": horizon,
            **lgb_eval,
        })

        # 3. HistGradientBoosting Regressor
        hgb = HistGradientBoostingDemandModel().fit(X_train, y_train)
        hgb_pred, hgb_low, hgb_high = hgb.predict_interval(X_val)
        hgb_eval = evaluate_forecast(y_val.values, hgb_pred, hgb_low, hgb_high)

        records.append({
            "model": "HistGradientBoosting",
            "fold_idx": fold.fold_idx,
            "horizon": horizon,
            **hgb_eval,
        })

        # 4. Panel Global Mean baseline for reference
        gm_mean = float(y_train.mean())
        gm_pred = np.full(len(y_val), gm_mean)
        gm_residuals = y_train.values - gm_mean
        gm_low_offset = float(np.quantile(gm_residuals, 0.05))
        gm_high_offset = float(np.quantile(gm_residuals, 0.95))
        gm_low = np.maximum(0.0, gm_pred + gm_low_offset)
        gm_high = np.maximum(gm_pred, gm_pred + gm_high_offset)
        gm_eval = evaluate_forecast(y_val.values, gm_pred, gm_low, gm_high)

        records.append({
            "model": "Panel_Global_Mean",
            "fold_idx": fold.fold_idx,
            "horizon": horizon,
            **gm_eval,
        })

    return pd.DataFrame(records)


def run_task2_full_comparison(
    panel_df: pd.DataFrame,
    horizons: Sequence[int] = (7, 28),
    n_splits: int = 4,
    step: int = 28,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Execute complete Task 2 model evaluation across all baselines and tabular models.

    Returns:
        Tuple of (detailed_fold_metrics_df, summary_comparison_df).
    """
    train_pool_df, _ = split_train_test(panel_df)
    series_dict = {
        k: s_df[s_df["Date"] < pd.Timestamp("2025-10-03")].copy()
        for k, s_df in {
            (s, c): grp.sort_values("Date").set_index("Date", drop=False)
            for (s, c), grp in train_pool_df.groupby(["Shop_ID", "Food_Category"])
        }.items()
    }

    all_fold_records: List[pd.DataFrame] = []

    for h in horizons:
        # Tabular models on panel
        tab_df = evaluate_tabular_models_across_folds(train_pool_df, horizon=h, n_splits=n_splits, step=step)
        all_fold_records.append(tab_df)

        # Baselines on series (aggregated across the 48 series)
        base_df = evaluate_baselines_across_folds(series_dict, horizon=h, n_splits=n_splits, step=step)
        base_agg = base_df.groupby(["model", "fold_idx", "horizon"])[["wape", "mae", "rmse", "bias", "coverage"]].mean().reset_index()
        all_fold_records.append(base_agg)

    combined_folds_df = pd.concat(all_fold_records, ignore_index=True)

    # Summary table: average metrics across folds per model and horizon
    summary_df = combined_folds_df.groupby(["model", "horizon"])[["wape", "mae", "rmse", "bias", "coverage"]].mean().reset_index()
    summary_df = summary_df.sort_values(["horizon", "wape"]).reset_index(drop=True)

    return combined_folds_df, summary_df
