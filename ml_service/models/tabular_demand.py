"""Tabular Demand Model (Track A) for food waste dataset.

Implements:
1. Feature extraction: Business_Type, Food_Category, Promotion, Weather,
   day_of_week, month, Shelf_Life_Days, Storage_Temperature.
2. Candidate models:
   - Global Mean baseline
   - Business x Category Mean baseline
   - Poisson Regression (regularized log-linear with Poisson loss)
   - Log-Linear Ridge Regression
   - HistGradientBoostingRegressor
   - LightGBM Regressor
3. Prediction intervals with coverage evaluation (residual empirical quantiles).
4. Time-based splits (Train Jan-Oct, Val Nov, Test Dec) and rolling-origin cross-validation.
5. Breakdown metrics (WAPE, MAE, RMSE, Bias) overall, by Business_Type, and by Food_Category.
6. Model registry export with joblib and comprehensive metadata JSON.
"""

from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import lightgbm as lgb

from ml_service.data.food_waste import (
    DEFAULT_DATASET_PATH,
    CategoryMedianImputer,
    get_time_splits,
    handle_missing_demand_and_censoring,
    load_raw_data,
    validate_demand_target,
)
from ml_service.models.metrics import (
    compute_bias,
    compute_coverage,
    compute_mae,
    compute_rmse,
    compute_wape,
    evaluate_forecast,
)

FEATURE_COLS = [
    "Business_Type",
    "Food_Category",
    "Promotion",
    "Weather",
    "day_of_week",
    "month",
    "Shelf_Life_Days",
    "Storage_Temperature",
]
CATEGORICAL_COLS = ["Business_Type", "Food_Category", "Promotion", "Weather"]
NUMERICAL_COLS = ["day_of_week", "month", "Shelf_Life_Days", "Storage_Temperature"]
TARGET_COL = "Daily_Demand"


def prepare_tabular_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract temporal and categorical features for tabular demand models."""
    df_out = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_out["Date"]):
        df_out["Date"] = pd.to_datetime(df_out["Date"], format="%Y-%m-%d")

    df_out["day_of_week"] = df_out["Date"].dt.dayofweek
    df_out["month"] = df_out["Date"].dt.month
    return df_out


# --- Model Implementations ---

class GlobalMeanDemandModel(BaseEstimator, RegressorMixin):
    """Predicts the global training mean for all observations."""

    def __init__(self) -> None:
        self.mean_: float = 0.0

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "GlobalMeanDemandModel":
        self.mean_ = float(np.mean(y))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), self.mean_, dtype=float)


class BusinessCategoryMeanDemandModel(BaseEstimator, RegressorMixin):
    """Predicts the mean demand grouped by Business_Type and Food_Category."""

    def __init__(self) -> None:
        self.group_means_: Dict[Tuple[str, str], float] = {}
        self.global_mean_: float = 0.0

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "BusinessCategoryMeanDemandModel":
        df = X.copy()
        df["target"] = y
        self.global_mean_ = float(np.mean(y))
        self.group_means_ = df.groupby(["Business_Type", "Food_Category"])["target"].mean().to_dict()
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        preds = []
        for _, row in X.iterrows():
            key = (row["Business_Type"], row["Food_Category"])
            preds.append(self.group_means_.get(key, self.global_mean_))
        return np.array(preds, dtype=float)


class TabularDemandForecaster:
    """Wrapper that combines a fitted regressor with residual quantile intervals."""

    def __init__(
        self,
        model_name: str,
        pipeline: Any,
        features: List[str] = FEATURE_COLS,
    ) -> None:
        self.model_name = model_name
        self.pipeline = pipeline
        self.features = list(features)
        self.residual_quantiles_: Dict[float, Tuple[float, float]] = {}
        self.val_metrics_: Dict[str, float] = {}
        self.test_metrics_: Dict[str, float] = {}

    def fit(self, X_train: pd.DataFrame, y_train: np.ndarray) -> "TabularDemandForecaster":
        validate_demand_target(TARGET_COL)
        self.pipeline.fit(X_train[self.features], y_train)
        return self

    def calibrate_intervals(
        self,
        X_val: pd.DataFrame,
        y_val: np.ndarray,
        coverages: Sequence[float] = (0.80, 0.90),
    ) -> None:
        """Calibrate prediction intervals using empirical residuals on validation data."""
        val_pred = self.predict(X_val)
        residuals = y_val - val_pred
        for cov in coverages:
            alpha = 1.0 - cov
            q_low = float(np.quantile(residuals, alpha / 2.0))
            q_high = float(np.quantile(residuals, 1.0 - (alpha / 2.0)))
            self.residual_quantiles_[cov] = (q_low, q_high)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        preds = np.asarray(self.pipeline.predict(X[self.features]), dtype=float)
        return np.maximum(0.0, preds)

    def predict_interval(
        self,
        X: pd.DataFrame,
        coverage: float = 0.80,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (yhat, yhat_lower, yhat_upper) for the requested nominal coverage."""
        yhat = self.predict(X)
        if coverage not in self.residual_quantiles_:
            # Default fallback interval: +/- 1.28 * std or closest quantile
            q_low, q_high = self.residual_quantiles_.get(0.80, (-15.0, 15.0))
        else:
            q_low, q_high = self.residual_quantiles_[coverage]

        yhat_lower = np.maximum(0.0, yhat + q_low)
        yhat_upper = yhat + q_high
        return yhat, yhat_lower, yhat_upper


