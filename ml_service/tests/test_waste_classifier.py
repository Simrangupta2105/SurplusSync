"""Unit and integration tests for Task 4 Waste-Level Classifier.

Verifies:
1. Strict data leakage prevention (raises DataLeakageError if forbidden columns are passed).
2. Target distribution and domain constraints.
3. Feature preparation and safe ratio calculations.
4. Majority and heuristic baseline classifier behaviors.
5. Trained classifiers strictly outperform majority baseline on Macro-F1.
6. High-waste class recall exceeds minimum operational threshold (> 60%).
7. Saved model inference smoke test and probability calibration validity.
8. Label noise documentation presence in metadata.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import joblib
import numpy as np
import pandas as pd
import pytest

from ml_service.data.food_waste import DEFAULT_DATASET_PATH, load_raw_data
from ml_service.models.waste_classifier import (
    ALL_ALLOWED_FEATURES,
    CLASS_LABELS,
    FORBIDDEN_FEATURES,
    DataLeakageError,
    HeuristicWasteClassifier,
    MajorityWasteClassifier,
    prepare_classifier_features,
    validate_feature_columns,
)


def test_data_leakage_enforcement_raises_loud_error() -> None:
    """CRITICAL INVARIANT: Fails loudly if ANY forbidden outcome column is in feature matrix."""
    for forbidden_col in FORBIDDEN_FEATURES:
        with pytest.raises(DataLeakageError, match="DATA LEAKAGE DETECTED"):
            validate_feature_columns(["Food_Category", forbidden_col, "Purchase_Quantity"])

    # Test multi-column leak
    with pytest.raises(DataLeakageError):
        validate_feature_columns(list(FORBIDDEN_FEATURES))


def test_allowed_feature_columns_pass_validation() -> None:
    """Verify that none of the allowed operational features trigger leakage validation."""
    # Should not raise
    validate_feature_columns(ALL_ALLOWED_FEATURES)
    for feat in ALL_ALLOWED_FEATURES:
        assert feat not in FORBIDDEN_FEATURES


def test_target_classes_domain() -> None:
    """Verify target classes are exactly Low, Medium, High."""
    assert set(CLASS_LABELS) == {"Low", "Medium", "High"}
    df = load_raw_data(DEFAULT_DATASET_PATH)
    unique_levels = set(df["Waste_Level"].unique())
    assert unique_levels == {"Low", "Medium", "High"}


def test_prepare_classifier_features_structure_and_ratios() -> None:
    """Verify feature extractor computes over_order_ratio and day_of_week correctly."""
    sample_df = pd.DataFrame({
        "Date": ["2025-06-15", "2025-06-16"],  # Sunday (6), Monday (0)
        "Food_Category": ["Bakery", "Dairy"],
        "Business_Type": ["Supermarket", "Restaurant"],
        "Promotion": ["No", "Yes"],
        "Weather": ["Sunny", "Rainy"],
        "Purchase_Quantity": [100.0, 150.0],
        "Shelf_Life_Days": [3.0, 7.0],
        "Storage_Temperature": [20.0, 4.0],
    })
    mock_forecast = np.array([80.0, 100.0])

    features = prepare_classifier_features(sample_df, forecast_demand_array=mock_forecast)

    assert list(features.columns) == ALL_ALLOWED_FEATURES
    assert features["day_of_week"].tolist() == [6, 0]
    # over_order_ratio = Purchase / Forecast
    expected_ratios = [100.0 / 80.0, 150.0 / 100.0]  # [1.25, 1.5]
    np.testing.assert_allclose(features["over_order_ratio"].values, expected_ratios)


def test_majority_baseline_predictions() -> None:
    """Verify majority baseline always predicts 'Low'."""
    clf = MajorityWasteClassifier()
    y_train = np.array(["Low", "Low", "Medium", "High", "Low"])
    X_mock = pd.DataFrame({"dummy": [1, 2, 3, 4, 5]})
    clf.fit(X_mock, y_train)

    assert clf.majority_class_ == "Low"
    preds = clf.predict(X_mock)
    assert (preds == "Low").all()

    probs = clf.predict_proba(X_mock)
    assert probs.shape == (5, 3)
    np.testing.assert_allclose(probs[:, list(clf.classes_).index("Low")], 1.0)


def test_heuristic_ratio_rule_logic() -> None:
    """Verify heuristic rule thresholds partition correctly."""
    clf = HeuristicWasteClassifier(threshold_medium=1.1, threshold_high=1.5)
    X = pd.DataFrame({"over_order_ratio": [0.8, 1.05, 1.15, 1.45, 1.55, 2.0]})
    preds = clf.predict(X)

    expected = ["Low", "Low", "Medium", "Medium", "High", "High"]
    assert list(preds) == expected


def test_trained_models_strictly_beat_majority_baseline() -> None:
    """Verify trained classifiers outperform majority baseline by > 0.35 in test Macro-F1."""
    metrics_path = Path(__file__).resolve().parent.parent / "reports" / "waste_classifier_metrics.csv"
    assert metrics_path.exists(), f"Missing metrics file: {metrics_path}"

    df = pd.read_csv(metrics_path).set_index("model")
    majority_macro_f1 = df.loc["Majority_Baseline", "test_macro_f1"]
    assert majority_macro_f1 < 0.25

    for model_name in ["LightGBM", "Logistic_Regression", "Hist_Gradient_Boosting"]:
        assert model_name in df.index
        macro_f1 = df.loc[model_name, "test_macro_f1"]
        assert macro_f1 > 0.65, f"{model_name} Macro-F1 was {macro_f1}, expected > 0.65"
        assert macro_f1 - majority_macro_f1 > 0.35


def test_high_waste_recall_meets_operational_target() -> None:
    """Verify best classifier achieves >= 65% recall on High waste class."""
    metadata_path = Path(__file__).resolve().parent.parent / "models" / "saved" / "best_waste_classifier_metadata.json"
    assert metadata_path.exists(), f"Missing metadata: {metadata_path}"

    with open(metadata_path, "r") as f:
        meta = json.load(f)

    high_recall = meta["test_metrics"]["per_class"]["High"]["recall"]
    assert high_recall >= 0.65, f"High waste recall was {high_recall:.3f}, expected >= 0.65"


def test_saved_model_inference_smoke_test() -> None:
    """Smoke test: verify saved model loads and predicts on new sample."""
    saved_dir = Path(__file__).resolve().parent.parent / "models" / "saved"
    model_file = saved_dir / "best_waste_classifier.joblib"
    assert model_file.exists(), f"Missing model file: {model_file}"

    model = joblib.load(model_file)

    sample_input = pd.DataFrame([{
        "Food_Category": "Prepared Food",
        "Business_Type": "Restaurant",
        "Promotion": "Yes",
        "Weather": "Hot",
        "Purchase_Quantity": 200.0,
        "forecast_demand": 120.0,
        "over_order_ratio": 200.0 / 120.0,  # 1.667 (High risk)
        "Shelf_Life_Days": 2.0,
        "Storage_Temperature": 4.0,
        "day_of_week": 4,
    }])

    pred = model.predict(sample_input)
    assert pred[0] in CLASS_LABELS

    probs = model.predict_proba(sample_input)[0]
    assert len(probs) == 3
    assert np.isclose(np.sum(probs), 1.0)
    assert probs[list(model.classes_).index("High")] > 0.40  # Should flag substantial high risk


def test_label_noise_documentation_present() -> None:
    """Verify label noise operational note is documented in metadata."""
    metadata_path = Path(__file__).resolve().parent.parent / "models" / "saved" / "best_waste_classifier_metadata.json"
    with open(metadata_path, "r") as f:
        meta = json.load(f)

    assert "label_noise_note" in meta
    assert "positive waste" in meta["label_noise_note"]
    assert "zero-waste" in meta["label_noise_note"]
