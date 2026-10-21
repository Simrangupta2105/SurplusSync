"""Unit and integration tests for Task 6: Reorder Evaluation & Retrospective Simulation.

Verifies:
1. compute_recommended_reorder() logic:
   - Normal case with hand-computed safety stock and z-scores
   - Shelf-life cap binding on highly perishable items (70% shelf life limit)
   - Storage capacity cap binding
   - Pack size multiple rounding
   - On-hand and on-order inventory offsets
2. Retrospective counterfactual simulation invariants:
   - Explicit COUNTERFACTUAL ESTIMATE labelling
   - Multi-service-level trade-off invariants (monotonicity of safety stock and stockouts)
   - AI policy strictly outperforms actual historical operator over-purchasing
3. Report and figure artifact generation.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Any

import pytest
import pandas as pd
from scipy import stats

from ml_service.scoring.reorder import (
    COUNTERFACTUAL_ASSUMPTIONS,
    ReorderRecommendation,
    compute_recommended_reorder,
    run_retrospective_reorder_simulation,
)


def test_reorder_normal_case_hand_computed() -> None:
    """Verify standard reorder calculation against hand-computed values."""
    forecast = 100.0
    sigma = 15.0
    lead_time = 1.0
    sl = 0.90
    z = stats.norm.ppf(sl)  # ~1.28155

    expected_ss = z * sigma * math.sqrt(lead_time)  # ~19.223
    expected_order = round(forecast + expected_ss)   # 119

    rec = compute_recommended_reorder(
        forecast_demand=forecast,
        forecast_residual_std=sigma,
        shelf_life_days=10.0,
        service_level=sl,
        lead_time_days=lead_time,
    )

    assert rec.suggested_qty == expected_order
    assert pytest.approx(rec.safety_stock, abs=0.05) == expected_ss
    assert rec.shelf_cap_applied is False
    assert rec.storage_cap_applied is False
    assert rec.expected_days_of_cover == round(expected_order / forecast, 1)


def test_reorder_shelf_life_cap_binding() -> None:
    """Verify shelf-life cap prevents ordering more than 70% of shelf life demand."""
    forecast = 100.0
    shelf_life = 2.0  # e.g. Prepared Food
    cap_ratio = 0.70
    shelf_cap = cap_ratio * shelf_life * forecast  # 0.70 * 2 * 100 = 140.0

    # Unconstrained order would be 100 + 1.645 * 30 = 149.35 > 140.0
    rec = compute_recommended_reorder(
        forecast_demand=forecast,
        forecast_residual_std=30.0,
        shelf_life_days=shelf_life,
        service_level=0.95,
        shelf_life_cap_ratio=cap_ratio,
    )

    assert rec.shelf_cap_applied is True
    assert rec.suggested_qty == int(round(shelf_cap))
    assert any("Shelf-life cap binding" in r for r in rec.reasons)


def test_reorder_storage_capacity_binding() -> None:
    """Verify storage location capacity strictly bounds order quantity."""
    rec = compute_recommended_reorder(
        forecast_demand=100.0,
        forecast_residual_std=10.0,
        shelf_life_days=10.0,
        service_level=0.90,
        storage_capacity_available=75.0,  # Less than unconstrained ~113
    )

    assert rec.storage_cap_applied is True
    assert rec.suggested_qty == 75
    assert any("Storage capacity cap binding" in r for r in rec.reasons)


def test_reorder_pack_size_rounding() -> None:
    """Verify order quantity rounds up to the nearest multiple of pack size."""
    # Unconstrained is 100 + 1.28 * 10 = 112.8 -> 113. Pack size = 12 -> 120 (10 packs)
    rec = compute_recommended_reorder(
        forecast_demand=100.0,
        forecast_residual_std=10.0,
        shelf_life_days=10.0,
        service_level=0.90,
        pack_size=12,
    )

    assert rec.suggested_qty == 120
    assert rec.suggested_qty % 12 == 0
    assert any("Rounded to pack size of 12" in r for r in rec.reasons)


def test_reorder_on_hand_and_on_order_offsets() -> None:
    """Verify current on-hand and pipeline inventory subtract from order requirement."""
    # Gross requirement: 100 + 15 = 115. On-hand: 60, On-order: 30. Net = 25.
    rec = compute_recommended_reorder(
        forecast_demand=100.0,
        forecast_residual_std=11.7,  # 1.28 * 11.7 ~ 15.0
        shelf_life_days=10.0,
        service_level=0.90,
        current_on_hand=60.0,
        on_order=30.0,
    )

    assert rec.suggested_qty == 25

    # Excess stock results in zero order
    rec_zero = compute_recommended_reorder(
        forecast_demand=100.0,
        forecast_residual_std=10.0,
        shelf_life_days=10.0,
        current_on_hand=200.0,
    )
    assert rec_zero.suggested_qty == 0


def test_counterfactual_labelling_and_assumptions() -> None:
    """CRITICAL RULE: Waste impact must be labelled a COUNTERFACTUAL ESTIMATE with assumptions written out."""
    assert len(COUNTERFACTUAL_ASSUMPTIONS) >= 4
    for assumption in COUNTERFACTUAL_ASSUMPTIONS:
        assert len(assumption) > 20

    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    macro_csv = reports_dir / "reorder_simulation_metrics.csv"
    assert macro_csv.exists()

    df = pd.read_csv(macro_csv)
    assert "counterfactual_waste_estimate" in df.columns
    assert "counterfactual_waste_reduction_pct" in df.columns


def test_retrospective_simulation_tradeoff_invariants() -> None:
    """Verify service level trade-off curve monotonicity and operator benchmark."""
    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    macro_csv = reports_dir / "reorder_simulation_metrics.csv"
    assert macro_csv.exists()

    df = pd.read_csv(macro_csv).set_index("policy")

    # Higher service level -> higher total purchase and higher over-purchase
    assert df.loc["AI_Reorder_SL_80", "total_purchase_units"] < df.loc["AI_Reorder_SL_90", "total_purchase_units"]
    assert df.loc["AI_Reorder_SL_90", "total_purchase_units"] < df.loc["AI_Reorder_SL_95", "total_purchase_units"]

    # Higher service level -> fewer stockouts
    assert df.loc["AI_Reorder_SL_80", "stockout_rows"] > df.loc["AI_Reorder_SL_90", "stockout_rows"]
    assert df.loc["AI_Reorder_SL_90", "stockout_rows"] > df.loc["AI_Reorder_SL_95", "stockout_rows"]

    # AI policy at 90% SL simultaneously achieves:
    # 1. Significantly lower over-purchase units than actual operator
    assert df.loc["AI_Reorder_SL_90", "over_purchase_units"] < df.loc["Actual_Operator_History", "over_purchase_units"]
    # 2. Significantly fewer stockouts than actual operator
    assert df.loc["AI_Reorder_SL_90", "stockout_rows"] < df.loc["Actual_Operator_History", "stockout_rows"]
    # 3. Estimated counterfactual waste reduction > 15%
    assert df.loc["AI_Reorder_SL_90", "counterfactual_waste_reduction_pct"] > 15.0


def test_reorder_simulation_figures_exist() -> None:
    """Verify generated plot artifact exists."""
    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    fig_path = reports_dir / "figures" / "reorder_simulation_comparison.png"
    assert fig_path.exists()
    assert fig_path.stat().st_size > 1000
