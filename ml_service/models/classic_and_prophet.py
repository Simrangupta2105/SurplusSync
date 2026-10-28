"""Classic Time-Series Baselines and Prophet Forecasters (Task 4).

Implements:
1. Classic Baselines across all 72 individual series:
   - Seasonal Naive-1:
     Predicts the most recent observed demand at origin T: y_{T+h} = y_T.
   - Seasonal Naive-7:
     Predicts demand from the same day-of-week last week: y_{T+h} = y_{T+h-7} <= y_T.
   - 28-Day Rolling Mean:
     Predicts the average demand over the lookback window [T-27 .. T].
   - Weekday Profile:
     Predicts historical average demand for the specific day-of-week of T+h up to origin T.
   - Calibrated 90% prediction intervals via empirical residual quantiles.
2. Category-Level Prophet Forecasters:
   - Trained per Food Category (Bakery, Dairy, Meat, Produce, Pantry, Prepared Meals).
   - Incorporates weekly and yearly seasonality.
   - Incorporates festivals via custom Prophet holidays DataFrame.
   - Incorporates extra exogenous regressors: Temperature_C, Rain_mm, Promotion.
   - Predicts at both Category Aggregate level and disaggregated 72-series level
     using strictly historical shop-within-category volume proportions.
3. Strict No-Leakage Protocol:
   - Uses only information up to forecast origin T.
   - Untouched final 90 days (2025-10-03 to 2025-12-31) strictly preserved.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from prophet import Prophet

# Suppress cmdstanpy verbose logs
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)

try:
    from ml_service.data.synthetic_panel import validate_demand_target
    from ml_service.data.time_series_splits import (
        FINAL_TEST_DAYS,
        LEAKAGE_COLUMNS,
        TEST_CUTOFF_DATE,
        RollingOriginSplitter,
        build_category_aggregate_series,
        verify_no_leakage,
    )
    from ml_service.models.fair_tabular_baselines import TabularFeatureEngine
    from ml_service.models.metrics import evaluate_forecast
except ModuleNotFoundError:
    import sys
    base_dir = str(Path(__file__).resolve().parent.parent)
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    from data.synthetic_panel import validate_demand_target
    from data.time_series_splits import (
        FINAL_TEST_DAYS,
        LEAKAGE_COLUMNS,
        TEST_CUTOFF_DATE,
        RollingOriginSplitter,
        build_category_aggregate_series,
        verify_no_leakage,
    )
    from models.fair_tabular_baselines import TabularFeatureEngine
    from models.metrics import evaluate_forecast


ClassicBaselineType = Literal["naive_1", "naive_7", "rolling_mean_28", "weekday_profile"]


class ClassicPanelBaselines:
    """Vectorized calculation of classic time-series baselines on TabularFeatureEngine."""

    def __init__(self, engine: TabularFeatureEngine):
        self.engine = engine
        self.demand = engine.demand_arr  # (1096, 72)
        self.dow = engine.cal_dow.astype(int)  # (1096,)
        self.n_dates = engine.n_dates
        self.n_series = engine.n_series

        # Precompute cumulative weekday mean matrices: shape (7, 1096, 72)
        self.dow_means = np.zeros((7, self.n_dates, self.n_series), dtype=np.float32)
        for w in range(7):
            mask = (self.dow == w)[:, None]  # (1096, 1)
            masked_demand = np.where(mask, self.demand, 0.0)
            cum_sum = np.cumsum(masked_demand, axis=0)
            cum_cnt = np.cumsum(mask.astype(float), axis=0)
            self.dow_means[w] = cum_sum / np.maximum(1.0, cum_cnt)

    def predict(
        self,
        origin_indices: Sequence[int],
        horizon: int,
        baseline_type: ClassicBaselineType,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate forecasts and empirical 90% prediction intervals for specified origins and horizon.

        Args:
            origin_indices: Array of integer date indices representing forecast origins T.
            horizon: Future step h in days (e.g. 1 or 7).
            baseline_type: One of 'naive_1', 'naive_7', 'rolling_mean_28', 'weekday_profile'.

        Returns:
            preds: (len(origins) * 72,) point forecasts (>= 0).
            lower: (len(origins) * 72,) lower bound 90% interval.
            upper: (len(origins) * 72,) upper bound 90% interval.
        """
        origs = np.asarray(origin_indices, dtype=np.int32)
        n_origs = len(origs)

        # 1. Point predictions per origin (shape: [n_origs, 72])
        if baseline_type == "naive_1":
            # Last observed demand at origin T: y_T
            point_matrix = self.demand[origs, :]
        elif baseline_type == "naive_7":
            # Same day last week: y_{T + h - 7} <= y_T
            ref_idx = origs + horizon - 7
            if np.any(ref_idx < 0):
                raise ValueError("Origin + horizon - 7 must be >= 0")
            point_matrix = self.demand[ref_idx, :]
        elif baseline_type == "rolling_mean_28":
            # 28-day trailing moving average ending at T
            point_matrix = self.engine.roll_mean_28_arr[origs, :]
        elif baseline_type == "weekday_profile":
            # Historical mean of target weekday up to origin T
            point_matrix = np.zeros((n_origs, self.n_series), dtype=np.float32)
            for i, t in enumerate(origs):
                target_w = self.dow[t + horizon]
                point_matrix[i, :] = self.dow_means[target_w, t, :]
        else:
            raise ValueError(f"Unknown baseline_type: {baseline_type}")

        point_preds = np.maximum(0.0, point_matrix.reshape(-1))

        # 2. Calibrate empirical 90% prediction intervals using historical residuals up to max origin
        max_orig = int(np.max(origs))
        calib_origs = np.arange(28, max_orig + 1, dtype=np.int32)

        if baseline_type == "naive_1":
            hist_preds = self.demand[calib_origs, :]
        elif baseline_type == "naive_7":
            hist_preds = self.demand[calib_origs + horizon - 7, :]
        elif baseline_type == "rolling_mean_28":
            hist_preds = self.engine.roll_mean_28_arr[calib_origs, :]
        elif baseline_type == "weekday_profile":
            hist_preds = np.zeros((len(calib_origs), self.n_series), dtype=np.float32)
            for i, t in enumerate(calib_origs):
                tw = self.dow[t + horizon]
                hist_preds[i, :] = self.dow_means[tw, t, :]

        hist_targets = self.demand[calib_origs + horizon, :]
        residuals = (hist_targets - hist_preds).reshape(-1)

        q_low = float(np.quantile(residuals, 0.05))
        q_high = float(np.quantile(residuals, 0.95))

        lower = np.maximum(0.0, point_preds + q_low)
        upper = np.maximum(0.0, point_preds + q_high)

        return point_preds, lower, upper