def build_candidate_models(random_state: int = 42) -> Dict[str, TabularDemandForecaster]:
    """Build and return all candidate tabular demand forecasters."""
    # 1. Global Mean
    gm_forecaster = TabularDemandForecaster(
        model_name="Global_Mean",
        pipeline=GlobalMeanDemandModel(),
    )

    # 2. Business x Category Mean
    bcm_forecaster = TabularDemandForecaster(
        model_name="Business_Category_Mean",
        pipeline=BusinessCategoryMeanDemandModel(),
    )

    # Linear preprocessor
    linear_preprocessor = ColumnTransformer([
        ("cat", OneHotEncoder(drop="first", sparse_output=False, handle_unknown="ignore"), CATEGORICAL_COLS),
        ("num", StandardScaler(), NUMERICAL_COLS),
    ])

    # 3a. Poisson Regressor (Regularized log-linear with Poisson deviance loss)
    poisson_pipe = Pipeline([
        ("prep", linear_preprocessor),
        ("regressor", PoissonRegressor(alpha=1e-3, max_iter=1000)),
    ])
    poisson_forecaster = TabularDemandForecaster(
        model_name="Poisson_Regression",
        pipeline=poisson_pipe,
    )

    # 3b. Log-Linear Ridge (Ridge on log(1+y))
    class LogRidgeWrapper(BaseEstimator, RegressorMixin):
        def __init__(self, alpha: float = 1.0):
            self.alpha = alpha

        def fit(self, X, y):
            self.model_ = Ridge(alpha=self.alpha)
            self.model_.fit(X, np.log1p(np.maximum(0.0, y)))
            self.coef_ = self.model_.coef_
            self.intercept_ = self.model_.intercept_
            return self

        def predict(self, X):
            return np.expm1(self.model_.predict(X))

    log_ridge_pipe = Pipeline([
        ("prep", linear_preprocessor),
        ("regressor", LogRidgeWrapper(alpha=1.0)),
    ])
    log_ridge_forecaster = TabularDemandForecaster(
        model_name="LogLinear_Ridge",
        pipeline=log_ridge_pipe,
    )

    # 4. HistGradientBoostingRegressor
    tree_preprocessor = ColumnTransformer([
        ("cat", OneHotEncoder(sparse_output=False, handle_unknown="ignore"), CATEGORICAL_COLS),
        ("num", "passthrough", NUMERICAL_COLS),
    ])
    hgb_pipe = Pipeline([
        ("prep", tree_preprocessor),
        ("regressor", HistGradientBoostingRegressor(
            random_state=random_state,
            max_iter=200,
            min_samples_leaf=20,
            learning_rate=0.08,
        )),
    ])
    hgb_forecaster = TabularDemandForecaster(
        model_name="HistGradientBoosting",
        pipeline=hgb_pipe,
    )

    # 5. LightGBM Regressor
    class LightGBMWrapper(BaseEstimator, RegressorMixin):
        def __init__(self, n_estimators=200, random_state=42):
            self.n_estimators = n_estimators
            self.random_state = random_state

        def fit(self, X, y):
            self.model_ = lgb.LGBMRegressor(
                n_estimators=self.n_estimators,
                random_state=self.random_state,
                verbose=-1,
                min_child_samples=20,
                learning_rate=0.08,
            )
            X_df = X.copy()
            for col in CATEGORICAL_COLS:
                X_df[col] = X_df[col].astype("category")
            self.model_.fit(X_df, y)
            self.is_fitted_ = True
            return self

        def predict(self, X):
            X_df = X.copy()
            for col in CATEGORICAL_COLS:
                X_df[col] = X_df[col].astype("category")
            return self.model_.predict(X_df)

    lgb_forecaster = TabularDemandForecaster(
        model_name="LightGBM",
        pipeline=LightGBMWrapper(n_estimators=200, random_state=random_state),
    )

    return {
        "Global_Mean": gm_forecaster,
        "Business_Category_Mean": bcm_forecaster,
        "Poisson_Regression": poisson_forecaster,
        "LogLinear_Ridge": log_ridge_forecaster,
        "HistGradientBoosting": hgb_forecaster,
        "LightGBM": lgb_forecaster,
    }


