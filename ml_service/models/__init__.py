"""Forecasting and prediction models package for ml_service."""

try:
    from ml_service.models.metrics import (
        compute_bias,
        compute_coverage,
        compute_mae,
        compute_rmse,
        compute_wape,
        evaluate_forecast,
    )
    from ml_service.models.registry import ModelRegistry
except ModuleNotFoundError:
    from models.metrics import (
        compute_bias,
        compute_coverage,
        compute_mae,
        compute_rmse,
        compute_wape,
        evaluate_forecast,
    )
    from models.registry import ModelRegistry

__all__ = [
    "compute_wape",
    "compute_mae",
    "compute_rmse",
    "compute_bias",
    "compute_coverage",
    "evaluate_forecast",
    "ModelRegistry",
]
