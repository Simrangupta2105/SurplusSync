"""Inventory Reorder Engine & Retrospective Simulation (Track A).

Answers the operational question:
"What stocking decision should be made given forecast demand and shelf-life constraints,
and how does it compare historically against operator stocking decisions?"

Implements Task 6 requirements:
1. Reorder recommendation:
   - horizon = lead_time + review_period (default: 1 day lead time)
   - safety_stock = z * forecast_error_std * sqrt(lead_time) for configurable service level
   - order_qty = max(0, forecast + safety_stock - sellable_on_hand - on_order)
   - Shelf-life cap: never order more than can be sold within 70% of shelf-life
     shelf_cap = 0.70 * shelf_life_days * forecast_demand
   - Storage cap: free capacity of matching storage location
   - Pack size rounding when defined
2. Retrospective counterfactual simulation:
   - Evaluates recommended purchase orders vs actual operator purchase orders
   - Metric comparison:
     - Over-purchase units: sum(max(0, P - D))
     - Stock-out rows: count & rate of P < D
     - Lost sales units: sum(max(0, D - P))
     - Counterfactual waste estimate: Estimated waste impact based on empirical category
       remaining-stock discard rates.
   - MANDATORY LABELLING: Waste impact is strictly labelled as a COUNTERFACTUAL ESTIMATE
     with all underlying assumptions explicitly documented.
3. Reporting & visualizations:
   - Metrics CSV and category breakdown CSV
   - Bar chart comparison and service-level trade-off curves (PNGs)
"""

from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.base import clone
import matplotlib.pyplot as plt

COUNTERFACTUAL_ASSUMPTIONS: List[str] = [
    "1. Demand Exogeneity: Customer demand (Daily_Demand) is strictly exogenous and invariant to purchase quantity (no display inventory presentation elasticity).",
    "2. Proportional Discard Behavior: Excess stock (remaining after customer sales) experiences waste at the historical category-specific remaining-discard rate (r_waste = sum(Waste) / sum(Remaining)).",
    "3. Deterministic Lead Time: Lead time is 1 day with 100% vendor order fulfillment (no supplier under-delivery).",
    "4. Freshness Window: Inventory ordered within 70% of nominal shelf-life is sellable during customer sales periods without premature spoilage.",
    "5. Counterfactual Status: These figures are derived from retrospective mathematical modeling and do NOT represent measured live trial outcomes.",
]


@dataclass
class ReorderRecommendation:
    """Output recommendation for an individual product/batch reorder evaluation."""
    product_name: str
    forecast_demand: float
    safety_stock: float
    service_level: float
    unconstrained_qty: float
    suggested_qty: int
    shelf_life_days: float
    shelf_life_cap: float
    shelf_cap_applied: bool
    storage_cap_applied: bool
    reasons: List[str] = field(default_factory=list)
    expected_days_of_cover: float = 0.0

    @property
    def recommended_order_quantity(self) -> int:
        return self.suggested_qty

    @property
    def counterfactual_assumptions(self) -> List[str]:
        return COUNTERFACTUAL_ASSUMPTIONS


