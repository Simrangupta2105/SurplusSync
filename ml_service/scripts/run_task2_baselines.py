"""Run Task 2 Fair Tabular Baselines across 4 rolling-origin CV folds for Horizons 1 and 7."""

import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import numpy as np
import pandas as pd

from data.synthetic_panel import load_synthetic_panel, DEFAULT_SYNTHETIC_SEQ_PATH
from models.fair_tabular_baselines import TabularFeatureEngine, run_tabular_rolling_cv

def main():
    print("==================================================")
    print("TASK 2: FAIR TABULAR BASELINES EVALUATION")
    print("==================================================")
    print("Loading synthetic sequence panel dataset...")
    df = load_synthetic_panel(DEFAULT_SYNTHETIC_SEQ_PATH)
    print(f"Dataset shape: {df.shape} (72 series, 1096 days)")

    t0 = time.time()
    engine = TabularFeatureEngine(df)
    print(f"Feature engine initialized in {time.time() - t0:.2f}s")

    models = ["hist_gradient_boosting", "lightgbm"]
    horizons = [1, 7]
    configs = [
        ("Covariates Only", False),
        ("Covariates + Demand History", True),
    ]

    results = []

    for model_type in models:
        for cfg_name, inc_hist in configs:
            for h in horizons:
                label = f"{'LightGBM' if model_type == 'lightgbm' else 'HistGradientBoosting'} ({cfg_name})"
                print(f"\n--- Running: {label} | Horizon = {h} day(s) ---")
                t_start = time.time()
                res = run_tabular_rolling_cv(
                    engine=engine,
                    horizon=h,
                    include_history=inc_hist,
                    model_type=model_type,
                    n_splits=4,
                )
                elapsed = time.time() - t_start
                ov = res["overall"]
                cov_val = ov.get("coverage", 0.0)
                print(f"Completed in {elapsed:.1f}s | WAPE: {ov['wape']:.4f} | MAE: {ov['mae']:.2f} | RMSE: {ov['rmse']:.2f} | Bias: {ov['bias']:+.2f} | 90% Cov: {cov_val*100:.1f}%")

                results.append({
                    "Model": "LightGBM" if model_type == "lightgbm" else "HistGradientBoosting",
                    "Features": cfg_name,
                    "Horizon": f"{h}d",
                    "WAPE": ov["wape"],
                    "MAE": ov["mae"],
                    "RMSE": ov["rmse"],
                    "Bias": ov["bias"],
                    "90% Coverage": cov_val,
                    "Time (s)": round(elapsed, 1),
                })

    print("\n==================================================")
    print("SUMMARY RESULTS TABLE (ROLLING-ORIGIN CV)")
    print("==================================================")
    res_df = pd.DataFrame(results)
    pd.set_option("display.max_columns", 10)
    pd.set_option("display.width", 120)
    print(res_df.to_string(index=False))

    # Save results to json
    out_path = BASE_DIR / "reports" / "task2_tabular_baseline_results.json"
    res_df.to_json(out_path, orient="records", indent=2)
    print(f"\nSaved results to {out_path}")

if __name__ == "__main__":
    main()