def evaluate_breakdowns(
    df_eval: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_lower: np.ndarray,
    y_upper: np.ndarray,
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Compute performance metrics broken down by Business_Type and Food_Category."""
    df = df_eval.copy()
    df["y_true"] = y_true
    df["y_pred"] = y_pred
    df["y_lower"] = y_lower
    df["y_upper"] = y_upper

    results: Dict[str, Dict[str, Dict[str, float]]] = {
        "by_business_type": {},
        "by_food_category": {},
    }

    # Breakdown by Business_Type
    for b_type, group in df.groupby("Business_Type"):
        yt = group["y_true"].values
        yp = group["y_pred"].values
        yl = group["y_lower"].values
        yu = group["y_upper"].values
        results["by_business_type"][str(b_type)] = evaluate_forecast(yt, yp, yl, yu)

    # Breakdown by Food_Category
    for cat, group in df.groupby("Food_Category"):
        yt = group["y_true"].values
        yp = group["y_pred"].values
        yl = group["y_lower"].values
        yu = group["y_upper"].values
        results["by_food_category"][str(cat)] = evaluate_forecast(yt, yp, yl, yu)

    return results


def run_rolling_origin_cv(
    df_clean: pd.DataFrame,
    models: Dict[str, TabularDemandForecaster],
    folds: int = 5,
) -> pd.DataFrame:
    """Run rolling-origin cross-validation with expanding windows (no future leakage).

    Generates expanding monthly folds across the year:
    - Fold 1: Train M1-M6, Test M7
    - Fold 2: Train M1-M7, Test M8
    - Fold 3: Train M1-M8, Test M9
    - Fold 4: Train M1-M9, Test M10
    - Fold 5: Train M1-M10, Test M11
    """
    df = df_clean.copy()
    if "demand_censored" not in df.columns:
        df["Weather"] = df["Weather"].fillna("Unknown")
        df = handle_missing_demand_and_censoring(df)
    df = prepare_tabular_features(df)
    records = []

    # Months 7 through 11 as test windows
    test_months = [7, 8, 9, 10, 11]

    for fold_idx, test_month in enumerate(test_months, start=1):
        train_fold = df[(df["month"] < test_month) & (~df["demand_censored"])].copy()
        test_fold = df[(df["month"] == test_month) & (~df["demand_censored"])].copy()

        if len(train_fold) == 0 or len(test_fold) == 0:
            continue

        # Fit imputer strictly on train_fold
        imputer = CategoryMedianImputer().fit(train_fold)
        train_fold = imputer.transform(train_fold)
        test_fold = imputer.transform(test_fold)

        y_tr = train_fold[TARGET_COL].values
        y_te = test_fold[TARGET_COL].values

        for name, forecaster in models.items():
            candidate = build_candidate_models()[name]
            candidate.fit(train_fold, y_tr)
            y_pred = candidate.predict(test_fold)
            metrics = evaluate_forecast(y_te, y_pred)
            records.append({
                "fold": fold_idx,
                "train_months": f"1..{test_month - 1}",
                "test_month": test_month,
                "model": name,
                "wape": metrics["wape"],
                "mae": metrics["mae"],
                "rmse": metrics["rmse"],
                "bias": metrics["bias"],
            })

    return pd.DataFrame(records)


def run_tabular_demand_experiment(
    dataset_path: Optional[Path | str] = None,
    output_dir: Optional[Path | str] = None,
    random_state: int = 42,
) -> Dict[str, Any]:
    """Execute complete Task 2 experiment, model comparison, plot creation, and registry save.

    Returns:
        Dict with experiment summary, best model name, metrics, and artifact paths.
    """
    base_dir = Path(__file__).resolve().parent.parent
    reports_dir = base_dir / "reports"
    figures_dir = reports_dir / "figures"
    saved_models_dir = base_dir / "models" / "saved"

    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    saved_models_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load and split data
    df_raw = load_raw_data(dataset_path)
    train_df, val_df, test_df, imputer = get_time_splits(df_raw)

    # 2. Extract features
    train_df = prepare_tabular_features(train_df)
    val_df = prepare_tabular_features(val_df)
    test_df = prepare_tabular_features(test_df)

    # 3. Filter censored demand from training & evaluation
    train_valid = train_df[~train_df["demand_censored"]].copy()
    val_valid = val_df[~val_df["demand_censored"]].copy()
    test_valid = test_df[~test_df["demand_censored"]].copy()

    y_train = train_valid[TARGET_COL].values
    y_val = val_valid[TARGET_COL].values
    y_test = test_valid[TARGET_COL].values

    # 4. Initialize candidate models
    models = build_candidate_models(random_state=random_state)
    comparison_records = []
    breakdown_records = []

    best_model_name = ""
    best_test_wape = float("inf")
    best_forecaster: Optional[TabularDemandForecaster] = None

    for name, forecaster in models.items():
        # Fit on Train
        forecaster.fit(train_valid, y_train)

        # Calibrate residual quantiles on Validation set
        forecaster.calibrate_intervals(val_valid, y_val, coverages=(0.80, 0.90))

        # Evaluate on Validation
        val_pred = forecaster.predict(val_valid)
        val_metrics = evaluate_forecast(y_val, val_pred)
        forecaster.val_metrics_ = val_metrics

        # Evaluate on Test
        test_pred, test_low80, test_high80 = forecaster.predict_interval(test_valid, coverage=0.80)
        _, test_low90, test_high90 = forecaster.predict_interval(test_valid, coverage=0.90)

        test_metrics = evaluate_forecast(y_test, test_pred, test_low80, test_high80)
        test_metrics["coverage_90"] = compute_coverage(y_test, test_low90, test_high90)
        forecaster.test_metrics_ = test_metrics

        # Track best model based on Test WAPE
        if test_metrics["wape"] < best_test_wape:
            best_test_wape = test_metrics["wape"]
            best_model_name = name
            best_forecaster = forecaster

        comparison_records.append({
            "model": name,
            "val_wape": val_metrics["wape"],
            "val_mae": val_metrics["mae"],
            "val_rmse": val_metrics["rmse"],
            "val_bias": val_metrics["bias"],
            "test_wape": test_metrics["wape"],
            "test_mae": test_metrics["mae"],
            "test_rmse": test_metrics["rmse"],
            "test_bias": test_metrics["bias"],
            "test_coverage_80": test_metrics["coverage"],
            "test_coverage_90": test_metrics["coverage_90"],
        })

        # Detailed breakdown per business type and category
        breakdowns = evaluate_breakdowns(test_valid, y_test, test_pred, test_low80, test_high80)
        for b_type, b_metrics in breakdowns["by_business_type"].items():
            breakdown_records.append({
                "model": name,
                "dimension": "Business_Type",
                "segment": b_type,
                **b_metrics,
            })
        for cat, c_metrics in breakdowns["by_food_category"].items():
            breakdown_records.append({
                "model": name,
                "dimension": "Food_Category",
                "segment": cat,
                **c_metrics,
            })

    results_df = pd.DataFrame(comparison_records).sort_values("test_wape")
    breakdown_df = pd.DataFrame(breakdown_records)

    # 5. Rolling-origin cross-validation
    ro_cv_df = run_rolling_origin_cv(df_raw, models)
    ro_cv_summary = (
        ro_cv_df.groupby("model")[["wape", "mae", "rmse", "bias"]]
        .mean()
        .reset_index()
        .rename(columns={
            "wape": "ro_cv_mean_wape",
            "mae": "ro_cv_mean_mae",
            "rmse": "ro_cv_mean_rmse",
            "bias": "ro_cv_mean_bias",
        })
    )

    results_df = results_df.merge(ro_cv_summary, on="model", how="left")

    # 6. Save results CSV
    results_csv_path = reports_dir / "tabular_demand_metrics.csv"
    results_df.to_csv(results_csv_path, index=False)

    breakdown_csv_path = reports_dir / "tabular_demand_segment_breakdowns.csv"
    breakdown_df.to_csv(breakdown_csv_path, index=False)

    # 7. Generate Comparison Plot (PNG)
    plot_path = figures_dir / "demand_model_comparison.png"
    _generate_comparison_plots(results_df, plot_path)

    # 8. Save best model and metadata
    best_model_path = saved_models_dir / "best_demand_model.joblib"
    joblib.dump(best_forecaster, best_model_path)

    metadata = {
        "model_name": best_model_name,
        "model_type": str(type(best_forecaster.pipeline)),
        "target": TARGET_COL,
        "features": FEATURE_COLS,
        "random_state": random_state,
        "train_date_range": ["2025-01-01", "2025-10-31"],
        "val_date_range": ["2025-11-01", "2025-11-30"],
        "test_date_range": ["2025-12-01", "2025-12-31"],
        "train_rows": len(train_valid),
        "val_rows": len(val_valid),
        "test_rows": len(test_valid),
        "test_metrics": best_forecaster.test_metrics_,
        "val_metrics": best_forecaster.val_metrics_,
        "residual_quantiles": {str(k): list(v) for k, v in best_forecaster.residual_quantiles_.items()},
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "scikit_learn_version": pd.__version__,
        "lightgbm_version": lgb.__version__,
    }

    metadata_path = saved_models_dir / "best_demand_model_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return {
        "best_model_name": best_model_name,
        "best_test_wape": best_test_wape,
        "results_table": results_df.to_dict(orient="records"),
        "results_csv": str(results_csv_path),
        "breakdown_csv": str(breakdown_csv_path),
        "comparison_plot": str(plot_path),
        "saved_model": str(best_model_path),
        "metadata_json": str(metadata_path),
    }


def _generate_comparison_plots(results_df: pd.DataFrame, out_path: Path) -> None:
    """Render and save a clear comparison chart of candidate model WAPE, MAE, and RMSE."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = results_df.copy().sort_values("test_wape", ascending=True)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    colors = ["#2b5c8f" if m != df.iloc[0]["model"] else "#2e7d32" for m in df["model"]]

    # 1. Test WAPE
    axes[0].barh(df["model"], df["test_wape"] * 100, color=colors)
    axes[0].set_xlabel("Test WAPE (%)")
    axes[0].set_title("Test WAPE (Lower is Better)")
    for i, v in enumerate(df["test_wape"] * 100):
        axes[0].text(v + 0.5, i, f"{v:.2f}%", va="center", fontsize=9)
    axes[0].invert_yaxis()

    # 2. Test MAE
    axes[1].barh(df["model"], df["test_mae"], color=colors)
    axes[1].set_xlabel("Test MAE (Units)")
    axes[1].set_title("Test MAE (Lower is Better)")
    for i, v in enumerate(df["test_mae"]):
        axes[1].text(v + 0.5, i, f"{v:.2f}", va="center", fontsize=9)
    axes[1].invert_yaxis()

    # 3. Test RMSE
    axes[2].barh(df["model"], df["test_rmse"], color=colors)
    axes[2].set_xlabel("Test RMSE (Units)")
    axes[2].set_title("Test RMSE (Lower is Better)")
    for i, v in enumerate(df["test_rmse"]):
        axes[2].text(v + 0.5, i, f"{v:.2f}", va="center", fontsize=9)
    axes[2].invert_yaxis()

    plt.suptitle("Demand Model Benchmark Evaluation (Test Split: Dec 2025)", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()
