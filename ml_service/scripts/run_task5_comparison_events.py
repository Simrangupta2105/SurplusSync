"""Task 5 Grand Unified Comparison, Significance Testing, and Event Analysis.

Executes:
1. Model Selection strictly on CV (zero test peeking):
   - Overall CV leaderboard for h=1 and h=7.
   - Breakdown by Business Type.
   - Breakdown by Food Category.
   - Best model selected per category strictly on CV WAPE.
2. Final Single-Pass Evaluation on the Untouched 90-Day Test Set:
   - 6,480 evaluation points for h=1 and h=7.
   - All 10 models + Best-Per-Category Ensemble.
3. Statistical Significance Testing:
   - Diebold-Mariano test (h-1 lag truncation).
   - Paired Bootstrap test (1,000 resamples, Delta-WAPE, 95% CI, p-value).
4. Event Adaptation Analysis:
   - Error degradation across hidden shocks and regimes.
   - Adaptation speed: Onset (Days 1-3) vs Sustained (Days 4+).
5. Diagnostic Figures and JSON results saving.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Unbuffer stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import numpy as np
import pandas as pd

from data.synthetic_panel import DEFAULT_SYNTHETIC_SEQ_PATH, load_synthetic_panel
from reports.task5_comparison_and_events import (
    FIGURES_DIR,
    REPORTS_DIR,
    Task5Evaluator,
    generate_task5_diagnostic_plots,
    load_events_log,
    perform_event_adaptation_analysis,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Task5Runner")


def format_table(df: pd.DataFrame, title: str) -> None:
    print(f"\n{'='*75}")
    print(f"{title}")
    print(f"{'='*75}")
    print(df.to_string(index=False))


def main():
    print("============================================================================")
    print("TASK 5: GRAND UNIFIED MODEL COMPARISON, ERROR ANALYSIS & EVENT ADAPTATION")
    print("============================================================================")
    t_start = time.time()

    print("\n1. Loading Synthetic Sequence Panel and Hidden Events Log...")
    df = load_synthetic_panel(DEFAULT_SYNTHETIC_SEQ_PATH)
    events_df = load_events_log()
    print(f"Panel shape: {df.shape} (72 series, 1096 days)")
    print(f"Events log: {len(events_df)} event records loaded")

    evaluator = Task5Evaluator(df)
    results_out = {
        "dataset_info": {
            "n_series": evaluator.engine.n_series,
            "n_dates": evaluator.engine.n_dates,
            "cutoff_date": str(evaluator.cutoff_date.date()),
            "test_days": 90,
            "test_samples": 90 * evaluator.engine.n_series,
        },
        "cv_selection": {},
        "test_evaluation": {},
        "significance_tests": {},
        "event_adaptation": {},
    }

    # ============================================================================
    # HORIZON 1 (h=1)
    # ============================================================================
    print("\n============================================================================")
    print("HORIZON 1 DAY (h=1): CROSS-VALIDATION BREAKDOWN & MODEL SELECTION")
    print("============================================================================")
    t0 = time.time()
    cv_df_h1, cv_breakdown_h1, best_cat_h1 = evaluator.run_cv_breakdown(horizon=1)
    print(f"CV breakdown completed in {time.time() - t0:.1f}s")

    # Table 1: Overall CV Leaderboard
    cv_overall_rows_h1 = []
    for m_col, m_dict in cv_breakdown_h1["overall"].items():
        cv_overall_rows_h1.append({
            "Model": m_col,
            "CV_WAPE": m_dict["wape"],
            "CV_MAE": m_dict["mae"],
            "CV_RMSE": m_dict["rmse"],
            "CV_Bias": m_dict["bias"],
        })
    cv_ov_df_h1 = pd.DataFrame(cv_overall_rows_h1).sort_values("CV_WAPE").reset_index(drop=True)
    format_table(cv_ov_df_h1, "CV LEADERBOARD (Horizon 1d) - 4 Rolling-Origin Folds")

    # Table 2: CV Breakdown by Business Type
    btype_rows_h1 = []
    for btype, m_dict in cv_breakdown_h1["by_business_type"].items():
        row = {"Business_Type": btype}
        for m_col, metrics in m_dict.items():
            row[m_col] = round(metrics["wape"], 4)
        btype_rows_h1.append(row)
    cv_btype_df_h1 = pd.DataFrame(btype_rows_h1)
    format_table(cv_btype_df_h1, "CV WAPE BY BUSINESS TYPE (Horizon 1d)")

    # Table 3: CV Breakdown by Food Category & Model Selection
    cat_rows_h1 = []
    for cat, m_dict in cv_breakdown_h1["by_category"].items():
        row = {"Food_Category": cat}
        for m_col, metrics in m_dict.items():
            row[m_col] = round(metrics["wape"], 4)
        row["Best_Model_Selected"] = best_cat_h1[cat]
        cat_rows_h1.append(row)
    cv_cat_df_h1 = pd.DataFrame(cat_rows_h1)
    format_table(cv_cat_df_h1, "CV WAPE BY FOOD CATEGORY & MODEL SELECTION (Horizon 1d)")

    print("\nBest Model Selected per Category (strictly on CV WAPE, zero test peeking):")
    for cat, b_m in best_cat_h1.items():
        print(f"  - {cat:16s} -> {b_m}")

    # ============================================================================
    # HORIZON 1 (h=1): FINAL SINGLE-PASS TEST EVALUATION
    # ============================================================================
    print("\n============================================================================")
    print("HORIZON 1 DAY (h=1): UNTOUCHED 90-DAY FINAL TEST SET EVALUATION")
    print("============================================================================")
    t0 = time.time()
    test_pred_df_h1, test_metrics_h1 = evaluator.run_final_test_set_evaluation(
        horizon=1, best_per_category=best_cat_h1
    )
    print(f"Final test set evaluation completed in {time.time() - t0:.1f}s")

    test_rows_h1 = []
    for m_label, m_dict in test_metrics_h1.items():
        test_rows_h1.append({
            "Model": m_label,
            "Test_WAPE": m_dict["wape"],
            "Test_MAE": m_dict["mae"],
            "Test_RMSE": m_dict["rmse"],
            "Test_Bias": m_dict["bias"],
            "90% Coverage": m_dict["coverage_90"],
        })
    test_summary_df_h1 = pd.DataFrame(test_rows_h1).sort_values("Test_WAPE").reset_index(drop=True)
    format_table(test_summary_df_h1, "FINAL TEST SET RESULTS (Horizon 1d, 6,480 Samples)")

    # Significance Tests h=1
    print("\nRunning Diebold-Mariano & Paired Bootstrap Tests (h=1)...")
    comp_models = [
        ("LightGBM (Covariates + History)", "LightGBM_History"),
        ("Global PyTorch LSTM", "Global_LSTM"),
        ("Prophet (Regressors + Festivals)", "Prophet"),
        ("Historical Weekday Profile", "Weekday_Profile"),
    ]
    sig_tests_h1 = evaluator.run_significance_tests(
        test_pred_df_h1,
        best_col="HistGradientBoosting_History",
        comp_cols=comp_models,
        horizon=1,
    )
    sig_df_h1 = pd.DataFrame(sig_tests_h1)
    format_table(sig_df_h1, "STATISTICAL SIGNIFICANCE TESTS (h=1, HistGradientBoosting vs Competitors)")

    # Event Adaptation Analysis h=1
    print("\nRunning Event Adaptation Analysis (h=1)...")
    ev_type_h1, ev_adapt_h1 = perform_event_adaptation_analysis(test_pred_df_h1, events_df)
    format_table(ev_type_h1, "ERROR DEGRADATION BY EVENT TYPE (h=1, Normal vs Shock vs Regimes)")
    if len(ev_adapt_h1) > 0:
        format_table(ev_adapt_h1, "REGIME SHIFT ADAPTATION SPEED (h=1, Onset vs Sustained)")

    # ============================================================================
    # HORIZON 7 (h=7)
    # ============================================================================
    print("\n============================================================================")
    print("HORIZON 7 DAYS (h=7): CROSS-VALIDATION BREAKDOWN & MODEL SELECTION")
    print("============================================================================")
    t0 = time.time()
    cv_df_h7, cv_breakdown_h7, best_cat_h7 = evaluator.run_cv_breakdown(horizon=7)
    print(f"CV breakdown completed in {time.time() - t0:.1f}s")

    # Table: Overall CV Leaderboard h=7
    cv_overall_rows_h7 = []
    for m_col, m_dict in cv_breakdown_h7["overall"].items():
        cv_overall_rows_h7.append({
            "Model": m_col,
            "CV_WAPE": m_dict["wape"],
            "CV_MAE": m_dict["mae"],
            "CV_RMSE": m_dict["rmse"],
            "CV_Bias": m_dict["bias"],
        })
    cv_ov_df_h7 = pd.DataFrame(cv_overall_rows_h7).sort_values("CV_WAPE").reset_index(drop=True)
    format_table(cv_ov_df_h7, "CV LEADERBOARD (Horizon 7d) - 4 Rolling-Origin Folds")

    cat_rows_h7 = []
    for cat, m_dict in cv_breakdown_h7["by_category"].items():
        row = {"Food_Category": cat}
        for m_col, metrics in m_dict.items():
            row[m_col] = round(metrics["wape"], 4)
        row["Best_Model_Selected"] = best_cat_h7[cat]
        cat_rows_h7.append(row)
    cv_cat_df_h7 = pd.DataFrame(cat_rows_h7)
    format_table(cv_cat_df_h7, "CV WAPE BY FOOD CATEGORY & MODEL SELECTION (Horizon 7d)")

    # HORIZON 7 (h=7): FINAL SINGLE-PASS TEST EVALUATION
    print("\n============================================================================")
    print("HORIZON 7 DAYS (h=7): UNTOUCHED 90-DAY FINAL TEST SET EVALUATION")
    print("============================================================================")
    t0 = time.time()
    test_pred_df_h7, test_metrics_h7 = evaluator.run_final_test_set_evaluation(
        horizon=7, best_per_category=best_cat_h7
    )
    print(f"Final test set evaluation completed in {time.time() - t0:.1f}s")

    test_rows_h7 = []
    for m_label, m_dict in test_metrics_h7.items():
        test_rows_h7.append({
            "Model": m_label,
            "Test_WAPE": m_dict["wape"],
            "Test_MAE": m_dict["mae"],
            "Test_RMSE": m_dict["rmse"],
            "Test_Bias": m_dict["bias"],
            "90% Coverage": m_dict["coverage_90"],
        })
    test_summary_df_h7 = pd.DataFrame(test_rows_h7).sort_values("Test_WAPE").reset_index(drop=True)
    format_table(test_summary_df_h7, "FINAL TEST SET RESULTS (Horizon 7d, 6,480 Samples)")

    sig_tests_h7 = evaluator.run_significance_tests(
        test_pred_df_h7,
        best_col="HistGradientBoosting_History",
        comp_cols=comp_models,
        horizon=7,
    )
    sig_df_h7 = pd.DataFrame(sig_tests_h7)
    format_table(sig_df_h7, "STATISTICAL SIGNIFICANCE TESTS (h=7, HistGradientBoosting vs Competitors)")

    # Event Adaptation Analysis h=7
    ev_type_h7, ev_adapt_h7 = perform_event_adaptation_analysis(test_pred_df_h7, events_df)

    # ============================================================================
    # GENERATE DIAGNOSTIC CHARTS
    # ============================================================================
    print("\n============================================================================")
    print("SAVING DIAGNOSTIC CHARTS WITH [SYNTHETIC DATA] WATERMARKS")
    print("============================================================================")
    saved_figs = generate_task5_diagnostic_plots(
        pred_df=test_pred_df_h1,
        summary_df=test_summary_df_h1.rename(columns={"Test_WAPE": "WAPE"}),
        event_summary_df=ev_type_h1,
        output_dir=FIGURES_DIR,
        regime_adapt_df=ev_adapt_h1,
    )
    for f in saved_figs:
        print(f"  - Saved: {f}")

    # ============================================================================
    # SAVE JSON RESULTS
    # ============================================================================
    results_out["cv_selection"]["h1"] = {
        "overall": cv_breakdown_h1["overall"],
        "by_business_type": cv_breakdown_h1["by_business_type"],
        "by_category": cv_breakdown_h1["by_category"],
        "best_per_category": best_cat_h1,
    }
    results_out["cv_selection"]["h7"] = {
        "overall": cv_breakdown_h7["overall"],
        "by_business_type": cv_breakdown_h7["by_business_type"],
        "by_category": cv_breakdown_h7["by_category"],
        "best_per_category": best_cat_h7,
    }
    results_out["test_evaluation"]["h1"] = test_metrics_h1
    results_out["test_evaluation"]["h7"] = test_metrics_h7
    results_out["significance_tests"]["h1"] = sig_tests_h1
    results_out["significance_tests"]["h7"] = sig_tests_h7
    results_out["event_adaptation"]["h1"] = {
        "by_event_type": ev_type_h1.to_dict(orient="records"),
        "regime_adaptation": ev_adapt_h1.to_dict(orient="records") if len(ev_adapt_h1) > 0 else [],
    }
    results_out["event_adaptation"]["h7"] = {
        "by_event_type": ev_type_h7.to_dict(orient="records"),
        "regime_adaptation": ev_adapt_h7.to_dict(orient="records") if len(ev_adapt_h7) > 0 else [],
    }

    out_json = REPORTS_DIR / "task5_comparison_results.json"
    with open(out_json, "w") as f:
        json.dump(results_out, f, indent=2)
    print(f"\nSaved complete results to: {out_json}")
    print(f"Total Task 5 execution time: {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
