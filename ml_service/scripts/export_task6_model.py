"""Export and serialize Task 6 winning demand forecasting model and metadata.

Saves:
- ml_service/models/saved/best_synthetic_sequence_demand_model.joblib
- ml_service/models/saved/best_synthetic_sequence_demand_model_metadata.json
- ml_service/models/saved/best_synthetic_demand_model.joblib (primary active artifact)
- ml_service/models/saved/best_synthetic_demand_model_metadata.json
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import joblib
import numpy as np
import pandas as pd

from data.synthetic_panel import DEFAULT_SYNTHETIC_SEQ_PATH, load_synthetic_panel
from data.time_series_splits import TEST_CUTOFF_DATE
from models.fair_tabular_baselines import FairTabularForecaster, TabularFeatureEngine
from models.metrics import evaluate_forecast

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ExportTask6Model")


def main():
    print("==================================================")
    print("TASK 6: WINNING MODEL SERIALIZATION & REGISTRY EXPORT")
    print("==================================================")
    t0 = time.time()

    print("1. Loading synthetic sequence panel dataset...")
    df = load_synthetic_panel(DEFAULT_SYNTHETIC_SEQ_PATH)
    engine = TabularFeatureEngine(df)
    cutoff_date = pd.Timestamp(TEST_CUTOFF_DATE)
    cutoff_idx = engine.date_to_idx[cutoff_date]

    print(f"Dataset shape: {df.shape} | Cutoff date: {cutoff_date.date()} (index {cutoff_idx})")

    # 2. Build training set on pre-cutoff data (origins 28 up to cutoff_idx - 1)
    train_origins = np.arange(28, cutoff_idx, dtype=np.int32)
    print(f"Building training features across {len(train_origins)} origins...")
    X_train, y_train = engine.build_dataset_vectorized(train_origins, horizon=1, include_history=True)
    print(f"Training dataset: {X_train.shape[0]} rows x {X_train.shape[1]} features")

    # 3. Fit winning HistGradientBoosting with History model
    print("Fitting winning HistGradientBoosting_History forecaster...")
    model = FairTabularForecaster(
        model_type="hist_gradient_boosting",
        include_history=True,
        random_state=42,
    )
    model.fit(X_train, y_train)

    # 4. Evaluate on untouched test set
    test_targets = np.arange(cutoff_idx, engine.n_dates, dtype=np.int32)
    test_origins = test_targets - 1
    print(f"Evaluating on untouched test set ({len(test_origins)} dates x 72 series = {len(test_origins) * 72} samples)...")
    X_test, y_test = engine.build_dataset_vectorized(test_origins, horizon=1, include_history=True)

    preds = model.predict(X_test)
    low, high = model.predict_interval(X_test)
    metrics = evaluate_forecast(y_test.values, preds, low, high)

    print("\nVerified Test Set Performance (Horizon 1d):")
    print(f"  - WAPE: {metrics['wape']:.4f}")
    print(f"  - MAE:  {metrics['mae']:.2f}")
    print(f"  - RMSE: {metrics['rmse']:.2f}")
    print(f"  - Bias: {metrics['bias']:+.2f}")
    print(f"  - 90% Coverage: {metrics.get('coverage', 0.0) * 100:.1f}%")

    # 5. Extract category property priors for inference fallback
    cat_means = df[df["Date"] < cutoff_date].groupby("Food_Category")["Daily_Demand"].mean().to_dict()
    cat_stds = df[df["Date"] < cutoff_date].groupby("Food_Category")["Daily_Demand"].std().to_dict()

    metadata = {
        "model_name": "HistGradientBoosting_History",
        "model_class": "FairTabularForecaster",
        "target": "Daily_Demand",
        "data_origin": "synthetic_seq_v2",
        "version": "2.0.0-synthetic-sequence",
        "random_seed": 42,
        "include_history": True,
        "n_features": len(model.feature_names_),
        "feature_names": model.feature_names_,
        "residual_quantiles_90": list(model.residual_quantiles_),
        "metrics": {
            "test_wape": round(float(metrics["wape"]), 4),
            "test_mae": round(float(metrics["mae"]), 2),
            "test_rmse": round(float(metrics["rmse"]), 2),
            "test_bias": round(float(metrics["bias"]), 2),
            "test_coverage_90": round(float(metrics.get("coverage", 0.0)), 4),
        },
        "train_date_range": ["2023-01-01", str(cutoff_date.date())],
        "test_date_range": [str(cutoff_date.date()), "2025-12-31"],
        "train_rows": int(X_train.shape[0]),
        "test_rows": int(X_test.shape[0]),
        "category_baseline_means": {k: round(float(v), 2) for k, v in cat_means.items()},
        "category_baseline_stds": {k: round(float(v), 2) for k, v in cat_stds.items()},
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }

    # 6. Save model and metadata to saved/ directory
    saved_dir = BASE_DIR / "models" / "saved"
    saved_dir.mkdir(parents=True, exist_ok=True)

    dest_paths = [
        (saved_dir / "best_synthetic_sequence_demand_model.joblib", saved_dir / "best_synthetic_sequence_demand_model_metadata.json"),
        (saved_dir / "best_synthetic_demand_model.joblib", saved_dir / "best_synthetic_demand_model_metadata.json"),
    ]

    for model_path, meta_path in dest_paths:
        joblib.dump(model, model_path)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        print(f"Saved model artifact -> {model_path}")
        print(f"Saved metadata -> {meta_path}")

    print(f"\nSerialization completed successfully in {time.time() - t0:.1f}s.")


if __name__ == "__main__":
    main()
