"""Run Task 4: Classic Baselines and Prophet Evaluation across 4 rolling-origin CV folds for Horizons 1 and 7."""

import json
import sys
import time
from pathlib import Path

# Ensure unbuffered printing
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import numpy as np
import pandas as pd

from data.synthetic_panel import load_synthetic_panel, DEFAULT_SYNTHETIC_SEQ_PATH
from models.classic_and_prophet import (
    ClassicPanelBaselines,
    run_classic_baselines_cv,
    run_prophet_cv,
)
from models.fair_tabular_baselines import TabularFeatureEngine


def main():
    print("==================================================")
    print("TASK 4: PROPHET AND CLASSIC BASELINES EVALUATION")
    print("==================================================")
    print(f"Loading synthetic sequence dataset from {DEFAULT_SYNTHETIC_SEQ_PATH}...")
    df = load_synthetic_panel(DEFAULT_SYNTHETIC_SEQ_PATH)
    print(f"Loaded: {df.shape[0]:,} rows (72 daily series, 1096 days)")

    t0 = time.time()
    engine = TabularFeatureEngine(df)
    print(f"Feature engine initialized in {time.time() - t0:.2f}s")

    horizons = [1, 7]
    series_results = []
    category_results = []

    # 1. Run Classic Baselines across 4 rolling-origin folds
    print("\n--- 1. EVALUATING CLASSIC BASELINES (72 SERIES) ---")
    for h in horizons:
        print(f"\nRunning Classic Baselines | Horizon = {h} day(s)...")
        t_start = time.time()
        classic_metrics = run_classic_baselines_cv(engine=engine, horizon=h, n_splits=4)
        elapsed = time.time() - t_start

        baseline_names = {
            "naive_1": "Seasonal Naive-1 (y_T)",
            "naive_7": "Seasonal Naive-7 (y_{T+h-7})",
            "rolling_mean_28": "28-Day Rolling Mean",
            "weekday_profile": "Historical Weekday Profile",
        }

        for b_key, b_name in baseline_names.items():
            m = classic_metrics[b_key]
            print(
                f"  * {b_name:<28} | WAPE: {m['wape']:.4f} | MAE: {m['mae']:.2f} | "
                f"RMSE: {m['rmse']:.2f} | Bias: {m['bias']:+.2f} | 90% Cov: {m['coverage']*100:.1f}%"
            )
            series_results.append({
                "Model": b_name,
                "Model_Type": "Classic Baseline",
                "Horizon": f"{h}d",
                "WAPE": m["wape"],
                "MAE": m["mae"],
                "RMSE": m["rmse"],
                "Bias": m["bias"],
                "90% Coverage": m["coverage"],
                "Time (s)": round(elapsed, 1),
            })

    # 2. Run Prophet with Regressors and Festivals
    print("\n--- 2. EVALUATING PROPHET PER CATEGORY (REGRESSORS + FESTIVALS) ---")
    for h in horizons:
        print(f"\nRunning Prophet per Category | Horizon = {h} day(s)...")
        t_start = time.time()
        m_series, m_cat = run_prophet_cv(
            panel_df=df,
            engine=engine,
            horizon=h,
            n_splits=4,
        )
        elapsed = time.time() - t_start

        print(
            f"  * Prophet (Disaggregated 72-Series)  | WAPE: {m_series['wape']:.4f} | MAE: {m_series['mae']:.2f} | "
            f"RMSE: {m_series['rmse']:.2f} | Bias: {m_series['bias']:+.2f} | 90% Cov: {m_series['coverage']*100:.1f}% ({elapsed:.1f}s)"
        )
        print(
            f"  * Prophet (Category Aggregate Level) | WAPE: {m_cat['wape']:.4f} | MAE: {m_cat['mae']:.2f} | "
            f"RMSE: {m_cat['rmse']:.2f} | Bias: {m_cat['bias']:+.2f} | 90% Cov: {m_cat['coverage']*100:.1f}%"
        )

        series_results.append({
            "Model": "Prophet (Regressors + Festivals)",
            "Model_Type": "Prophet",
            "Horizon": f"{h}d",
            "WAPE": m_series["wape"],
            "MAE": m_series["mae"],
            "RMSE": m_series["rmse"],
            "Bias": m_series["bias"],
            "90% Coverage": m_series["coverage"],
            "Time (s)": round(elapsed, 1),
        })

        category_results.append({
            "Model": "Prophet (Regressors + Festivals)",
            "Level": "Category Aggregate (6 Categories)",
            "Horizon": f"{h}d",
            "WAPE": m_cat["wape"],
            "MAE": m_cat["mae"],
            "RMSE": m_cat["rmse"],
            "Bias": m_cat["bias"],
            "90% Coverage": m_cat["coverage"],
            "Time (s)": round(elapsed, 1),
        })

    # 3. Print Comprehensive Comparison Table
    print("\n==================================================")
    print("TASK 4 RESULTS SUMMARY: 72-SERIES PANEL FORECASTING")
    print("==================================================")
    res_df = pd.DataFrame(series_results)
    pd.set_option("display.max_columns", 10)
    pd.set_option("display.width", 140)
    print(res_df.to_string(index=False))

    # Save to json report
    out_dir = BASE_DIR / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "task4_prophet_classic_results.json"
    with open(out_file, "w") as f:
        json.dump({
            "series_level_evaluation": series_results,
            "category_level_evaluation": category_results,
        }, f, indent=2)
    print(f"\nSaved structured results to: {out_file}")


if __name__ == "__main__":
    main()