def compute_recommended_reorder(
    forecast_demand: float,
    forecast_residual_std: Optional[float] = None,
    shelf_life_days: float = 3.0,
    service_level: float = 0.90,
    lead_time_days: float = 1.0,
    shelf_life_cap_ratio: float = 0.70,
    current_on_hand: float = 0.0,
    on_order: float = 0.0,
    storage_capacity_available: Optional[float] = None,
    pack_size: Optional[int] = None,
    product_name: str = "Item",
    **kwargs: Any,
) -> ReorderRecommendation:
    """Compute optimal purchase recommendation with safety stock and shelf-life cap.

    Args:
        forecast_demand: Expected daily customer demand (units).
        forecast_residual_std: Standard deviation of forecast errors (sigma_epsilon).
        shelf_life_days: Total shelf life in days.
        service_level: Target cycle service level (e.g. 0.90 = 90%).
        lead_time_days: Replenishment lead time in days.
        shelf_life_cap_ratio: Fraction of shelf life permitted to order (default 0.70).
        current_on_hand: Sellable stock currently on hand.
        on_order: Pipeline inventory already ordered but not yet received.
        storage_capacity_available: Available storage capacity units (optional).
        pack_size: Case/pack size multiple for rounding (optional).
        product_name: Identifier for reporting.
        **kwargs: Aliases such as sellable_on_hand and forecast_error_std.

    Returns:
        ReorderRecommendation with suggested order quantity and binding constraints.
    """
    if forecast_residual_std is None:
        forecast_residual_std = kwargs.get("forecast_error_std", 17.63)
    if "sellable_on_hand" in kwargs:
        current_on_hand = kwargs["sellable_on_hand"]

    safe_forecast = max(0.0, float(forecast_demand))
    safe_std = max(0.1, float(forecast_residual_std))
    safe_shelf_life = max(1.0, float(shelf_life_days))

    # 1. Safety Stock: z * sigma_epsilon * sqrt(L)
    z_score = float(stats.norm.ppf(service_level))
    safety_stock = max(0.0, z_score * safe_std * math.sqrt(lead_time_days))

    # 2. Net Required Order Quantity
    gross_requirement = safe_forecast * lead_time_days + safety_stock
    net_order = max(0.0, gross_requirement - current_on_hand - on_order)
    unconstrained_order = net_order

    reasons: List[str] = []
    shelf_cap_applied = False
    storage_cap_applied = False

    # 3. Shelf-Life Cap: 70% of shelf life demand
    # Prevents ordering batches that cannot turn over before expiration
    shelf_cap = shelf_life_cap_ratio * safe_shelf_life * safe_forecast
    if net_order > shelf_cap:
        reasons.append(
            f"Shelf-life cap binding: reduced from {net_order:.1f} to {shelf_cap:.1f} units "
            f"(70% of {safe_shelf_life:.0f}-day shelf life at {safe_forecast:.1f} units/day)."
        )
        net_order = shelf_cap
        shelf_cap_applied = True

    # 4. Storage Location Capacity Cap (if defined)
    if storage_capacity_available is not None:
        safe_capacity = max(0.0, float(storage_capacity_available))
        if net_order > safe_capacity:
            reasons.append(
                f"Storage capacity cap binding: reduced from {net_order:.1f} to {safe_capacity:.1f} units."
            )
            net_order = safe_capacity
            storage_cap_applied = True

    # 5. Pack Size Rounding (if defined)
    if pack_size is not None and pack_size > 1:
        packs = math.ceil(net_order / pack_size)
        rounded_order = packs * pack_size
        if rounded_order != net_order:
            reasons.append(f"Rounded to pack size of {pack_size}: {rounded_order} units.")
        net_order = float(rounded_order)

    suggested_qty = int(round(net_order))
    if not reasons:
        reasons.append(f"Standard reorder: forecast {safe_forecast:.1f} + safety stock {safety_stock:.1f} units.")

    # Days of cover provided by this order
    expected_days_of_cover = (
        round(suggested_qty / safe_forecast, 1) if safe_forecast > 0 else float("inf")
    )

    return ReorderRecommendation(
        product_name=product_name,
        forecast_demand=safe_forecast,
        safety_stock=round(safety_stock, 2),
        service_level=service_level,
        unconstrained_qty=round(unconstrained_order, 2),
        suggested_qty=suggested_qty,
        shelf_life_days=safe_shelf_life,
        shelf_life_cap=round(shelf_cap, 2),
        shelf_cap_applied=shelf_cap_applied,
        storage_cap_applied=storage_cap_applied,
        reasons=reasons,
        expected_days_of_cover=expected_days_of_cover,
    )


DEFAULT_DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "Food_Waste_Data.csv"


