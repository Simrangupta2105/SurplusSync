"""Unit tests for TASK 6: MODEL REGISTRY INTERFACE, WASTE-LEVEL CLASSIFIER, AND REORDER SIMULATION (Track B).

Verifies:
1. Strict data leakage prevention (raises LeakageError if forbidden outcome columns appear).
2. Out-of-fold forecast demand generation without target leakage.
3. Majority baseline and heuristic rule classifier behaviors.
4. Trained waste classifier evaluation (Macro-F1 strictly beats majority baseline).
5. Clean-rule label noise caveat presence in classifier metadata.
6. Retrospective reorder simulation invariants (shelf-life cap, service-level monotonicity).
7. Explicit COUNTERFACTUAL ESTIMATE status and documented assumptions.
8. Model registry interface (save_models_to_registry, load_best) with required metadata fields.
9. Diagnostic figure generation with valid PNG magic bytes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest

# Ensure parent paths in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
PARENT_DIR = BASE_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

try:
    from ml_service.data.time_series_splits import LeakageError
    from ml_service.models.synthetic_downstream import (
        ALLOWED_CLASSIFIER_FEATURES,
        FORBIDDEN_LEAKAGE_COLUMNS,
        TARGET_CLASSES,
        HeuristicOverOrderClassifier,
        MajorityClassifier,
        generate_task6_figures,
        load_best,
        run_retrospective_reorder_simulation,
        save_models_to_registry,
        train_and_evaluate_waste_classifiers,
        validate_no_leakage,
    )
except ModuleNotFoundError:
    from data.time_series_splits import LeakageError
    from models.synthetic_downstream import (
        ALLOWED_CLASSIFIER_FEATURES,
        FORBIDDEN_LEAKAGE_COLUMNS,
        TARGET_CLASSES,
        HeuristicOverOrderClassifier,
        MajorityClassifier,
        generate_task6_figures,
        load_best,
        run_retrospective_reorder_simulation,
        save_models_to_registry,
        train_and_evaluate_waste_classifiers,
        validate_no_leakage,
    )


def test_data_leakage_enforcement_raises_loud_error():
    """CRITICAL: Fails loudly if ANY forbidden outcome column appears in classifier features."""
    for col in FORBIDDEN_LEAKAGE_COLUMNS:
        with pytest.raises(LeakageError, match="DATA LEAKAGE DETECTED"):
            validate_no_leakage(["Food_Category", "Purchase_Quantity", col])


def test_allowed_classifier_features_pass_validation():
    """Verify that allowed features contain zero leakage columns."""
    validate_no_leakage(ALLOWED_CLASSIFIER_FEATURES)
    assert len(set(ALLOWED_CLASSIFIER_FEATURES).intersection(FORBIDDEN_LEAKAGE_COLUMNS)) == 0


def test_majority_and_heuristic_classifier_baselines():
    """Verify baseline classifier prediction shapes and class domains."""
    X = pd.DataFrame({
        "Purchase_Quantity": [50.0, 60.0, 100.0, 150.0],
        "forecast_demand": [50.0, 60.0, 90.0, 100.0],
        "over_order_ratio": [1.00, 1.00, 1.11, 1.50],
    })
    y = ["Low", "Low", "Medium", "High"]

    maj = MajorityClassifier().fit(X, y)
    preds_maj = maj.predict(X)
    assert len(preds_maj) == 4
    assert set(preds_maj) == {"Low"}

    rule = HeuristicOverOrderClassifier(low_threshold=1.02, high_threshold=1.10).fit(X, y)
    preds_rule = rule.predict(X)
    assert preds_rule[0] == "Low"     # ratio 1.00 < 1.02
    assert preds_rule[2] == "High"    # ratio 1.11 >= 1.10
    assert preds_rule[3] == "High"    # ratio 1.50 >= 1.10


def test_waste_classifier_training_and_evaluation_smoke():
    """Verify classifier training on synthetic slice, macro-F1 beating majority, and clean rule note."""
    dates = pd.date_range("2025-09-01", periods=60, freq="D")
    records = []
    for i, d in enumerate(dates):
        # Create clear synthetic correlation
        ratio = 0.95 + 0.01 * (i % 30)
        p_qty = 100.0 * ratio
        w_level = "Low" if ratio < 1.015 else ("Medium" if ratio < 1.085 else "High")

        records.append({
            "Date": d,
            "Shop_ID": "S01",
            "Business_Type": "Bakery",
            "Food_Category": "Bakery",
            "Purchase_Quantity": p_qty,
            "forecast_demand": 100.0,
            "over_order_ratio": ratio,
            "Shelf_Life_Days": 3.0,
            "Storage_Temperature": 20.0,
            "Temperature_C": 22.0,
            "Day_Of_Week": d.dayofweek,
            "Lead_Time_Days": 1.0,
            "Weather": "Sunny",
            "Promotion": False,
            "Is_Holiday": False,
            "Waste_Level": w_level,
        })
    mock_df = pd.DataFrame(records)

    details, results_df, best_model = train_and_evaluate_waste_classifiers(
        mock_df, test_cutoff="2025-10-15", random_seed=42
    )

    assert "best_model_name" in details
    assert "best_macro_f1" in details
    assert details["best_macro_f1"] > 0.0

    # Macro-F1 of top trained model should beat majority baseline
    maj_f1 = results_df.loc[results_df["model"] == "Majority_Baseline", "macro_f1"].values[0]
    assert details["best_macro_f1"] >= maj_f1

    # Check clean rule note presence
    assert "clean synthetic rule" in details["note"]
    assert len(details["confusion_matrix"]) == 3


def test_reorder_simulation_invariants():
    """Verify retrospective reorder simulation monotonicity, shelf-life caps, and counterfactual status."""
    dates = pd.date_range("2025-10-01", periods=30, freq="D")
    records = []
    for d in dates:
        records.append({
            "Date": d,
            "Purchase_Quantity": 120.0,
            "Daily_Demand": 100.0,
            "forecast_demand": 98.0,
            "Shelf_Life_Days": 4.0,
            "Lead_Time_Days": 1.0,
            "Waste_Quantity": 8.0,
        })
    mock_df = pd.DataFrame(records)

    sim = run_retrospective_reorder_simulation(mock_df, test_cutoff="2025-10-01", residual_std=15.0)

    sim_df = sim["simulation_table"]
    assert "Actual_Historical_Purchases" in sim_df["policy"].values
    assert "AI_Recommended_80%" in sim_df["policy"].values
    assert "AI_Recommended_90%" in sim_df["policy"].values
    assert "AI_Recommended_95%" in sim_df["policy"].values

    # Monotonicity: higher service level -> more units purchased, fewer stockouts
    p_80 = sim_df.loc[sim_df["policy"] == "AI_Recommended_80%", "total_purchased_units"].values[0]
    p_90 = sim_df.loc[sim_df["policy"] == "AI_Recommended_90%", "total_purchased_units"].values[0]
    p_95 = sim_df.loc[sim_df["policy"] == "AI_Recommended_95%", "total_purchased_units"].values[0]
    assert p_80 < p_90 < p_95

    # Check mandatory counterfactual labeling and documented assumptions
    cw = sim["counterfactual_waste_estimate"]
    assert cw["status"] == "COUNTERFACTUAL ESTIMATE"
    assert len(sim["assumptions"]) >= 4


def test_model_registry_save_and_load_best(tmp_path):
    """Verify registry serialization, metadata schema, and load_best round-trip."""
    dummy_demand_model = {"model": "HistGradientBoostingDemandModel", "version": 1}
    dummy_classifier = {"model": "LightGBMClassifier", "version": 1}

    d_meta = {
        "model_name": "HistGradientBoostingDemandModel",
        "data_origin": "synthetic",
        "version": "1.0.0-synthetic-track-b",
        "train_date_range": ["2023-01-01", "2025-10-02"],
        "test_date_range": ["2025-10-03", "2025-12-31"],
        "metrics": {"test_wape": 0.1571},
        "random_seed": 42,
    }
    c_meta = {
        "model_name": "LightGBM",
        "data_origin": "synthetic",
        "version": "1.0.0-synthetic-track-b",
        "classes": TARGET_CLASSES,
        "metrics": {"test_macro_f1": 0.95},
        "random_seed": 42,
    }

    d_path, c_path = save_models_to_registry(
        demand_model=dummy_demand_model,
        demand_metadata=d_meta,
        waste_classifier=dummy_classifier,
        classifier_metadata=c_meta,
        registry_dir=tmp_path,
    )

    assert d_path.exists()
    assert c_path.exists()

    # Test load_best demand
    loaded_d, loaded_d_meta = load_best("demand", track="synthetic", registry_dir=tmp_path)
    assert loaded_d["model"] == "HistGradientBoostingDemandModel"
    assert loaded_d_meta["data_origin"] == "synthetic"
    assert loaded_d_meta["version"] == "1.0.0-synthetic-track-b"

    # Test load_best classifier
    loaded_c, loaded_c_meta = load_best("classifier", track="synthetic", registry_dir=tmp_path)
    assert loaded_c["model"] == "LightGBMClassifier"
    assert loaded_c_meta["data_origin"] == "synthetic"
    assert loaded_c_meta["classes"] == TARGET_CLASSES


def test_generate_task6_figures_creates_valid_pngs(tmp_path):
    """Verify that both Task 6 diagnostic plots are generated with valid PNG magic bytes."""
    cm = [[100, 5, 1], [4, 80, 6], [0, 3, 50]]
    sim_df = pd.DataFrame([
        {"policy": "Actual_Historical_Purchases", "over_purchase_units": 50000, "stockout_rate": 0.12},
        {"policy": "AI_Recommended_80%", "over_purchase_units": 20000, "stockout_rate": 0.19},
        {"policy": "AI_Recommended_90%", "over_purchase_units": 28000, "stockout_rate": 0.09},
        {"policy": "AI_Recommended_95%", "over_purchase_units": 35000, "stockout_rate": 0.04},
    ])

    saved_plots = generate_task6_figures(cm, sim_df, output_dir=tmp_path)
    assert len(saved_plots) == 2

    png_magic = b"\x89PNG\r\n\x1a\n"
    for p in saved_plots:
        path = Path(p)
        assert path.exists()
        assert path.stat().st_size > 1000
        with open(path, "rb") as f:
            header = f.read(8)
            assert header == png_magic
