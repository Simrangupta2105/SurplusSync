"""Evaluation metrics for demand forecasting and tabular models.

Implements standard forecasting error metrics:
- WAPE (Weighted Absolute Percentage Error) = sum(|y - yhat|) / sum(y)
- MAE (Mean Absolute Error) = mean(|y - yhat|)
- RMSE (Root Mean Squared Error) = sqrt(mean((y - yhat)^2))
- Bias (Mean Error) = mean(yhat - y) [positive indicates over-forecasting]
- Prediction Interval Coverage = mean(y_lower <= y <= y_upper)
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Sequence, Union

import numpy as np


def compute_wape(
    y_true: Union[np.ndarray, Sequence[float]],
    y_pred: Union[np.ndarray, Sequence[float]],
) -> float:
    """Compute Weighted Absolute Percentage Error (WAPE).

    Formula: sum(|y - yhat|) / sum(y)
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    denom = np.sum(y_t)
    if denom == 0:
        return 0.0 if np.all(y_t == y_p) else float("inf")
    return float(np.sum(np.abs(y_t - y_p)) / denom)


def compute_mae(
    y_true: Union[np.ndarray, Sequence[float]],
    y_pred: Union[np.ndarray, Sequence[float]],
) -> float:
    """Compute Mean Absolute Error (MAE)."""
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    if len(y_t) == 0:
        return 0.0
    return float(np.mean(np.abs(y_t - y_p)))


def compute_rmse(
    y_true: Union[np.ndarray, Sequence[float]],
    y_pred: Union[np.ndarray, Sequence[float]],
) -> float:
    """Compute Root Mean Squared Error (RMSE)."""
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    if len(y_t) == 0:
        return 0.0
    return float(math.sqrt(np.mean((y_t - y_p) ** 2)))


def compute_bias(
    y_true: Union[np.ndarray, Sequence[float]],
    y_pred: Union[np.ndarray, Sequence[float]],
) -> float:
    """Compute Forecasting Bias (Mean Error: y_pred - y_true).

    Positive indicates systematic over-forecasting;
    Negative indicates systematic under-forecasting.
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    if len(y_t) == 0:
        return 0.0
    return float(np.mean(y_p - y_t))


def compute_coverage(
    y_true: Union[np.ndarray, Sequence[float]],
    y_lower: Union[np.ndarray, Sequence[float]],
    y_upper: Union[np.ndarray, Sequence[float]],
) -> float:
    """Compute empirical coverage of prediction interval: fraction of y_true in [y_lower, y_upper]."""
    y_t = np.asarray(y_true, dtype=float)
    y_l = np.asarray(y_lower, dtype=float)
    y_u = np.asarray(y_upper, dtype=float)
    if len(y_t) == 0:
        return 0.0
    in_interval = (y_t >= y_l) & (y_t <= y_u)
    return float(np.mean(in_interval))


def evaluate_forecast(
    y_true: Union[np.ndarray, Sequence[float]],
    y_pred: Union[np.ndarray, Sequence[float]],
    y_lower: Optional[Union[np.ndarray, Sequence[float]]] = None,
    y_upper: Optional[Union[np.ndarray, Sequence[float]]] = None,
) -> Dict[str, float]:
    """Compute all standard evaluation metrics for predictions."""
    res: Dict[str, float] = {
        "wape": compute_wape(y_true, y_pred),
        "mae": compute_mae(y_true, y_pred),
        "rmse": compute_rmse(y_true, y_pred),
        "bias": compute_bias(y_true, y_pred),
    }
    if y_lower is not None and y_upper is not None:
        res["coverage"] = compute_coverage(y_true, y_lower, y_upper)
    return res