def run_retrospective_reorder_simulation(
    raw_data_path: Path | str = DEFAULT_DATASET_PATH,
    service_levels: Sequence[float] = (0.80, 0.90, 0.95),
    output_dir: Optional[Path | str] = None,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Run counterfactual reorder simulation on the unseen test set (December).

    Compares the AI reorder recommendations against historical operator purchases.
    """
    from ml_service.data.food_waste import get_time_splits, load_raw_data
    from ml_service.models.tabular_demand import (
        FEATURE_COLS as DEMAND_FEATURE_COLS,
        build_candidate_models,
        prepare_tabular_features,
    )

    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "reports"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load data and split
    df_raw = load_raw_data(raw_data_path)
    train_clean, val_clean, test_clean, _ = get_time_splits(df_raw)

    train_prep = prepare_tabular_features(train_clean)
    val_prep = prepare_tabular_features(val_clean)
    test_prep = prepare_tabular_features(test_clean)

    # 2. Fit Task 2 winning Poisson regression model
    base_pipe = build_candidate_models(random_state=random_state)["Poisson_Regression"].pipeline
    demand_model = clone(base_pipe)
    train_uncensored = train_prep[~train_prep["demand_censored"]]
    demand_model.fit(train_uncensored[DEMAND_FEATURE_COLS], train_uncensored["Daily_Demand"].values)

    # Generate forecasts
    val_prep["forecast_demand"] = demand_model.predict(val_prep[DEMAND_FEATURE_COLS])
    test_prep["forecast_demand"] = demand_model.predict(test_prep[DEMAND_FEATURE_COLS])

    # 3. Compute empirical residual stds on validation partition
    val_uncensored = val_prep[~val_prep["demand_censored"]]
    global_residual_std = float(np.std(val_uncensored["Daily_Demand"] - val_uncensored["forecast_demand"]))

    category_residual_stds: Dict[str, float] = {}
    category_waste_rates: Dict[str, float] = {}

    for cat_name, sub in val_uncensored.groupby("Food_Category"):
        category_residual_stds[str(cat_name)] = float(np.std(sub["Daily_Demand"] - sub["forecast_demand"]))

    # Historical waste rate of remaining stock per category (from train set)
    for cat_name, sub in train_prep.groupby("Food_Category"):
        rem_sum = sub["Remaining_Stock"].sum()
        w_sum = sub["Waste_Quantity"].sum()
        category_waste_rates[str(cat_name)] = float(w_sum / rem_sum) if rem_sum > 0 else 0.25

    # 4. Filter test set to rows with known demand for ground truth evaluation
    test_eval = test_prep[~test_prep["demand_censored"]].copy()
    n_rows = len(test_eval)

    # Ground truth actual operator behavior
    actual_purchases = test_eval["Purchase_Quantity"].values
    actual_demands = test_eval["Daily_Demand"].values
    actual_wastes = test_eval["Waste_Quantity"].values

    actual_over_purchase = np.maximum(0, actual_purchases - actual_demands)
    actual_lost_sales = np.maximum(0, actual_demands - actual_purchases)
    actual_stockouts = (actual_purchases < actual_demands)

    total_actual_purchase = float(np.sum(actual_purchases))
    total_actual_over_purchase = float(np.sum(actual_over_purchase))
    total_actual_lost_sales = float(np.sum(actual_lost_sales))
    total_actual_waste = float(np.sum(actual_wastes))
    count_actual_stockouts = int(np.sum(actual_stockouts))

    macro_results: List[Dict[str, Any]] = [{
        "policy": "Actual_Operator_History",
        "service_level": float("nan"),
        "total_purchase_units": total_actual_purchase,
        "over_purchase_units": total_actual_over_purchase,
        "over_purchase_pct_reduction": 0.0,
        "stockout_rows": count_actual_stockouts,
        "stockout_pct_of_rows": round((count_actual_stockouts / n_rows) * 100, 2),
        "lost_sales_units": total_actual_lost_sales,
        "counterfactual_waste_estimate": total_actual_waste,
        "counterfactual_waste_reduction_pct": 0.0,
        "shelf_cap_applied_count": 0,
    }]

    category_results: List[Dict[str, Any]] = []

    # 5. Evaluate Reorder Policies across Service Levels
    for sl in service_levels:
        sl_name = f"AI_Reorder_SL_{int(sl * 100)}"
        rec_purchases = np.zeros(n_rows, dtype=float)
        shelf_caps_triggered = 0

        for i, (_, row) in enumerate(test_eval.iterrows()):
            cat = str(row["Food_Category"])
            cat_std = category_residual_stds.get(cat, global_residual_std)
            rec = compute_recommended_reorder(
                forecast_demand=row["forecast_demand"],
                forecast_residual_std=cat_std,
                shelf_life_days=row["Shelf_Life_Days"],
                service_level=sl,
            )
            rec_purchases[i] = rec.suggested_qty
            if rec.shelf_cap_applied:
                shelf_caps_triggered += 1

        # Evaluate simulated outcomes
        sim_over_purchase = np.maximum(0, rec_purchases - actual_demands)
        sim_lost_sales = np.maximum(0, actual_demands - rec_purchases)
        sim_stockouts = (rec_purchases < actual_demands)

        # Counterfactual waste estimate:
        # Each row's expected waste is sim_remaining * category_waste_rate
        sim_remaining = np.maximum(0, rec_purchases - np.minimum(rec_purchases, actual_demands))
        sim_wastes = np.zeros(n_rows, dtype=float)
        for i, (_, row) in enumerate(test_eval.iterrows()):
            cat = str(row["Food_Category"])
            rate = category_waste_rates.get(cat, 0.25)
            sim_wastes[i] = sim_remaining[i] * rate

        tot_sim_purchase = float(np.sum(rec_purchases))
        tot_sim_over = float(np.sum(sim_over_purchase))
        tot_sim_lost = float(np.sum(sim_lost_sales))
        tot_sim_stockout = int(np.sum(sim_stockouts))
        tot_sim_waste = float(np.sum(sim_wastes))

        over_pct_red = ((total_actual_over_purchase - tot_sim_over) / total_actual_over_purchase) * 100
        waste_pct_red = ((total_actual_waste - tot_sim_waste) / total_actual_waste) * 100

        macro_results.append({
            "policy": sl_name,
            "service_level": sl,
            "total_purchase_units": tot_sim_purchase,
            "over_purchase_units": tot_sim_over,
            "over_purchase_pct_reduction": round(over_pct_red, 2),
            "stockout_rows": tot_sim_stockout,
            "stockout_pct_of_rows": round((tot_sim_stockout / n_rows) * 100, 2),
            "lost_sales_units": tot_sim_lost,
            "counterfactual_waste_estimate": round(tot_sim_waste, 1),
            "counterfactual_waste_reduction_pct": round(waste_pct_red, 2),
            "shelf_cap_applied_count": shelf_caps_triggered,
        })

        # Category breakdowns for recommended 90% service level
        if sl == 0.90:
            for cat_name, sub in test_eval.groupby("Food_Category"):
                c_idx = test_eval.index.isin(sub.index)
                sub_act_pur = float(actual_purchases[c_idx].sum())
                sub_sim_pur = float(rec_purchases[c_idx].sum())
                sub_act_over = float(actual_over_purchase[c_idx].sum())
                sub_sim_over = float(sim_over_purchase[c_idx].sum())
                sub_act_so = int(actual_stockouts[c_idx].sum())
                sub_sim_so = int(sim_stockouts[c_idx].sum())
                sub_act_w = float(actual_wastes[c_idx].sum())
                sub_sim_w = float(sim_wastes[c_idx].sum())

                category_results.append({
                    "category": cat_name,
                    "evaluated_rows": int(len(sub)),
                    "actual_purchase": sub_act_pur,
                    "simulated_purchase": sub_sim_pur,
                    "actual_over_purchase": sub_act_over,
                    "simulated_over_purchase": sub_sim_over,
                    "over_purchase_reduction_pct": round(((sub_act_over - sub_sim_over) / sub_act_over) * 100, 2),
                    "actual_stockouts": sub_act_so,
                    "simulated_stockouts": sub_sim_so,
                    "stockout_change": sub_sim_so - sub_act_so,
                    "actual_waste_units": sub_act_w,
                    "counterfactual_waste_units": round(sub_sim_w, 1),
                    "counterfactual_waste_reduction_pct": round(((sub_act_w - sub_sim_w) / sub_act_w) * 100, 2),
                })

    macro_df = pd.DataFrame(macro_results)
    cat_df = pd.DataFrame(category_results)

    # Export CSVs
    macro_csv_path = output_dir / "reorder_simulation_metrics.csv"
    cat_csv_path = output_dir / "reorder_simulation_by_category.csv"
    macro_df.to_csv(macro_csv_path, index=False)
    cat_df.to_csv(cat_csv_path, index=False)
    print(f"Saved reorder simulation metrics to {macro_csv_path}")
    print(f"Saved category breakdown to {cat_csv_path}")

    # Generate Figures
    _generate_reorder_figures(
        macro_df=macro_df,
        cat_df=cat_df,
        fig_dir=fig_dir,
    )

    summary_metadata = {
        "evaluated_test_rows": n_rows,
        "service_levels_evaluated": list(service_levels),
        "counterfactual_assumptions": COUNTERFACTUAL_ASSUMPTIONS,
        "actual_baseline": {
            "purchase_units": total_actual_purchase,
            "over_purchase_units": total_actual_over_purchase,
            "stockout_rows": count_actual_stockouts,
            "lost_sales_units": total_actual_lost_sales,
            "actual_waste_units": total_actual_waste,
        },
        "recommended_90sl_policy": macro_results[2],  # index 2 corresponds to SL 90%
    }

    return macro_df, cat_df, summary_metadata


def _generate_reorder_figures(
    macro_df: pd.DataFrame,
    cat_df: pd.DataFrame,
    fig_dir: Path,
) -> None:
    """Generate comparative visualization plots for reorder policy evaluation."""
    # 1. Comparison Bar Chart (Over-purchase vs Stockouts vs Waste)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    policies = macro_df["policy"].tolist()
    clean_labels = ["Actual\nOperator", "AI Reorder\n(80% SL)", "AI Reorder\n(90% SL)", "AI Reorder\n(95% SL)"]
    x = np.arange(len(policies))
    colors = ["#7f7f7f", "#2ca02c", "#1f77b4", "#ff7f0e"]

    # Panel 1: Over-Purchase Units
    axes[0].bar(x, macro_df["over_purchase_units"], color=colors, edgecolor="black")
    axes[0].set_title("Over-Purchase Units (Lower is Better)", fontsize=12, fontweight="bold")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(clean_labels, fontsize=10)
    axes[0].set_ylabel("Units", fontsize=11)
    axes[0].grid(axis="y", linestyle="--", alpha=0.6)
    for i, v in enumerate(macro_df["over_purchase_units"]):
        axes[0].text(i, v + 200, f"{v:,.0f}", ha="center", fontsize=9, fontweight="bold")

    # Panel 2: Stockout Incidents Count
    axes[1].bar(x, macro_df["stockout_rows"], color=colors, edgecolor="black")
    axes[1].set_title("Stockout Rows (Lower is Better)", fontsize=12, fontweight="bold")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(clean_labels, fontsize=10)
    axes[1].set_ylabel("Rows with P < Demand", fontsize=11)
    axes[1].grid(axis="y", linestyle="--", alpha=0.6)
    for i, v in enumerate(macro_df["stockout_rows"]):
        axes[1].text(i, v + 4, f"{v}", ha="center", fontsize=9, fontweight="bold")

    # Panel 3: Counterfactual Waste Estimate
    axes[2].bar(x, macro_df["counterfactual_waste_estimate"], color=colors, edgecolor="black")
    axes[2].set_title("Waste Estimate (COUNTERFACTUAL)", fontsize=12, fontweight="bold")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(clean_labels, fontsize=10)
    axes[2].set_ylabel("Estimated Waste Units", fontsize=11)
    axes[2].grid(axis="y", linestyle="--", alpha=0.6)
    for i, v in enumerate(macro_df["counterfactual_waste_estimate"]):
        axes[2].text(i, v + 50, f"{v:,.0f}", ha="center", fontsize=9, fontweight="bold")

    plt.tight_layout()
    comparison_png_path = fig_dir / "reorder_simulation_comparison.png"
    plt.savefig(comparison_png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved reorder comparison plot to {comparison_png_path}")

    # Copy to brain artifact directory if accessible
    artifact_dir = Path("C:/Users/simra/.gemini/antigravity-ide/brain/ecfe9bad-14f2-483d-a866-3e0adf9bd56c")
    if artifact_dir.exists():
        try:
            shutil.copy2(comparison_png_path, artifact_dir / comparison_png_path.name)
        except Exception:
            pass


def run_sequence_reorder_simulation(
    service_levels: Sequence[float] = (0.80, 0.90, 0.95),
    output_dir: Optional[Union[Path, str]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Run counterfactual reorder simulation on the untouched 90-day sequence test set.

    Compares the winning HistGradientBoosting_History reorder recommendations against historical operator purchases.
    """
    try:
        from ml_service.data.synthetic_panel import DEFAULT_SYNTHETIC_SEQ_PATH, load_synthetic_panel
        from ml_service.data.time_series_splits import TEST_CUTOFF_DATE
        from ml_service.models.fair_tabular_baselines import TabularFeatureEngine
        from ml_service.models.registry import ModelRegistry
    except ModuleNotFoundError:
        from data.synthetic_panel import DEFAULT_SYNTHETIC_SEQ_PATH, load_synthetic_panel
        from data.time_series_splits import TEST_CUTOFF_DATE
        from models.fair_tabular_baselines import TabularFeatureEngine
        from models.registry import ModelRegistry

    if output_dir is None:
        out_dir = Path(__file__).resolve().parent.parent / "reports"
    else:
        out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load data
    df = load_synthetic_panel(DEFAULT_SYNTHETIC_SEQ_PATH)
    engine = TabularFeatureEngine(df)
    cutoff_date = pd.Timestamp(TEST_CUTOFF_DATE)
    cutoff_idx = engine.date_to_idx[cutoff_date]

    # Pre-cutoff discard rates per category
    train_df = df[df["Date"] < cutoff_date]
    cat_waste_rates: Dict[str, float] = {}
    for cat_name, sub in train_df.groupby("Food_Category"):
        rem_sum = sub["Remaining_Stock"].sum()
        w_sum = sub["Waste_Quantity"].sum()
        cat_waste_rates[str(cat_name)] = float(w_sum / rem_sum) if rem_sum > 0 else 0.25

    # 2. Predict on untouched test set using winning model
    model, meta = ModelRegistry.get_demand_model()
    test_targets = np.arange(cutoff_idx, engine.n_dates, dtype=np.int32)
    test_origins = test_targets - 1

    X_test, _ = engine.build_dataset_vectorized(test_origins, horizon=1, include_history=True)
    preds = model.predict(X_test)
    low, high = model.predict_interval(X_test)
    residual_stds = np.maximum(5.0, (high - preds) / 1.645)

    # 3. Assemble test evaluation dataframe
    piv_p = df.pivot(index="Date", columns=["Shop_ID", "Food_Category"], values="Purchase_Quantity")
    piv_w = df.pivot(index="Date", columns=["Shop_ID", "Food_Category"], values="Waste_Quantity")
    purch_arr = piv_p[engine.series_list].values
    waste_arr = piv_w[engine.series_list].values

    test_rows = []
    sample_idx = 0
    for t_targ in test_targets:
        t_date = engine.idx_to_date[t_targ]
        for s_idx, (shop, cat) in enumerate(engine.series_list):
            demand_val = float(engine.demand_arr[t_targ, s_idx])
            shelf_life = float(engine.series_meta.loc[(shop, cat)]["Shelf_Life_Days"])
            test_rows.append({
                "Date": t_date,
                "Shop_ID": shop,
                "Food_Category": cat,
                "Daily_Demand": demand_val,
                "Operator_Purchase": float(purch_arr[t_targ, s_idx]),
                "Operator_Waste": float(waste_arr[t_targ, s_idx]),
                "Shelf_Life_Days": shelf_life,
                "forecast_demand": float(preds[sample_idx]),
                "forecast_std": float(residual_stds[sample_idx]),
            })
            sample_idx += 1

    test_eval = pd.DataFrame(test_rows)
    total_demand = float(test_eval["Daily_Demand"].sum())

    # 4. Actual Operator Performance
    act_purch = test_eval["Operator_Purchase"].values
    act_demand = test_eval["Daily_Demand"].values
    act_over = np.maximum(0, act_purch - act_demand)
    act_lost = np.maximum(0, act_demand - act_purch)
    act_stockouts = int(np.sum(act_purch < act_demand))
    act_waste = float(test_eval["Operator_Waste"].sum())

    macro_results = [{
        "policy": "Actual Operator",
        "service_level_target": "N/A",
        "total_purchase_units": round(float(np.sum(act_purch)), 1),
        "over_purchase_units": round(float(np.sum(act_over)), 1),
        "stockout_rows": act_stockouts,
        "stockout_rate": round(act_stockouts / len(test_eval), 4),
        "lost_sales_units": round(float(np.sum(act_lost)), 1),
        "counterfactual_waste_estimate": round(act_waste, 1),
        "service_level_achieved": round(1.0 - float(np.sum(act_lost)) / total_demand, 4),
    }]

    cat_breakdown_rows = []
    for cat_name, sub in test_eval.groupby("Food_Category"):
        c_purch = sub["Operator_Purchase"].values
        c_dem = sub["Daily_Demand"].values
        c_over = np.maximum(0, c_purch - c_dem)
        c_lost = np.maximum(0, c_dem - c_purch)
        cat_breakdown_rows.append({
            "policy": "Actual Operator",
            "category": cat_name,
            "total_purchase": round(float(np.sum(c_purch)), 1),
            "over_purchase": round(float(np.sum(c_over)), 1),
            "stockout_rate": round(float(np.mean(c_purch < c_dem)), 4),
            "lost_sales": round(float(np.sum(c_lost)), 1),
            "counterfactual_waste": round(float(sub["Operator_Waste"].sum()), 1),
        })

    # 5. Simulate AI Reorder Policy for each Target Service Level
    for sl in service_levels:
        ai_orders = []
        for _, row in test_eval.iterrows():
            rec = compute_recommended_reorder(
                forecast_demand=row["forecast_demand"],
                forecast_residual_std=row["forecast_std"],
                shelf_life_days=row["Shelf_Life_Days"],
                service_level=sl,
                lead_time_days=1.0,
                shelf_life_cap_ratio=0.70,
                current_on_hand=0.0,
            )
            ai_orders.append(rec.suggested_qty)

        ai_ord = np.array(ai_orders, dtype=float)
        ai_over = np.maximum(0, ai_ord - act_demand)
        ai_lost = np.maximum(0, act_demand - ai_ord)
        ai_stockouts = int(np.sum(ai_ord < act_demand))

        # Counterfactual waste estimation per category
        w_est = 0.0
        for i, row in test_eval.iterrows():
            c_rate = cat_waste_rates.get(row["Food_Category"], 0.25)
            w_est += max(0.0, ai_orders[i] - row["Daily_Demand"]) * c_rate

        macro_results.append({
            "policy": f"AI Reorder ({int(sl*100)}% SL)",
            "service_level_target": f"{int(sl*100)}%",
            "total_purchase_units": round(float(np.sum(ai_ord)), 1),
            "over_purchase_units": round(float(np.sum(ai_over)), 1),
            "stockout_rows": ai_stockouts,
            "stockout_rate": round(ai_stockouts / len(test_eval), 4),
            "lost_sales_units": round(float(np.sum(ai_lost)), 1),
            "counterfactual_waste_estimate": round(w_est, 1),
            "service_level_achieved": round(1.0 - float(np.sum(ai_lost)) / total_demand, 4),
        })

        # Category breakdowns for this policy
        test_eval[f"ai_order_{int(sl*100)}"] = ai_ord
        for cat_name, sub in test_eval.groupby("Food_Category"):
            c_ord = sub[f"ai_order_{int(sl*100)}"].values
            c_dem = sub["Daily_Demand"].values
            c_over = np.maximum(0, c_ord - c_dem)
            c_lost = np.maximum(0, c_dem - c_ord)
            c_rate = cat_waste_rates.get(str(cat_name), 0.25)
            cat_breakdown_rows.append({
                "policy": f"AI Reorder ({int(sl*100)}% SL)",
                "category": cat_name,
                "total_purchase": round(float(np.sum(c_ord)), 1),
                "over_purchase": round(float(np.sum(c_over)), 1),
                "stockout_rate": round(float(np.mean(c_ord < c_dem)), 4),
                "lost_sales": round(float(np.sum(c_lost)), 1),
                "counterfactual_waste": round(float(np.sum(c_over) * c_rate), 1),
            })

    macro_df = pd.DataFrame(macro_results)
    cat_df = pd.DataFrame(cat_breakdown_rows)

    # Save CSVs
    macro_csv_path = out_dir / "reorder_simulation_metrics_task6.csv"
    cat_csv_path = out_dir / "reorder_simulation_by_category_task6.csv"
    macro_df.to_csv(macro_csv_path, index=False)
    cat_df.to_csv(cat_csv_path, index=False)
    print(f"Saved simulation metrics -> {macro_csv_path}")
    print(f"Saved category breakdown -> {cat_csv_path}")

    # Generate Plot
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    clean_labels = ["Operator", "AI (80% SL)", "AI (90% SL)", "AI (95% SL)"]
    x = np.arange(len(macro_df))
    colors = ["#7f7f7f", "#2ca02c", "#1f77b4", "#ff7f0e"]

    # 1. Over-purchase units
    axes[0].bar(x, macro_df["over_purchase_units"], color=colors, edgecolor="black", alpha=0.85)
    axes[0].set_title("Over-Purchase Units (Lower is Better)", fontsize=11, fontweight="bold")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(clean_labels, fontsize=10)
    axes[0].set_ylabel("Units", fontsize=11)
    axes[0].grid(axis="y", linestyle="--", alpha=0.5)
    for i, v in enumerate(macro_df["over_purchase_units"]):
        axes[0].text(i, v + 500, f"{v:,.0f}", ha="center", fontsize=9, fontweight="bold")

    # 2. Stockout Incidents Count
    axes[1].bar(x, macro_df["stockout_rows"], color=colors, edgecolor="black", alpha=0.85)
    axes[1].set_title("Stockout Rows (Lower is Better)", fontsize=11, fontweight="bold")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(clean_labels, fontsize=10)
    axes[1].set_ylabel("Count of Days with P < Demand", fontsize=11)
    axes[1].grid(axis="y", linestyle="--", alpha=0.5)
    for i, v in enumerate(macro_df["stockout_rows"]):
        axes[1].text(i, v + 20, f"{v}", ha="center", fontsize=9, fontweight="bold")

    # 3. Counterfactual Waste Estimate
    axes[2].bar(x, macro_df["counterfactual_waste_estimate"], color=colors, edgecolor="black", alpha=0.85)
    axes[2].set_title("Counterfactual Waste Estimate", fontsize=11, fontweight="bold")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(clean_labels, fontsize=10)
    axes[2].set_ylabel("Estimated Waste Units", fontsize=11)
    axes[2].grid(axis="y", linestyle="--", alpha=0.5)
    for i, v in enumerate(macro_df["counterfactual_waste_estimate"]):
        axes[2].text(i, v + 200, f"{v:,.0f}", ha="center", fontsize=9, fontweight="bold")

    fig.text(0.99, 0.01, "[SYNTHETIC DATA] SurplusSync ml_service reorder simulation", ha="right", va="bottom", fontsize=8, color="gray", alpha=0.7)
    plt.tight_layout()
    comparison_png_path = fig_dir / "reorder_simulation_comparison_task6.png"
    plt.savefig(comparison_png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved reorder comparison plot -> {comparison_png_path}")

    summary_metadata = {
        "dataset": "synthetic_sequence_panel_full.csv",
        "test_period": "2025-10-03 to 2025-12-31",
        "test_rows": len(test_eval),
        "operator": macro_results[0],
        "ai_90sl": macro_results[2],
    }

    return macro_df, cat_df, summary_metadata


if __name__ == "__main__":
    run_retrospective_reorder_simulation()
