"""Fair Tabular Demand Models (Task 2).

Implements:
1. Covariates-only models:
   - Known future covariates at T+h (calendar, promotion, weather, festival, series id, static shop attributes)
   - Origin lagged covariates at T (promotion, rain, temperature, cost, price, storage)
2. Covariates + Demand-history models:
   - All covariates above
   - Lags 1 to 28 of past demand ending at origin T
   - 7-day and 28-day rolling mean and standard deviation ending at origin T
   - Same weekday last week demand (T + h - 7, strictly <= T)
   - Group cross-series features at origin T:
     * Mean of the shop's other categories at origin T
     * Mean of the city's other shops for the same category at origin T
3. Global models across all 72 series:
   - HistGradientBoostingRegressor (loss='poisson', random_state=42)
   - LightGBM Regressor (objective='poisson', random_state=42)
   - Direct approach per horizon (h=1 and h=7)
4. Strict No-Leakage Verification:
   - Proves no feature uses target or operational data after forecast origin T.
5. 90% Prediction Intervals and evaluation metrics (WAPE, MAE, RMSE, Bias, Coverage).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

try:
    import lightgbm as lgb
except ImportError:
    lgb = None

try:
    from ml_service.data.synthetic_panel import load_synthetic_panel, validate_demand_target
    from ml_service.data.time_series_splits import (
        FINAL_TEST_DAYS,
        LEAKAGE_COLUMNS,
        TEST_CUTOFF_DATE,
        RollingOriginSplitter,
        split_train_test,
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
    import sys
    base_dir = str(Path(__file__).resolve().parent.parent)
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    from data.synthetic_panel import load_synthetic_panel, validate_demand_target
    from data.time_series_splits import (
        FINAL_TEST_DAYS,
        LEAKAGE_COLUMNS,
        TEST_CUTOFF_DATE,
        RollingOriginSplitter,
        split_train_test,
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


class TabularFeatureEngine:
    """Pre-computes panel matrices and constructs fully vectorized sample matrices."""

    def __init__(self, df: pd.DataFrame):
        validate_demand_target("Daily_Demand")
        self.df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(self.df["Date"]):
            self.df["Date"] = pd.to_datetime(self.df["Date"])
        self.df = self.df.sort_values(["Shop_ID", "Food_Category", "Date"]).reset_index(drop=True)

        # Unique date lookups
        self.unique_dates = [pd.Timestamp(d) for d in sorted(self.df["Date"].unique())]
        self.n_dates = len(self.unique_dates)
        self.date_to_idx = {d: i for i, d in enumerate(self.unique_dates)}
        self.idx_to_date = {i: d for i, d in enumerate(self.unique_dates)}

        # Static shop / series metadata (exactly 72 unique series)
        self.series_meta = self.df.groupby(["Shop_ID", "Food_Category"])[
            ["City", "Business_Type", "Latitude", "Longitude", "Shelf_Life_Days", "Lead_Time_Days"]
        ].first()
        self.series_list = list(self.series_meta.index)
        self.n_series = len(self.series_list)

        # Categorical vocabulary encodings (fixed deterministic integer codes)
        self.cat_vocabs: Dict[str, Dict[str, int]] = {
            "Shop_ID": {s: i for i, s in enumerate(sorted(self.df["Shop_ID"].unique()))},
            "Food_Category": {c: i for i, c in enumerate(sorted(self.df["Food_Category"].unique()))},
            "City": {c: i for i, c in enumerate(sorted(self.df["City"].unique()))},
            "Business_Type": {b: i for i, b in enumerate(sorted(self.df["Business_Type"].unique()))},
            "Weather": {w: i for i, w in enumerate(["Sunny", "Cloudy", "Hot", "Rainy"])},
            "Festival": {f: i for i, f in enumerate(sorted(self.df["Festival"].fillna("no festival").unique()))},
        }

        # Precompute static feature matrix for all 72 series (shape: [72, n_static])
        static_rows = []
        for (shop, cat) in self.series_list:
            meta = self.series_meta.loc[(shop, cat)]
            city = str(meta["City"])
            b_type = str(meta["Business_Type"])
            static_rows.append([
                float(self.cat_vocabs["Shop_ID"][shop]),
                float(self.cat_vocabs["Food_Category"][cat]),
                float(self.cat_vocabs["City"][city]),
                float(self.cat_vocabs["Business_Type"][b_type]),
                float(meta["Shelf_Life_Days"]),
                float(meta["Lead_Time_Days"]),
            ])
        self.static_features_72 = np.array(static_rows, dtype=np.float32)  # [72, 6]
        self.static_col_names = ["shop_code", "cat_code", "city_code", "btype_code", "shelf_life", "lead_time"]

        # 2D Panel Matrices: index=Date (1096), columns=(Shop_ID, Food_Category) (72)
        piv_d = self.df.pivot_table(index="Date", columns=["Shop_ID", "Food_Category"], values="Daily_Demand")
        piv_pr = (self.df.pivot_table(index="Date", columns=["Shop_ID", "Food_Category"], values="Promotion", aggfunc="first") == "Yes").astype(float)
        piv_rn = self.df.pivot_table(index="Date", columns=["Shop_ID", "Food_Category"], values="Rain_mm")
        piv_tp = self.df.pivot_table(index="Date", columns=["Shop_ID", "Food_Category"], values="Temperature_C")
        piv_wt = self.df.pivot_table(index="Date", columns=["Shop_ID", "Food_Category"], values="Weather", aggfunc="first")
        piv_fs = self.df.pivot_table(index="Date", columns=["Shop_ID", "Food_Category"], values="Festival", aggfunc="first").fillna("no festival")
        piv_st = self.df.pivot_table(index="Date", columns=["Shop_ID", "Food_Category"], values="Storage_Temperature")
        piv_cs = self.df.pivot_table(index="Date", columns=["Shop_ID", "Food_Category"], values="Unit_Cost_INR")
        piv_pc = self.df.pivot_table(index="Date", columns=["Shop_ID", "Food_Category"], values="Unit_Price_INR")

        # Map weather and festival to integer codes
        wt_codes = piv_wt.map(lambda x: float(self.cat_vocabs["Weather"].get(x, 0)))
        fs_codes = piv_fs.map(lambda x: float(self.cat_vocabs["Festival"].get(x, 0)))

        self.demand_arr = piv_d.values.astype(np.float32)  # [1096, 72]
        self.promo_arr = piv_pr.values.astype(np.float32)
        self.rain_arr = piv_rn.values.astype(np.float32)
        self.temp_arr = piv_tp.values.astype(np.float32)
        self.weather_arr = wt_codes.values.astype(np.float32)
        self.fest_arr = fs_codes.values.astype(np.float32)
        self.storage_arr = piv_st.values.astype(np.float32)
        self.cost_arr = piv_cs.values.astype(np.float32)
        self.price_arr = piv_pc.values.astype(np.float32)

        # Rolling demand matrices
        self.roll_mean_7_arr = piv_d.rolling(7, min_periods=1).mean().values.astype(np.float32)
        self.roll_std_7_arr = piv_d.rolling(7, min_periods=1).std().fillna(0.0).values.astype(np.float32)
        self.roll_mean_28_arr = piv_d.rolling(28, min_periods=1).mean().values.astype(np.float32)
        self.roll_std_28_arr = piv_d.rolling(28, min_periods=1).std().fillna(0.0).values.astype(np.float32)

        # Group cross-series features at date T:
        # 1. Shop other categories mean (sum across 6 categories - own category) / 5
        shop_totals = piv_d.T.groupby(level="Shop_ID").sum().T
        shop_other_cats = pd.DataFrame(index=piv_d.index, columns=piv_d.columns, dtype=float)
        for (shop, cat) in piv_d.columns:
            shop_other_cats[(shop, cat)] = (shop_totals[shop] - piv_d[(shop, cat)]) / 5.0
        self.shop_other_cats_arr = shop_other_cats.values.astype(np.float32)

        # 2. City other shops mean for the same category: (city_cat_total - own shop) / (city_shop_count - 1)
        shop_to_city = self.df[["Shop_ID", "City"]].drop_duplicates().set_index("Shop_ID")["City"].to_dict()
        city_shop_count = self.df.groupby("City")["Shop_ID"].nunique().to_dict()
        city_cat_totals = piv_d.T.groupby([
            piv_d.columns.get_level_values("Shop_ID").map(shop_to_city),
            piv_d.columns.get_level_values("Food_Category"),
        ]).sum().T
        city_other_shops = pd.DataFrame(index=piv_d.index, columns=piv_d.columns, dtype=float)
        for (shop, cat) in piv_d.columns:
            city = shop_to_city[shop]
            n_other = city_shop_count[city] - 1
            city_other_shops[(shop, cat)] = (city_cat_totals[(city, cat)] - piv_d[(shop, cat)]) / n_other
        self.city_other_shops_arr = city_other_shops.values.astype(np.float32)

        # Precompute calendar arrays for all 1096 dates
        doy = np.array([d.dayofyear for d in self.unique_dates], dtype=np.float32)
        dow = np.array([d.dayofweek for d in self.unique_dates], dtype=np.float32)
        is_wknd = np.array([1.0 if d.dayofweek in (5, 6) else 0.0 for d in self.unique_dates], dtype=np.float32)
        self.cal_sin_doy = np.sin(2.0 * np.pi * doy / 365.25).astype(np.float32)
        self.cal_cos_doy = np.cos(2.0 * np.pi * doy / 365.25).astype(np.float32)
        self.cal_dow = dow
        self.cal_is_weekend = is_wknd

    def build_dataset_vectorized(
        self,
        origin_indices: Sequence[int],
        horizon: int,
        include_history: bool = True,
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """Construct full feature matrix and target vector for specified origins and horizon.

        Args:
            origin_indices: Array-like of integer date indices representing forecast origins T.
            horizon: Future step h in days (e.g. 1 or 7).
            include_history: True for Covariates + Demand History; False for Covariates Only.

        Returns:
            X_df: pd.DataFrame of features (length: len(origin_indices) * 72).
            y_series: pd.Series of target demand values.
        """
        origs = np.asarray(origin_indices, dtype=np.int32)
        targets = origs + horizon
        n_orig = len(origs)
        total_samples = n_orig * self.n_series

        # Verify bounds
        if np.any(targets >= self.n_dates):
            raise ValueError(f"Target index exceeds total dates ({self.n_dates}).")
        if include_history and np.any(origs < 27):
            raise ValueError("Origin index must be >= 27 to supply 28 days of past demand lags.")

        # 1. Targets y at T + h
        y_vals = self.demand_arr[targets, :].reshape(-1)

        # 2. Known future covariates at T + h
        promo_fut = self.promo_arr[targets, :].reshape(-1, 1)
        rain_fut = self.rain_arr[targets, :].reshape(-1, 1)
        temp_fut = self.temp_arr[targets, :].reshape(-1, 1)
        weather_fut = self.weather_arr[targets, :].reshape(-1, 1)
        fest_fut = self.fest_arr[targets, :].reshape(-1, 1)

        # Calendar features for target dates (expanded to all 72 series per origin)
        dow_fut = np.repeat(self.cal_dow[targets], self.n_series).reshape(-1, 1)
        wknd_fut = np.repeat(self.cal_is_weekend[targets], self.n_series).reshape(-1, 1)
        sin_doy_fut = np.repeat(self.cal_sin_doy[targets], self.n_series).reshape(-1, 1)
        cos_doy_fut = np.repeat(self.cal_cos_doy[targets], self.n_series).reshape(-1, 1)

        # Static series features repeated across all origins: [total_samples, 6]
        static_block = np.tile(self.static_features_72, (n_orig, 1))

        # Origin lagged covariates at T:
        promo_orig = self.promo_arr[origs, :].reshape(-1, 1)
        rain_orig = self.rain_arr[origs, :].reshape(-1, 1)
        temp_orig = self.temp_arr[origs, :].reshape(-1, 1)
        storage_orig = self.storage_arr[origs, :].reshape(-1, 1)
        cost_orig = self.cost_arr[origs, :].reshape(-1, 1)
        price_orig = self.price_arr[origs, :].reshape(-1, 1)

        cov_parts = [
            static_block,
            dow_fut,
            wknd_fut,
            sin_doy_fut,
            cos_doy_fut,
            promo_fut,
            rain_fut,
            temp_fut,
            weather_fut,
            fest_fut,
            promo_orig,
            rain_orig,
            temp_orig,
            storage_orig,
            cost_orig,
            price_orig,
        ]
        cov_names = (
            self.static_col_names
            + ["dow", "is_weekend", "sin_doy", "cos_doy"]
            + ["promo_future", "rain_future", "temp_future", "weather_code", "fest_code"]
            + ["promo_origin", "rain_origin", "temp_origin", "storage_origin", "unit_cost", "unit_price"]
        )

        if include_history:
            # 28 Demand Lags: lag 1 is demand at T, lag 2 is T-1, ..., lag 28 is T-27
            lag_blocks = []
            lag_names = []
            for lag in range(1, 29):
                l_orig = origs - (lag - 1)
                lag_blocks.append(self.demand_arr[l_orig, :].reshape(-1, 1))
                lag_names.append(f"demand_lag_{lag}")

            # Rolling stats ending at origin T
            rm7 = self.roll_mean_7_arr[origs, :].reshape(-1, 1)
            rs7 = self.roll_std_7_arr[origs, :].reshape(-1, 1)
            rm28 = self.roll_mean_28_arr[origs, :].reshape(-1, 1)
            rs28 = self.roll_std_28_arr[origs, :].reshape(-1, 1)

            # Same weekday last week: date (T + h - 7). Guaranteed strictly <= T for h in 1..7.
            same_dow_idx = targets - 7
            if np.any(same_dow_idx > origs):
                raise RuntimeError("Leakage invariant violated: same_weekday_last_week date > origin date.")
            same_dow = self.demand_arr[same_dow_idx, :].reshape(-1, 1)

            # Cross-series group features at origin T
            shop_other = self.shop_other_cats_arr[origs, :].reshape(-1, 1)
            city_other = self.city_other_shops_arr[origs, :].reshape(-1, 1)

            hist_parts = (
                lag_blocks
                + [rm7, rs7, rm28, rs28]
                + [same_dow, shop_other, city_other]
            )
            hist_names = (
                lag_names
                + ["rolling_mean_7", "rolling_std_7", "rolling_mean_28", "rolling_std_28"]
                + ["same_weekday_last_week", "shop_other_cats_mean", "city_other_shops_mean"]
            )

            all_parts = cov_parts + hist_parts
            all_names = cov_names + hist_names
        else:
            all_parts = cov_parts
            all_names = cov_names

        X_mat = np.hstack(all_parts)
        X_df = pd.DataFrame(X_mat, columns=all_names)
        y_ser = pd.Series(y_vals, name="Daily_Demand")
        return X_df, y_ser


class FairTabularForecaster:
    """Direct global forecaster for horizon h using Poisson loss."""

    def __init__(
        self,
        model_type: Literal["lightgbm", "hist_gradient_boosting"] = "lightgbm",
        include_history: bool = True,
        random_state: int = 42,
    ):
        self.model_type = model_type
        self.include_history = include_history
        self.random_state = random_state
        self.fitted_ = False
        self.residual_quantiles_: Tuple[float, float] = (0.0, 0.0)

        self.cat_cols = ["shop_code", "cat_code", "city_code", "btype_code", "weather_code", "fest_code"]

        if self.model_type == "lightgbm":
            if lgb is None:
                raise ImportError("lightgbm is not installed. Please use 'hist_gradient_boosting'.")
            self.model = lgb.LGBMRegressor(
                objective="poisson",
                random_state=self.random_state,
                n_estimators=160,
                learning_rate=0.08,
                num_leaves=31,
                min_child_samples=20,
                subsample=0.9,
                colsample_bytree=0.9,
                verbose=-1,
                n_jobs=-1,
            )
        elif self.model_type == "hist_gradient_boosting":
            self.model = HistGradientBoostingRegressor(
                loss="poisson",
                random_state=self.random_state,
                max_iter=160,
                learning_rate=0.08,
                max_leaf_nodes=31,
                min_samples_leaf=20,
                categorical_features=self.cat_cols,
            )
        else:
            raise ValueError(f"Unknown model_type '{self.model_type}'")

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "FairTabularForecaster":
        """Fit model and calibrate 90% prediction intervals."""
        verify_no_leakage(X.columns)

        if self.model_type == "lightgbm":
            X_in = X.copy()
            for col in self.cat_cols:
                if col in X_in.columns:
                    X_in[col] = X_in[col].astype("category")
            self.model.fit(X_in, y)
            preds = self.model.predict(X_in)
        else:
            self.model.fit(X, y)
            preds = self.model.predict(X)

        preds = np.maximum(0.0, preds)
        residuals = y.values - preds
        q_low = float(np.quantile(residuals, 0.05))
        q_high = float(np.quantile(residuals, 0.95))
        self.residual_quantiles_ = (q_low, q_high)
        self.feature_names_ = list(X.columns)
        self.fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict point demand forecasts."""
        if not self.fitted_:
            raise RuntimeError("Model is not fitted.")
        verify_no_leakage(X.columns)

        if self.model_type == "lightgbm":
            X_in = X.copy()
            for col in self.cat_cols:
                if col in X_in.columns:
                    X_in[col] = X_in[col].astype("category")
            raw_preds = self.model.predict(X_in)
        else:
            raw_preds = self.model.predict(X)

        return np.maximum(0.0, raw_preds)

    def predict_interval(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Predict lower and upper bounds of 90% prediction interval."""
        point_preds = self.predict(X)
        q_low, q_high = self.residual_quantiles_
        lower = np.maximum(0.0, point_preds + q_low)
        upper = np.maximum(0.0, point_preds + q_high)
        return lower, upper


def run_tabular_rolling_cv(
    engine: TabularFeatureEngine,
    horizon: int = 1,
    include_history: bool = True,
    model_type: Literal["lightgbm", "hist_gradient_boosting"] = "lightgbm",
    n_splits: int = 4,
    test_cutoff: str = TEST_CUTOFF_DATE,
) -> Dict[str, Any]:
    """Run rolling-origin cross-validation on pre-cutoff data for direct horizon h."""
    pre_cutoff_dates = [d for d in engine.unique_dates if d < pd.Timestamp(test_cutoff)]
    splitter = RollingOriginSplitter(n_splits=n_splits, horizon=horizon, step=28, test_cutoff=test_cutoff)
    folds = splitter.get_folds(pre_cutoff_dates)

    fold_metrics: List[Dict[str, float]] = []
    all_y_true: List[float] = []
    all_y_pred: List[float] = []
    all_y_low: List[float] = []
    all_y_high: List[float] = []

    for fold in folds:
        train_end_idx = engine.date_to_idx[fold.train_end]
        # Train origins: from index 28 up to train_end_idx - horizon
        train_origins = np.arange(28, train_end_idx - horizon + 1, dtype=np.int32)

        X_train, y_train = engine.build_dataset_vectorized(
            origin_indices=train_origins,
            horizon=horizon,
            include_history=include_history,
        )

        model = FairTabularForecaster(
            model_type=model_type,
            include_history=include_history,
            random_state=42,
        )
        model.fit(X_train, y_train)

        # Validation origin is fold.train_end
        val_origin_idx = np.array([train_end_idx], dtype=np.int32)
        X_val, y_val = engine.build_dataset_vectorized(
            origin_indices=val_origin_idx,
            horizon=horizon,
            include_history=include_history,
        )

        preds = model.predict(X_val)
        low, high = model.predict_interval(X_val)

        m = evaluate_forecast(y_val.values, preds, low, high)
        fold_metrics.append({
            "fold": fold.fold_idx,
            "wape": m["wape"],
            "mae": m["mae"],
            "rmse": m["rmse"],
            "bias": m["bias"],
            "coverage_90": m.get("coverage", 0.0),
        })

        all_y_true.extend(y_val.values.tolist())
        all_y_pred.extend(preds.tolist())
        all_y_low.extend(low.tolist())
        all_y_high.extend(high.tolist())

    overall_metrics = evaluate_forecast(
        np.array(all_y_true),
        np.array(all_y_pred),
        np.array(all_y_low),
        np.array(all_y_high),
    )

    return {
        "model_type": model_type,
        "include_history": include_history,
        "horizon": horizon,
        "fold_metrics": fold_metrics,
        "overall": overall_metrics,
    }
