"""Execute Task 3 LSTM Evaluation across 4 Ablations, 4 Rolling-Origin Folds, and 5 Random Seeds."""

import json
import sys
import time
from pathlib import Path

# Ensure unbuffered immediate printing to console and log files
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
from models.fair_tabular_baselines import TabularFeatureEngine
from models.lstm_global import (
    LSTM_SEEDS,
    GlobalLSTMForecaster,
    GlobalMultiHorizonLSTM,
    get_parameter_count,
    run_lstm_rolling_cv_seed,
)


def main():
    print("==================================================")
    print("TASK 3: GLOBAL MULTI-HORIZON LSTM EVALUATION")
    print("==================================================")
    print(f"Loading synthetic sequence dataset from {DEFAULT_SYNTHETIC_SEQ_PATH}...")
    df = load_synthetic_panel(DEFAULT_SYNTHETIC_SEQ_PATH)
    print(f"Loaded: {df.shape[0]:,} rows (72 series, 1096 days)")

    t0 = time.time()
    engine = TabularFeatureEngine(df)
    print(f"Feature engine initialized in {time.time() - t0:.2f}s")

    ablations = [
        ("Ablation (a): Past demand only", False, False, False),
        ("Ablation (b): + Future covariates", True, False, False),
        ("Ablation (c): + Embeddings", True, True, False),
        ("Ablation (d): + Cross-series", True, True, True),
    ]

    print("\n--- MODEL ARCHITECTURE & PARAMETER COUNTS ---")
    for name, cov, emb, cross in ablations:
        m = GlobalMultiHorizonLSTM(use_covariates=cov, use_embeddings=emb, use_cross_series=cross)
        p_count = get_parameter_count(m)
        print(f"  * {name:<36}: {p_count:>6,} trainable parameters")

    print("\nEvaluation Protocol:")
    print("  * 4 Rolling-Origin CV Folds on Pre-Cutoff Data (Date < 2025-10-03)")
    print("  * Untouched Final 90 Days (2025-10-03 to 2025-12-31) strictly preserved")
    print("  * 5 Fixed Random Seeds: [42, 123, 456, 789, 999]")
    print("  * Horizons Evaluated: h=1 day and h=7 days (direct multi-horizon)")
    print("  * Loss: Huber Loss (beta=1.0) with AdamW (1e-3), gradient clipping, dropout (0.1)")
    print("==================================================")

    all_results = []
    summary_rows = []

    for name, cov, emb, cross in ablations:
        print(f"\n==================================================")
        print(f"Running {name}...")
        print(f"==================================================")
        ablation_t0 = time.time()

        seed_results = []
        for s_idx, seed in enumerate(LSTM_SEEDS, 1):
            s_t0 = time.time()
            res = run_lstm_rolling_cv_seed(
                engine=engine,
                use_covariates=cov,
                use_embeddings=emb,
                use_cross_series=cross,
                seed=seed,
                n_splits=4,
            )
            s_elapsed = time.time() - s_t0
            seed_results.append(res)
            print(
                f"  [Seed {seed} ({s_idx}/5) - {s_elapsed:.1f}s] "
                f"h=1 WAPE: {res['h1']['wape']:.4f}, MAE: {res['h1']['mae']:.2f}, Cov: {res['h1']['coverage']*100:.1f}% | "
                f"h=7 WAPE: {res['h7']['wape']:.4f}, MAE: {res['h7']['mae']:.2f}, Cov: {res['h7']['coverage']*100:.1f}%"
            )

        ablation_elapsed = time.time() - ablation_t0
        print(f"Completed {name} in {ablation_elapsed:.1f}s")

        # Aggregate across seeds
        for h_key, h_label in [("h1", "1d"), ("h7", "7d")]:
            wapes = [r[h_key]["wape"] for r in seed_results]
            maes = [r[h_key]["mae"] for r in seed_results]
            rmses = [r[h_key]["rmse"] for r in seed_results]
            biases = [r[h_key]["bias"] for r in seed_results]
            covs = [r[h_key]["coverage"] for r in seed_results]

            summary_rows.append({
                "Ablation": name,
                "Horizon": h_label,
                "WAPE": f"{np.mean(wapes):.4f} +/- {np.std(wapes):.4f}",
                "MAE": f"{np.mean(maes):.2f} +/- {np.std(maes):.2f}",
                "RMSE": f"{np.mean(rmses):.2f} +/- {np.std(rmses):.2f}",
                "Bias": f"{np.mean(biases):+.2f} +/- {np.std(biases):.2f}",
                "90% Coverage": f"{np.mean(covs)*100:.1f}% +/- {np.std(covs)*100:.1f}%",
                "WAPE_mean": float(np.mean(wapes)),
                "MAE_mean": float(np.mean(maes)),
                "RMSE_mean": float(np.mean(rmses)),
                "Bias_mean": float(np.mean(biases)),
                "Coverage_mean": float(np.mean(covs)),
            })

        all_results.append({
            "ablation": name,
            "use_covariates": cov,
            "use_embeddings": emb,
            "use_cross_series": cross,
            "seeds": seed_results,
            "time_seconds": round(ablation_elapsed, 1),
        })

    # Display comparison table
    summary_df = pd.DataFrame(summary_rows)
    print("\n==================================================")
    print("TASK 3 LSTM ABLATION RESULTS (MEAN +/- STD ACROSS 5 SEEDS)")
    print("==================================================")
    cols_to_show = ["Ablation", "Horizon", "WAPE", "MAE", "RMSE", "Bias", "90% Coverage"]
    pd.set_option("display.max_columns", 10)
    pd.set_option("display.width", 140)
    print(summary_df[cols_to_show].to_string(index=False))

    # Save to json report
    out_dir = BASE_DIR / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "task3_lstm_results.json"
    with open(out_file, "w") as f:
        json.dump({
            "ablations_summary": summary_rows,
            "detailed_runs": all_results,
        }, f, indent=2)
    print(f"\nSaved structured results to: {out_file}")


if __name__ == "__main__":
    main()
