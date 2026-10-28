"""Task 0 Verification Script:
Recomputes and reports invariants, autocorrelations (lags 1, 7, 14, 28, 365),
calibration against benchmark CSV, and comparison against validation_report.md.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import numpy as np
import pandas as pd

from data.synthetic_panel import load_synthetic_panel, validate_invariants
RAW_DIR = BASE_DIR / "data" / "raw"
BENCH_PATH = RAW_DIR / "food_waste_dataset.csv"
SEQ_PATH = RAW_DIR / "synthetic_sequence_panel_full.csv"
SYN_V1_PATH = RAW_DIR / "synthetic_panel_full.csv"
VAL_REPORT_PATH = RAW_DIR / "validation_report.md"


def compute_calibration_stats(df: pd.DataFrame, name: str) -> pd.Series:
    d = df.dropna(subset=["Daily_Demand"])
    s = {}
    for t in ["Cafeteria", "Restaurant", "Cloud Kitchen", "Supermarket"]:
        s[f"mean demand: {t}"] = float(d[d.Business_Type == t].Daily_Demand.mean())
    s["promotion lift (demand ratio)"] = float(
        d[d.Promotion == "Yes"].Daily_Demand.mean() / d[d.Promotion == "No"].Daily_Demand.mean()
    )
    s["promotion share of rows"] = float((df.Promotion == "Yes").mean())
    w = d.groupby("Weather")["Daily_Demand"].mean()
    for k in ["Cloudy", "Hot", "Rainy"]:
        s[f"weather ratio vs Sunny: {k}"] = float(w[k] / w["Sunny"])
    for k in ["Sunny", "Cloudy", "Hot", "Rainy"]:
        s[f"weather share: {k}"] = float((df.Weather == k).mean())
    for c in sorted(df.Food_Category.unique()):
        g = df[df.Food_Category == c]
        s[f"waste/purchase: {c}"] = float(g.Waste_Quantity.sum() / g.Purchase_Quantity.sum())
    for c in sorted(df.Food_Category.unique()):
        g = df[df.Food_Category == c]
        s[f"mean shelf life: {c}"] = float(g.Shelf_Life_Days.mean())
    for c in sorted(df.Food_Category.unique()):
        s[f"mean storage temp: {c}"] = float(df[df.Food_Category == c].Storage_Temperature.mean())
    s["waste > 0 share"] = float((df.Waste_Quantity > 0).mean())
    s["remaining = 0 share"] = float((df.Remaining_Stock == 0).mean())
    s["purchase > demand share"] = float((d.Purchase_Quantity > d.Daily_Demand).mean())
    s["demand > purchase share (stock-out)"] = float((d.Daily_Demand > d.Purchase_Quantity).mean())
    s["mean purchase / demand"] = float((d.Purchase_Quantity / d.Daily_Demand).mean())
    wr = df[df.Waste_Quantity > 0]
    s["donation share among waste rows"] = float((wr.Donation_Made == "Yes").mean())
    for k in ["Low", "Medium", "High"]:
        s[f"Waste_Level share: {k}"] = float((df.Waste_Level == k).mean())
    for k in ["Expired", "Low Demand", "Overproduction", "Storage Issue"]:
        s[f"reason share among waste rows: {k}"] = float((wr.Waste_Reason == k).mean())
    return pd.Series(s, name=name)


def acf(x: np.ndarray, k: int) -> float:
    x = x - x.mean()
    denom = (x * x).sum()
    if denom == 0:
        return 0.0
    return float((x[:-k] * x[k:]).sum() / denom)


def main():
    print("==================================================")
    print("TASK 0: LOAD AND VERIFY REPORT")
    print("==================================================")
    
    # 1. Load sequence dataset
    print(f"\nLoading sequence dataset from: {SEQ_PATH}")
    seq_df = load_synthetic_panel(SEQ_PATH, validate=True, enforce_invariants=True)
    print(f"Loaded shape: {seq_df.shape} (Rows: {len(seq_df)}, Columns: {seq_df.shape[1]})")
    print(f"Data_Origin: {seq_df['Data_Origin'].unique().tolist()}")
    print(f"Date range: {seq_df['Date'].min().strftime('%Y-%m-%d')} to {seq_df['Date'].max().strftime('%Y-%m-%d')}")
    print(f"Unique days: {seq_df['Date'].nunique()}")
    print(f"Unique shops ({seq_df['Shop_ID'].nunique()}): {sorted(seq_df['Shop_ID'].unique().tolist())}")
    print(f"Unique categories ({seq_df['Food_Category'].nunique()}): {sorted(seq_df['Food_Category'].unique().tolist())}")
    print(f"Total series (shops x categories): {seq_df.groupby(['Shop_ID', 'Food_Category']).ngroups}")

    # 2. Invariants Check
    print("\n--- INVARIANTS CHECK ---")
    invariants = {
        "Remaining = Purchase - Sold": bool((seq_df["Remaining_Stock"] == seq_df["Purchase_Quantity"] - seq_df["Units_Sold"]).all()),
        "Sold = min(Purchase, Demand)": bool((seq_df["Units_Sold"] == np.minimum(seq_df["Purchase_Quantity"], seq_df["Daily_Demand"])).all()),
        "Waste <= Remaining": bool((seq_df["Waste_Quantity"] <= seq_df["Remaining_Stock"]).all()),
        "Donated_Units <= Waste_Quantity": bool((seq_df["Donated_Units"] <= seq_df["Waste_Quantity"]).all()),
        "Donation_Made = Yes only when waste > 0": bool((seq_df[seq_df["Donation_Made"] == "Yes"]["Waste_Quantity"] > 0).all()),
        "Carried_Forward = Remaining - Waste": bool((seq_df["Carried_Forward_Units"] == seq_df["Remaining_Stock"] - seq_df["Waste_Quantity"]).all()),
        "Expiry_Date = Date + Shelf_Life_Days": bool(((seq_df["Expiry_Date"] - seq_df["Date"]).dt.days == seq_df["Shelf_Life_Days"]).all()),
        "Exactly one row per (Date, Shop_ID, Food_Category)": bool(seq_df.duplicated(["Date", "Shop_ID", "Food_Category"]).sum() == 0),
        "No missing days in any of the 72 series": bool(
            (seq_df.groupby(["Shop_ID", "Food_Category"])["Date"].nunique() == seq_df["Date"].nunique()).all()
        ),
        "No negative quantities in numeric columns": bool(
            (seq_df[["Purchase_Quantity", "Units_Sold", "Remaining_Stock", "Waste_Quantity", "Daily_Demand", "Donated_Units", "Carried_Forward_Units"]] >= 0).all().all()
        ),
        "No missing values in mandatory columns": bool(seq_df.drop(columns=["Festival"]).isna().sum().sum() == 0),
    }
    for inv_name, status in invariants.items():
        print(f"  [{'PASS' if status else 'FAIL'}] {inv_name}")

    # 3. Autocorrelation Analysis
    print("\n--- AUTOCORRELATION OF DAILY DEMAND ---")
    ser = seq_df.pivot_table(index="Date", columns=["Shop_ID", "Food_Category"], values="Daily_Demand")
    lags = [1, 7, 14, 28, 365]
    
    acf_results = []
    for lag in lags:
        v = [acf(ser[c].values.astype(float), lag) for c in ser.columns]
        acf_results.append({
            "Lag (days)": lag,
            "Mean ACF (72 series)": float(np.mean(v)),
            "Std ACF": float(np.std(v)),
            "Min ACF": float(np.min(v)),
            "Max ACF": float(np.max(v)),
        })
    acf_df = pd.DataFrame(acf_results)
    print(acf_df.to_string(index=False))

    # Benchmark CSV ACF for comparison
    bench_df = pd.read_csv(BENCH_PATH, parse_dates=["Date"])
    bs = bench_df.dropna(subset=["Daily_Demand"]).groupby(["Date", "Food_Category"])["Daily_Demand"].mean().unstack()
    bench_acfs = {}
    for l in [1, 7, 14, 28]:
        bench_acfs[l] = float(np.nanmean([bs[c].dropna().autocorr(l) for c in bs.columns if len(bs[c].dropna()) > l]))
    print("\nBenchmark CSV (category-level daily mean) ACF:")
    for l, val in bench_acfs.items():
        print(f"  Lag {l}: {val:.4f}")

    # 4. Calibration vs Benchmark CSV and Comparison vs synthetic_v1 (validation_report.md)
    print("\n--- CALIBRATION VS BENCHMARK CSV & SYNTHETIC V1 ---")
    bench_stats = compute_calibration_stats(bench_df, "Benchmark (food_waste)")
    seq_stats = compute_calibration_stats(seq_df, "Synthetic Seq v2 (72 series)")
    
    syn_v1_df = pd.read_csv(SYN_V1_PATH, parse_dates=["Date"]) if SYN_V1_PATH.exists() else None
    syn_v1_stats = compute_calibration_stats(syn_v1_df, "Synthetic v1 (48 series)") if syn_v1_df is not None else None

    cmp_df = pd.concat([bench_stats, seq_stats], axis=1)
    if syn_v1_stats is not None:
        cmp_df = pd.concat([cmp_df, syn_v1_stats], axis=1)
        cmp_df["Diff (Seq v2 - Bench)"] = cmp_df["Synthetic Seq v2 (72 series)"] - cmp_df["Benchmark (food_waste)"]
        cmp_df["Diff (Seq v2 - Syn v1)"] = cmp_df["Synthetic Seq v2 (72 series)"] - cmp_df["Synthetic v1 (48 series)"]
    else:
        cmp_df["Diff (Seq v2 - Bench)"] = cmp_df["Synthetic Seq v2 (72 series)"] - cmp_df["Benchmark (food_waste)"]

    pd.set_option("display.max_rows", 50)
    pd.set_option("display.float_format", lambda x: f"{x:.4f}")
    print(cmp_df.to_string())


if __name__ == "__main__":
    main()