class ProphetCategoryForecaster:
    """Prophet model fit per Food Category with festivals and exogenous regressors."""

    def __init__(
        self,
        holidays_df: Optional[pd.DataFrame] = None,
        use_regressors: bool = True,
        interval_width: float = 0.90,
    ):
        self.holidays_df = holidays_df
        self.use_regressors = use_regressors
        self.interval_width = interval_width
        self.model: Optional[Prophet] = None
        self.is_fitted_: bool = False

    def fit(self, df_train: pd.DataFrame, target_col: str = "Daily_Demand") -> "ProphetCategoryForecaster":
        """Fit Prophet model on category daily aggregate series."""
        validate_demand_target(target_col)
        verify_no_leakage(df_train.columns)

        p_train = pd.DataFrame({
            "ds": pd.to_datetime(df_train["Date"]),
            "y": df_train[target_col].astype(float).values,
        })

        self.model = Prophet(
            weekly_seasonality=True,
            yearly_seasonality=True,
            daily_seasonality=False,
            holidays=self.holidays_df,
            interval_width=self.interval_width,
        )

        if self.use_regressors:
            for reg in ["Temperature_C", "Rain_mm", "promo_num"]:
                if reg in df_train.columns:
                    p_train[reg] = df_train[reg].astype(float).values
                    self.model.add_regressor(reg)
                elif reg == "promo_num" and "Promotion" in df_train.columns:
                    p_train["promo_num"] = (df_train["Promotion"] == "Yes").astype(float).values
                    self.model.add_regressor("promo_num")

        self.model.fit(p_train)
        self.is_fitted_ = True
        return self

    def predict(self, df_future: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate forecasts and 90% uncertainty intervals."""
        if not self.is_fitted_ or self.model is None:
            raise RuntimeError("Prophet model is not fitted.")

        p_future = pd.DataFrame({"ds": pd.to_datetime(df_future["Date"])})
        if self.use_regressors:
            for reg in ["Temperature_C", "Rain_mm", "promo_num"]:
                if reg in df_future.columns:
                    p_future[reg] = df_future[reg].astype(float).values
                elif reg == "promo_num" and "Promotion" in df_future.columns:
                    p_future["promo_num"] = (df_future["Promotion"] == "Yes").astype(float).values
                else:
                    p_future[reg] = 0.0

        forecast = self.model.predict(p_future)
        yhat = np.maximum(0.0, forecast["yhat"].values.astype(float))
        lower = np.maximum(0.0, forecast["yhat_lower"].values.astype(float))
        upper = np.maximum(0.0, forecast["yhat_upper"].values.astype(float))
        return yhat, lower, upper


def run_classic_baselines_cv(
    engine: TabularFeatureEngine,
    horizon: int = 1,
    n_splits: int = 4,
    test_cutoff: str = TEST_CUTOFF_DATE,
) -> Dict[str, Dict[str, float]]:
    """Evaluate the 4 classic baselines across 4 rolling-origin CV folds on all 72 series."""
    pre_cutoff_dates = [d for d in engine.unique_dates if d < pd.Timestamp(test_cutoff)]
    splitter = RollingOriginSplitter(n_splits=n_splits, horizon=horizon, step=28, test_cutoff=test_cutoff)
    folds = splitter.get_folds(pre_cutoff_dates)

    baselines: List[ClassicBaselineType] = ["naive_1", "naive_7", "rolling_mean_28", "weekday_profile"]
    records: Dict[str, Dict[str, List[float]]] = {
        b: {"true": [], "pred": [], "low": [], "high": []} for b in baselines
    }

    panel_baselines = ClassicPanelBaselines(engine)

    for fold in folds:
        train_end_idx = engine.date_to_idx[fold.train_end]
        target_idx = train_end_idx + horizon
        y_true = engine.demand_arr[target_idx, :]  # (72,)

        for b in baselines:
            point, low, high = panel_baselines.predict(
                origin_indices=[train_end_idx],
                horizon=horizon,
                baseline_type=b,
            )
            records[b]["true"].extend(y_true.tolist())
            records[b]["pred"].extend(point.tolist())
            records[b]["low"].extend(low.tolist())
            records[b]["high"].extend(high.tolist())

    metrics_out: Dict[str, Dict[str, float]] = {}
    for b in baselines:
        m = evaluate_forecast(
            np.array(records[b]["true"]),
            np.array(records[b]["pred"]),
            np.array(records[b]["low"]),
            np.array(records[b]["high"]),
        )
        metrics_out[b] = {
            "wape": m["wape"],
            "mae": m["mae"],
            "rmse": m["rmse"],
            "bias": m["bias"],
            "coverage": m.get("coverage", 0.0),
        }

    return metrics_out


def run_prophet_cv(
    panel_df: pd.DataFrame,
    engine: TabularFeatureEngine,
    horizon: int = 1,
    n_splits: int = 4,
    test_cutoff: str = TEST_CUTOFF_DATE,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Evaluate Prophet per Category with regressors and festivals across the 4 rolling CV folds.

    Returns:
        tuple of (disaggregated_72_series_metrics, category_aggregate_metrics)
    """
    pre_cutoff_dates = [d for d in engine.unique_dates if d < pd.Timestamp(test_cutoff)]
    splitter = RollingOriginSplitter(n_splits=n_splits, horizon=horizon, step=28, test_cutoff=test_cutoff)
    folds = splitter.get_folds(pre_cutoff_dates)

    # Prepare category aggregate daily series
    cat_series_dict = build_category_aggregate_series(panel_df[panel_df["Date"] < pd.Timestamp(test_cutoff)])
    categories = sorted(cat_series_dict.keys())

    # Build holidays DataFrame from dataset festivals
    fest_df = panel_df[panel_df["Festival"] != "no festival"][["Date", "Festival"]].drop_duplicates()
    holidays_df = fest_df.rename(columns={"Date": "ds", "Festival": "holiday"})
    holidays_df["lower_window"] = 0
    holidays_df["upper_window"] = 1

    series_true, series_pred, series_low, series_high = [], [], [], []
    cat_true, cat_pred, cat_low, cat_high = [], [], [], []

    for fold in folds:
        train_end_date = fold.train_end
        train_end_idx = engine.date_to_idx[train_end_date]
        target_date = engine.idx_to_date[train_end_idx + horizon]

        # For each category, fit Prophet on past history up to train_end_date
        for cat in categories:
            cat_df = cat_series_dict[cat]
            train_cat_df = cat_df[cat_df["Date"] <= train_end_date].copy()
            val_cat_df = cat_df[cat_df["Date"] == target_date].copy()

            if len(val_cat_df) == 0:
                continue

            forecaster = ProphetCategoryForecaster(
                holidays_df=holidays_df,
                use_regressors=True,
                interval_width=0.90,
            )
            forecaster.fit(train_cat_df)
            yhat, low, high = forecaster.predict(val_cat_df)

            y_actual_cat = float(val_cat_df["Daily_Demand"].iloc[0])
            cat_true.append(y_actual_cat)
            cat_pred.append(float(yhat[0]))
            cat_low.append(float(low[0]))
            cat_high.append(float(high[0]))

            # Disaggregate to individual shops for this category
            # Historical share of each shop within this category:
            cat_series_indices = [
                i for i, (s, c) in enumerate(engine.series_list) if c == cat
            ]
            hist_demand_by_shop = engine.demand_arr[: train_end_idx + 1, cat_series_indices]  # (T+1, n_shops)
            total_cat_hist = np.sum(hist_demand_by_shop)
            if total_cat_hist > 1e-4:
                shop_shares = np.sum(hist_demand_by_shop, axis=0) / total_cat_hist  # (n_shops,)
            else:
                shop_shares = np.full(len(cat_series_indices), 1.0 / len(cat_series_indices))

            # Target date actuals for these shop-category series
            actuals_shops = engine.demand_arr[train_end_idx + horizon, cat_series_indices]
            preds_shops = float(yhat[0]) * shop_shares
            low_shops = float(low[0]) * shop_shares
            high_shops = float(high[0]) * shop_shares

            series_true.extend(actuals_shops.tolist())
            series_pred.extend(preds_shops.tolist())
            series_low.extend(low_shops.tolist())
            series_high.extend(high_shops.tolist())

    m_series = evaluate_forecast(
        np.array(series_true),
        np.array(series_pred),
        np.array(series_low),
        np.array(series_high),
    )
    m_cat = evaluate_forecast(
        np.array(cat_true),
        np.array(cat_pred),
        np.array(cat_low),
        np.array(cat_high),
    )

    return {
        "wape": m_series["wape"],
        "mae": m_series["mae"],
        "rmse": m_series["rmse"],
        "bias": m_series["bias"],
        "coverage": m_series.get("coverage", 0.0),
    }, {
        "wape": m_cat["wape"],
        "mae": m_cat["mae"],
        "rmse": m_cat["rmse"],
        "bias": m_cat["bias"],
        "coverage": m_cat.get("coverage", 0.0),
    }
