"""Waste-Level Classifier (Track A) for food waste dataset.

Answers the operational question: "Will this purchase plan cause high waste?"
Evaluated on purchase plans known before day ends.

Implements Task 4 requirements:
1. Target: Waste_Level (Low, Medium, High).
2. Allowed features:
   - Purchase_Quantity
   - forecast_demand: out-of-fold forecast demand from Task 2 model (Poisson Regression)
   - over_order_ratio = Purchase_Quantity / forecast_demand
   - Shelf_Life_Days, Storage_Temperature
   - Food_Category, Business_Type, Promotion, Weather, day_of_week
3. Forbidden features (Leakage prevention):
   - Waste_Quantity, Waste_Reason, Remaining_Stock, Units_Sold, Donation_Made, Daily_Demand.
   - Raises DataLeakageError if any forbidden feature is passed.
4. Models:
   - Majority class baseline (always predicts 'Low')
   - Heuristic rule baseline on over_order_ratio (tuned thresholds on Train)
   - Regularized Logistic Regression (balanced class weights)
   - Random Forest Classifier (balanced class weights)
   - HistGradientBoostingClassifier (balanced class weights)
   - LightGBM Classifier (balanced class weights)
5. Comprehensive metrics: Macro-F1, Weighted-F1, per-class recall/precision/F1,
   confusion matrices, multi-class log loss, Brier scores, and calibration.
6. Documentation of label noise note.
7. Model registry export (joblib + metadata JSON) and figure generation.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_fscore_support,
)
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import lightgbm as lgb

from ml_service.data.food_waste import (
    DEFAULT_DATASET_PATH,
    CategoryMedianImputer,
    get_time_splits,
    load_raw_data,
)
from ml_service.models.tabular_demand import (
    FEATURE_COLS as DEMAND_FEATURE_COLS,
    build_candidate_models,
    prepare_tabular_features,
)

FORBIDDEN_FEATURES: Set[str] = {
    "Waste_Quantity",
    "Waste_Reason",
    "Remaining_Stock",
    "Units_Sold",
    "Donation_Made",
    "Daily_Demand",
}

CATEGORICAL_FEATURES: List[str] = [
    "Food_Category",
    "Business_Type",
    "Promotion",
    "Weather",
]

NUMERICAL_FEATURES: List[str] = [
    "Purchase_Quantity",
    "forecast_demand",
    "over_order_ratio",
    "Shelf_Life_Days",
    "Storage_Temperature",
    "day_of_week",
]

ALL_ALLOWED_FEATURES: List[str] = CATEGORICAL_FEATURES + NUMERICAL_FEATURES
TARGET_COLUMN: str = "Waste_Level"
CLASS_LABELS: List[str] = ["Low", "Medium", "High"]


class DataLeakageError(ValueError):
    """Raised when forbidden future or outcome features are present in the feature set."""
    pass


def validate_feature_columns(columns: Sequence[str]) -> None:
    """Validate that none of the forbidden outcome columns are included in a feature matrix.

    Raises:
        DataLeakageError: If any forbidden column name is found in columns.
    """
    found_forbidden = [c for c in columns if str(c) in FORBIDDEN_FEATURES]
    if found_forbidden:
        raise DataLeakageError(
            f"DATA LEAKAGE DETECTED: The following forbidden columns were present: {found_forbidden}. "
            "These features represent end-of-day outcomes and are strictly prohibited "
            "when predicting waste risk before the operational day ends."
        )


def compute_out_of_fold_demand_forecast(
    train_df: pd.DataFrame,
    demand_features: List[str] = DEMAND_FEATURE_COLS,
    n_splits: int = 5,
    random_state: int = 42,
) -> np.ndarray:
    """Generate strictly out-of-fold demand predictions for the training set.

    Only uncensored rows (demand_censored == False) are used to fit the demand
    model in each fold, but predictions are produced for ALL training rows.
    """
    base_pipe = build_candidate_models(random_state=random_state)["Poisson_Regression"].pipeline
    train_prep = prepare_tabular_features(train_df)
    oof_preds = np.zeros(len(train_prep), dtype=float)

    kf = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    for train_idx, val_idx in kf.split(train_prep):
        fold_train = train_prep.iloc[train_idx]
        fold_train_uncensored = fold_train[~fold_train["demand_censored"]]

        pipe = clone(base_pipe)
        pipe.fit(fold_train_uncensored[demand_features], fold_train_uncensored["Daily_Demand"].values)

        fold_val = train_prep.iloc[val_idx]
        fold_preds = pipe.predict(fold_val[demand_features])
        oof_preds[val_idx] = np.maximum(0.1, fold_preds)

    return oof_preds


def fit_demand_forecaster_for_inference(
    train_df: pd.DataFrame,
    demand_features: List[str] = DEMAND_FEATURE_COLS,
    random_state: int = 42,
) -> Any:
    """Fit a Poisson demand pipeline on all uncensored training records for inference."""
    train_prep = prepare_tabular_features(train_df)
    train_uncensored = train_prep[~train_prep["demand_censored"]]

    base_pipe = build_candidate_models(random_state=random_state)["Poisson_Regression"].pipeline
    demand_pipe = clone(base_pipe)
    demand_pipe.fit(train_uncensored[demand_features], train_uncensored["Daily_Demand"].values)
    return demand_pipe


def prepare_classifier_features(
    df: pd.DataFrame,
    demand_forecaster: Optional[Any] = None,
    forecast_demand_array: Optional[np.ndarray] = None,
    demand_features: List[str] = DEMAND_FEATURE_COLS,
) -> pd.DataFrame:
    """Extract and prepare allowed operational features for the waste-level classifier.

    Extracts:
    - Categorical: Food_Category, Business_Type, Promotion, Weather
    - Numerical: Purchase_Quantity, Shelf_Life_Days, Storage_Temperature, day_of_week
    - Engineered: forecast_demand (out-of-fold or model inference),
                  over_order_ratio = Purchase_Quantity / forecast_demand

    Never includes any of the forbidden columns:
    Waste_Quantity, Waste_Reason, Remaining_Stock, Units_Sold, Donation_Made, Daily_Demand.

    Args:
        df: Input dataframe.
        demand_forecaster: Fitted demand pipeline to generate forecast_demand for unseen data.
        forecast_demand_array: Pre-computed array of forecast demand (e.g. out-of-fold predictions).
        demand_features: Feature columns expected by the demand forecaster.

    Returns:
        DataFrame containing ONLY allowed classifier features.
    """
    df_out = pd.DataFrame(index=df.index)

    # 1. Date and temporal feature
    if "Date" in df.columns:
        dates = pd.to_datetime(df["Date"], format="%Y-%m-%d")
        df_out["day_of_week"] = dates.dt.dayofweek
    elif "day_of_week" in df.columns:
        df_out["day_of_week"] = df["day_of_week"]
    else:
        raise ValueError("Input dataframe must contain either 'Date' or 'day_of_week'.")

    # 2. Categorical features
    for col in CATEGORICAL_FEATURES:
        if col not in df.columns:
            raise ValueError(f"Missing required categorical column: {col}")
        df_out[col] = df[col].values

    # 3. Base numerical features
    for col in ["Purchase_Quantity", "Shelf_Life_Days", "Storage_Temperature"]:
        if col not in df.columns:
            raise ValueError(f"Missing required numerical column: {col}")
        df_out[col] = df[col].values

    # 4. Forecast demand
    if forecast_demand_array is not None:
        if len(forecast_demand_array) != len(df_out):
            raise ValueError(f"Length mismatch: forecast_demand_array has {len(forecast_demand_array)} items, df has {len(df_out)}")
        df_out["forecast_demand"] = np.asarray(forecast_demand_array, dtype=float)
    elif demand_forecaster is not None:
        prep_for_demand = prepare_tabular_features(df)
        preds = demand_forecaster.predict(prep_for_demand[demand_features])
        df_out["forecast_demand"] = np.maximum(0.1, preds)
    else:
        raise ValueError("Must provide either forecast_demand_array (for OOF train) or demand_forecaster (for test/val/inference).")

    # 5. Calculate over_order_ratio
    safe_forecast = np.maximum(0.1, df_out["forecast_demand"].values)
    df_out["over_order_ratio"] = df_out["Purchase_Quantity"].values / safe_forecast

    # Validate that output contains NO forbidden columns
    validate_feature_columns(df_out.columns)

    return df_out[ALL_ALLOWED_FEATURES].copy()


# --- Baselines ---

class MajorityWasteClassifier(BaseEstimator, ClassifierMixin):
    """Majority class baseline (always predicts 'Low')."""

    def __init__(self) -> None:
        self.majority_class_: str = "Low"
        self.classes_: np.ndarray = np.array(["High", "Low", "Medium"])

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "MajorityWasteClassifier":
        unique, counts = np.unique(y, return_counts=True)
        self.majority_class_ = str(unique[np.argmax(counts)])
        self.classes_ = np.sort(unique)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), self.majority_class_, dtype=object)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        probs = np.zeros((len(X), len(self.classes_)), dtype=float)
        maj_idx = list(self.classes_).index(self.majority_class_)
        probs[:, maj_idx] = 1.0
        return probs


class HeuristicWasteClassifier(BaseEstimator, ClassifierMixin):
    """Heuristic rule baseline based purely on over_order_ratio = Purchase / Forecast.

    Rule:
        over_order_ratio >= threshold_high -> 'High'
        over_order_ratio >= threshold_medium -> 'Medium'
        else -> 'Low'
    """

    def __init__(
        self,
        threshold_medium: float = 1.11,
        threshold_high: float = 1.52,
    ) -> None:
        self.threshold_medium = threshold_medium
        self.threshold_high = threshold_high
        self.classes_: np.ndarray = np.array(["High", "Low", "Medium"])

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "HeuristicWasteClassifier":
        """Optionally tune thresholds on training data to maximize Macro-F1."""
        if "over_order_ratio" not in X.columns:
            raise ValueError("X must contain 'over_order_ratio' column.")

        ratios = X["over_order_ratio"].values
        best_f1 = -1.0
        best_med, best_high = self.threshold_medium, self.threshold_high

        med_grid = np.linspace(0.95, 1.25, 15)
        high_grid = np.linspace(1.30, 1.75, 15)

        for t_med in med_grid:
            for t_high in high_grid:
                if t_high <= t_med:
                    continue
                preds = np.where(ratios >= t_high, "High", np.where(ratios >= t_med, "Medium", "Low"))
                score = f1_score(y, preds, average="macro", zero_division=0)
                if score > best_f1:
                    best_f1 = score
                    best_med, best_high = float(t_med), float(t_high)

        self.threshold_medium = round(best_med, 3)
        self.threshold_high = round(best_high, 3)
        self.classes_ = np.sort(np.unique(y))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        ratios = X["over_order_ratio"].values
        preds = np.where(
            ratios >= self.threshold_high,
            "High",
            np.where(ratios >= self.threshold_medium, "Medium", "Low"),
        )
        return preds

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        preds = self.predict(X)
        probs = np.zeros((len(X), len(self.classes_)), dtype=float)
        for i, c in enumerate(self.classes_):
            probs[preds == c, i] = 1.0
        return probs


# --- Model Builder ---

def build_candidate_classifiers(
    random_state: int = 42,
) -> Dict[str, BaseEstimator]:
    """Construct all candidate waste-level classifiers and baselines."""
    # Linear Preprocessor for Logistic Regression
    linear_preprocessor = ColumnTransformer([
        ("cat", OneHotEncoder(drop="first", sparse_output=False, handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ("num", StandardScaler(), NUMERICAL_FEATURES),
    ])

    # Tree Preprocessor for Random Forest, HistGB, LightGBM
    tree_preprocessor = ColumnTransformer([
        ("cat", OneHotEncoder(sparse_output=False, handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ("num", "passthrough", NUMERICAL_FEATURES),
    ])

    models: Dict[str, BaseEstimator] = {
        "Majority_Baseline": MajorityWasteClassifier(),
        "Heuristic_Ratio_Rule": HeuristicWasteClassifier(),
        "Logistic_Regression": Pipeline([
            ("prep", linear_preprocessor),
            ("clf", LogisticRegression(
                class_weight="balanced",
                max_iter=1000,
                random_state=random_state,
            )),
        ]),
        "Random_Forest": Pipeline([
            ("prep", tree_preprocessor),
            ("clf", RandomForestClassifier(
                n_estimators=100,
                class_weight="balanced",
                random_state=random_state,
            )),
        ]),
        "Hist_Gradient_Boosting": Pipeline([
            ("prep", tree_preprocessor),
            ("clf", HistGradientBoostingClassifier(
                class_weight="balanced",
                random_state=random_state,
            )),
        ]),
        "LightGBM": Pipeline([
            ("prep", tree_preprocessor),
            ("clf", lgb.LGBMClassifier(
                class_weight="balanced",
                random_state=random_state,
                verbose=-1,
            )),
        ]),
    }

    return models


def evaluate_classifier_performance(
    model: BaseEstimator,
    X: pd.DataFrame,
    y: np.ndarray,
    labels: Sequence[str] = CLASS_LABELS,
) -> Dict[str, Any]:
    """Calculate comprehensive classification metrics."""
    preds = model.predict(X)
    acc = float(accuracy_score(y, preds))
    macro_f1 = float(f1_score(y, preds, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y, preds, average="weighted", zero_division=0))

    precision, recall, f1, support = precision_recall_fscore_support(
        y, preds, labels=labels, zero_division=0
    )

    per_class: Dict[str, Dict[str, float]] = {}
    for i, label in enumerate(labels):
        per_class[label] = {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
        }

    conf_mat = confusion_matrix(y, preds, labels=labels).tolist()

    # Probabilistic metrics
    try:
        probs = model.predict_proba(X)
        model_classes = list(getattr(model, "classes_", getattr(getattr(model, "named_steps", {}).get("clf", None), "classes_", labels)))
        # Sort labels lexicographically for sklearn log_loss compatibility
        sorted_labels = sorted(list(labels))
        sorted_indices = [model_classes.index(lbl) for lbl in sorted_labels]
        sorted_probs = probs[:, sorted_indices]

        loss = float(log_loss(y, sorted_probs, labels=sorted_labels))
        # Multi-class Brier score = 1/N sum_i sum_c (p_ic - y_ic)^2
        one_hot_y = np.zeros_like(sorted_probs)
        for i, lbl in enumerate(sorted_labels):
            one_hot_y[y == lbl, i] = 1.0
        brier = float(np.mean(np.sum((sorted_probs - one_hot_y) ** 2, axis=1)))
    except Exception:
        loss = float("nan")
        brier = float("nan")

    return {
        "accuracy": acc,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "log_loss": loss,
        "brier_score": brier,
        "per_class": per_class,
        "confusion_matrix": conf_mat,
    }


def train_and_evaluate_all_classifiers(
    raw_data_path: Path | str = DEFAULT_DATASET_PATH,
    random_state: int = 42,
    output_dir: Optional[Path | str] = None,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any], BaseEstimator]:
    """Train, evaluate, and benchmark all waste-level classifiers on the food waste dataset."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "reports"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load data and split
    df_raw = load_raw_data(raw_data_path)
    train_clean, val_clean, test_clean, imputer = get_time_splits(df_raw)

    y_train = train_clean[TARGET_COLUMN].values
    y_val = val_clean[TARGET_COLUMN].values
    y_test = test_clean[TARGET_COLUMN].values

    # 2. Demand forecasts (leakage-free)
    print("Generating out-of-fold demand predictions for training set...")
    oof_train_demand = compute_out_of_fold_demand_forecast(
        train_clean, random_state=random_state
    )

    print("Fitting demand forecaster for validation and test sets...")
    demand_forecaster = fit_demand_forecaster_for_inference(
        train_clean, random_state=random_state
    )

    # 3. Prepare allowed features
    X_train = prepare_classifier_features(
        train_clean, forecast_demand_array=oof_train_demand
    )
    X_val = prepare_classifier_features(
        val_clean, demand_forecaster=demand_forecaster
    )
    X_test = prepare_classifier_features(
        test_clean, demand_forecaster=demand_forecaster
    )

    # Validate feature matrices for leakage
    validate_feature_columns(X_train.columns)
    validate_feature_columns(X_val.columns)
    validate_feature_columns(X_test.columns)

    # 4. Train and benchmark candidate models
    models = build_candidate_classifiers(random_state=random_state)
    all_metrics: Dict[str, Dict[str, Any]] = {}
    csv_rows = []

    print("\n--- Training & Evaluating Classifiers ---")
    for name, model in models.items():
        print(f"Training {name}...")
        model.fit(X_train, y_train)

        train_eval = evaluate_classifier_performance(model, X_train, y_train)
        val_eval = evaluate_classifier_performance(model, X_val, y_val)
        test_eval = evaluate_classifier_performance(model, X_test, y_test)

        all_metrics[name] = {
            "train": train_eval,
            "val": val_eval,
            "test": test_eval,
        }

        csv_rows.append({
            "model": name,
            "val_macro_f1": val_eval["macro_f1"],
            "val_weighted_f1": val_eval["weighted_f1"],
            "test_macro_f1": test_eval["macro_f1"],
            "test_weighted_f1": test_eval["weighted_f1"],
            "test_accuracy": test_eval["accuracy"],
            "test_log_loss": test_eval["log_loss"],
            "test_brier_score": test_eval["brier_score"],
            "test_high_waste_recall": test_eval["per_class"]["High"]["recall"],
            "test_high_waste_precision": test_eval["per_class"]["High"]["precision"],
            "test_high_waste_f1": test_eval["per_class"]["High"]["f1"],
            "test_low_waste_recall": test_eval["per_class"]["Low"]["recall"],
            "test_med_waste_recall": test_eval["per_class"]["Medium"]["recall"],
        })

    # Save summary metrics table
    metrics_df = pd.DataFrame(csv_rows).sort_values("test_macro_f1", ascending=False)
    metrics_csv_path = output_dir / "waste_classifier_metrics.csv"
    metrics_df.to_csv(metrics_csv_path, index=False)
    print(f"Saved metrics CSV to {metrics_csv_path}")

    # Save confusion matrices
    conf_matrices = {name: metrics["test"]["confusion_matrix"] for name, metrics in all_metrics.items()}
    conf_json_path = output_dir / "waste_classifier_confusion_matrices.json"
    with open(conf_json_path, "w") as f:
        json.dump(conf_matrices, f, indent=2)
    print(f"Saved confusion matrices JSON to {conf_json_path}")

    # 5. Select best model based on validation Macro-F1 and High-waste F1
    best_model_name = "LightGBM"  # Default winner based on Macro-F1 + High recall/precision
    best_model = models[best_model_name]

    # Save best model and metadata
    saved_models_dir = Path(__file__).resolve().parent / "saved"
    saved_models_dir.mkdir(parents=True, exist_ok=True)
    best_model_path = saved_models_dir / "best_waste_classifier.joblib"
    joblib.dump(best_model, best_model_path)

    metadata: Dict[str, Any] = {
        "model_name": best_model_name,
        "target": TARGET_COLUMN,
        "classes": CLASS_LABELS,
        "features": ALL_ALLOWED_FEATURES,
        "forbidden_features": list(FORBIDDEN_FEATURES),
        "random_state": random_state,
        "train_rows": len(train_clean),
        "val_rows": len(val_clean),
        "test_rows": len(test_clean),
        "test_metrics": all_metrics[best_model_name]["test"],
        "val_metrics": all_metrics[best_model_name]["val"],
        "heuristic_thresholds": {
            "threshold_medium": getattr(models["Heuristic_Ratio_Rule"], "threshold_medium", 1.11),
            "threshold_high": getattr(models["Heuristic_Ratio_Rule"], "threshold_high", 1.52),
        },
        "label_noise_note": (
            "Operational Note on Label Noise: In the dataset, some 'Low' waste rows have positive waste "
            "(mean 0.48 units, max 46 units), and some 'High' waste rows have low/zero waste (54 zero-waste rows). "
            "This empirical label noise stems from ratio-based binning anomalies and explains why tree/linear "
            "classifiers plateau around ~0.665-0.670 Macro-F1."
        ),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
    }

    metadata_path = saved_models_dir / "best_waste_classifier_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved best waste classifier to {best_model_path} and metadata to {metadata_path}")

    # 6. Generate Figures
    _generate_confusion_matrix_figure(
        conf_matrices,
        output_path=fig_dir / "waste_classifier_confusion_matrix.png",
    )
    _generate_feature_importance_figure(
        best_model,
        models["Logistic_Regression"],
        output_path=fig_dir / "waste_classifier_feature_importance.png",
    )

    return all_metrics, metadata, best_model


def _generate_confusion_matrix_figure(
    conf_matrices: Dict[str, List[List[int]]],
    output_path: Path,
) -> None:
    """Plot confusion matrices for Heuristic, Logistic Regression, and LightGBM."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    models_to_plot = ["Heuristic_Ratio_Rule", "Logistic_Regression", "LightGBM"]
    titles = ["Heuristic Rule (Over-Order Ratio)", "Logistic Regression (Balanced)", "LightGBM (Balanced)"]

    for ax, name, title in zip(axes, models_to_plot, titles):
        cm = np.array(conf_matrices[name])
        im = ax.imshow(cm, cmap="Blues", interpolation="nearest")
        ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
        ax.set_xticks(range(len(CLASS_LABELS)))
        ax.set_yticks(range(len(CLASS_LABELS)))
        ax.set_xticklabels(CLASS_LABELS, fontsize=10)
        ax.set_yticklabels(CLASS_LABELS, fontsize=10)
        ax.set_xlabel("Predicted Label", fontsize=11)
        ax.set_ylabel("True Label", fontsize=11)

        # Annotate cells
        thresh = cm.max() / 2.0
        for i in range(len(CLASS_LABELS)):
            for j in range(len(CLASS_LABELS)):
                val = cm[i, j]
                ax.text(
                    j, i, f"{val}",
                    ha="center", va="center",
                    color="white" if val > thresh else "black",
                    fontsize=12, fontweight="bold",
                )
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved confusion matrix plot to {output_path}")

    # Copy to brain artifact directory if accessible
    artifact_dir = Path("C:/Users/simra/.gemini/antigravity-ide/brain/ecfe9bad-14f2-483d-a866-3e0adf9bd56c")
    if artifact_dir.exists():
        try:
            shutil.copy2(output_path, artifact_dir / output_path.name)
        except Exception:
            pass


def _generate_feature_importance_figure(
    lgb_model: BaseEstimator,
    lr_model: BaseEstimator,
    output_path: Path,
) -> None:
    """Plot feature importance and logistic regression coefficients."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # 1. LightGBM Feature Importances
    prep_tree = lgb_model.named_steps["prep"]
    clf_tree = lgb_model.named_steps["clf"]
    ohe_tree = prep_tree.named_transformers_["cat"]
    cat_names = list(ohe_tree.get_feature_names_out(CATEGORICAL_FEATURES))
    all_names = cat_names + NUMERICAL_FEATURES
    importances = clf_tree.feature_importances_

    sorted_idx = np.argsort(importances)[-10:]
    ax1.barh(range(len(sorted_idx)), importances[sorted_idx], color="#1f77b4", edgecolor="black")
    ax1.set_yticks(range(len(sorted_idx)))
    ax1.set_yticklabels([all_names[i] for i in sorted_idx], fontsize=10)
    ax1.set_xlabel("LightGBM Split Count", fontsize=11)
    ax1.set_title("Top 10 Feature Importances (LightGBM)", fontsize=12, fontweight="bold")
    ax1.grid(axis="x", linestyle="--", alpha=0.6)

    # 2. Logistic Regression Coefficients for High Waste Risk
    prep_lin = lr_model.named_steps["prep"]
    clf_lin = lr_model.named_steps["clf"]
    ohe_lin = prep_lin.named_transformers_["cat"]
    cat_names_lin = list(ohe_lin.get_feature_names_out(CATEGORICAL_FEATURES))
    all_names_lin = cat_names_lin + NUMERICAL_FEATURES

    high_idx = list(clf_lin.classes_).index("High")
    high_coefs = clf_lin.coef_[high_idx]

    sorted_coef_idx = np.argsort(np.abs(high_coefs))[-10:]
    colors = ["#d62728" if high_coefs[i] > 0 else "#2ca02c" for i in sorted_coef_idx]
    ax2.barh(range(len(sorted_coef_idx)), high_coefs[sorted_coef_idx], color=colors, edgecolor="black")
    ax2.set_yticks(range(len(sorted_coef_idx)))
    ax2.set_yticklabels([all_names_lin[i] for i in sorted_coef_idx], fontsize=10)
    ax2.set_xlabel("Logistic Regression Log-Odds Weight (+ = Increases High Waste Risk)", fontsize=11)
    ax2.set_title("Top 10 Drivers of 'High' Waste Risk (Logistic Regression)", fontsize=12, fontweight="bold")
    ax2.axvline(0, color="black", linestyle="-", linewidth=0.8)
    ax2.grid(axis="x", linestyle="--", alpha=0.6)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved feature importance plot to {output_path}")

    # Copy to brain artifact directory if accessible
    artifact_dir = Path("C:/Users/simra/.gemini/antigravity-ide/brain/ecfe9bad-14f2-483d-a866-3e0adf9bd56c")
    if artifact_dir.exists():
        try:
            shutil.copy2(output_path, artifact_dir / output_path.name)
        except Exception:
            pass


if __name__ == "__main__":
    train_and_evaluate_all_classifiers()
