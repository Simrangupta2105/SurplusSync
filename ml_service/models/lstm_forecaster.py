"""PyTorch LSTM Sequence Forecaster for Demand Forecasting (Track B).

Implements Task 4 requirements:
1. PyTorch LSTM CPU sequence model:
   - Configurable lookback window (default 28 days)
   - Configurable hidden dimension and layers
   - Standardized input scaling learned strictly on training history
   - Non-negative output projection
   - Calibrated 90% uncertainty intervals via empirical training residual quantiles
2. Multi-seed Evaluation:
   - Evaluated across 5 fixed random seeds (42, 123, 456, 789, 999)
   - Reports mean and std across seeds for WAPE, MAE, RMSE, Bias, and 90% Coverage
3. Ablation Study:
   - Lookback window variation (14 vs 28 vs 56 days)
   - Hidden dimension capacity (8 vs 16 vs 32 units)
   - Exogenous regressors (Univariate demand vs Multivariate with covariates)
4. Strict Invariant & Leakage Enforcement:
   - Rejects Units_Sold as demand target
   - Rejects any leakage outcome/accounting columns
   - Operates strictly on pre-cutoff data (Date < 2025-10-03)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.base import BaseEstimator, RegressorMixin

try:
    from ml_service.data.synthetic_panel import validate_demand_target
    from ml_service.data.time_series_splits import (
        RollingOriginSplitter,
        build_category_aggregate_series,
        split_train_test,
        verify_no_leakage,
    )
    from ml_service.models.metrics import evaluate_forecast
except ModuleNotFoundError:
    from data.synthetic_panel import validate_demand_target
    from data.time_series_splits import (
        RollingOriginSplitter,
        build_category_aggregate_series,
        split_train_test,
        verify_no_leakage,
    )
    from models.metrics import evaluate_forecast


FIXED_SEEDS: List[int] = [42, 123, 456, 789, 999]

DEFAULT_LSTM_COVARIATES: List[str] = [
    "Temperature_C",
    "Rain_mm",
    "Is_Weekend",
    "Is_Holiday",
]


class _LSTMNetwork(nn.Module):
    """Internal PyTorch recurrent neural network module."""

    def __init__(self, input_dim: int, hidden_size: int, num_layers: int = 1):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (batch_size, seq_len, input_dim)
        out, _ = self.lstm(x)
        # Output from last timestep: (batch_size, 1)
        last_timestep = out[:, -1, :]
        pred = self.fc(last_timestep)
        return pred


class PyTorchLSTMForecaster(BaseEstimator, RegressorMixin):
    """CPU-based PyTorch LSTM sequence forecaster with interval calibration."""

    def __init__(
        self,
        lookback: int = 28,
        hidden_size: int = 16,
        num_layers: int = 1,
        epochs: int = 30,
        learning_rate: float = 0.01,
        batch_size: int = 64,
        random_seed: int = 42,
        use_covariates: bool = False,
        covariate_cols: Optional[List[str]] = None,
    ) -> None:
        self.lookback = lookback
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.random_seed = random_seed
        self.use_covariates = use_covariates
        self.covariate_cols = covariate_cols if covariate_cols is not None else DEFAULT_LSTM_COVARIATES

        self.net_: Optional[_LSTMNetwork] = None
        self.target_mean_: float = 0.0
        self.target_std_: float = 1.0
        self.cov_means_: Dict[str, float] = {}
        self.cov_stds_: Dict[str, float] = {}
        self.active_covariates_: List[str] = []
        self.last_lookback_history_: Optional[np.ndarray] = None
        self.residual_quantiles_: Dict[float, Tuple[float, float]] = {}
        self.is_fitted_: bool = False

    def fit(
        self,
        df_train: Union[pd.DataFrame, pd.Series, np.ndarray],
        target_col: str = "Daily_Demand",
    ) -> "PyTorchLSTMForecaster":
        """Train the LSTM model on CPU using strictly historical data."""
        # Set seeds for deterministic training
        torch.manual_seed(self.random_seed)
        np.random.seed(self.random_seed)

        # Extract target and covariates
        if isinstance(df_train, pd.DataFrame):
            validate_demand_target(target_col)
            if target_col not in df_train.columns:
                raise ValueError(f"Target column '{target_col}' not found in training DataFrame.")
            y_raw = df_train[target_col].astype(float).values

            if self.use_covariates:
                verify_no_leakage([c for c in df_train.columns if c != target_col])
                self.active_covariates_ = [c for c in self.covariate_cols if c in df_train.columns]
                cov_arrays = []
                for c in self.active_covariates_:
                    vals = df_train[c].astype(float).fillna(0.0).values
                    m_c = float(np.mean(vals))
                    s_c = float(np.std(vals)) if np.std(vals) > 1e-6 else 1.0
                    self.cov_means_[c] = m_c
                    self.cov_stds_[c] = s_c
                    cov_arrays.append((vals - m_c) / s_c)
                cov_matrix = np.column_stack(cov_arrays) if cov_arrays else None
            else:
                self.active_covariates_ = []
                cov_matrix = None
        elif isinstance(df_train, pd.Series):
            y_raw = df_train.astype(float).values
            cov_matrix = None
            self.active_covariates_ = []
        else:
            y_raw = np.asarray(df_train, dtype=float)
            cov_matrix = None
            self.active_covariates_ = []

        n_samples = len(y_raw)
        if n_samples <= self.lookback:
            raise ValueError(
                f"Training sequence length ({n_samples}) must be greater than lookback window ({self.lookback})."
            )

        # Standardize target
        self.target_mean_ = float(np.mean(y_raw))
        self.target_std_ = float(np.std(y_raw)) if np.std(y_raw) > 1e-6 else 1.0
        y_scaled = (y_raw - self.target_mean_) / self.target_std_

        # Prepare sliding window sequences
        X_seqs = []
        y_targets = []
        input_dim = 1 + (len(self.active_covariates_) if cov_matrix is not None else 0)

        for i in range(n_samples - self.lookback):
            target_slice = y_scaled[i : i + self.lookback]
            if cov_matrix is not None:
                cov_slice = cov_matrix[i : i + self.lookback]
                seq_features = np.column_stack([target_slice, cov_slice])
            else:
                seq_features = target_slice[:, np.newaxis]

            X_seqs.append(seq_features)
            y_targets.append(y_scaled[i + self.lookback])

        X_tensor = torch.tensor(np.array(X_seqs), dtype=torch.float32)
        y_tensor = torch.tensor(np.array(y_targets), dtype=torch.float32).unsqueeze(-1)

        # Initialize network
        self.net_ = _LSTMNetwork(
            input_dim=input_dim,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
        )
        optimizer = torch.optim.Adam(self.net_.parameters(), lr=self.learning_rate)
        criterion = nn.SmoothL1Loss()

        # Training loop
        self.net_.train()
        n_batches = int(math.ceil(len(X_tensor) / self.batch_size))

        for _ in range(self.epochs):
            permutation = torch.randperm(len(X_tensor))
            for b in range(n_batches):
                indices = permutation[b * self.batch_size : (b + 1) * self.batch_size]
                batch_x = X_tensor[indices]
                batch_y = y_tensor[indices]

                optimizer.zero_grad()
                preds = self.net_(batch_x)
                loss = criterion(preds, batch_y)
                loss.backward()
                optimizer.step()

        # Store last lookback history for autoregressive rollout
        last_target_slice = y_scaled[-self.lookback:]
        if cov_matrix is not None:
            last_cov_slice = cov_matrix[-self.lookback:]
            self.last_lookback_history_ = np.column_stack([last_target_slice, last_cov_slice])
        else:
            self.last_lookback_history_ = last_target_slice[:, np.newaxis]

        # Calibrate 90% prediction intervals on training residuals
        self.net_.eval()
        with torch.no_grad():
            fitted_scaled = self.net_(X_tensor).numpy().flatten()
            fitted_actual = np.maximum(0.0, fitted_scaled * self.target_std_ + self.target_mean_)
            actual_y = y_raw[self.lookback:]
            residuals = actual_y - fitted_actual

            for cov in (0.90,):
                alpha = 1.0 - cov
                q_low = float(np.quantile(residuals, alpha / 2.0))
                q_high = float(np.quantile(residuals, 1.0 - (alpha / 2.0)))
                self.residual_quantiles_[cov] = (q_low, q_high)

        self.is_fitted_ = True
        return self

    def predict(
        self,
        horizon: int,
        future_covariates_df: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        """Autoregressively roll out forecasts for `horizon` steps ahead."""
        if not self.is_fitted_ or self.net_ is None or self.last_lookback_history_ is None:
            raise RuntimeError("Model must be fitted before calling predict().")

        # Process future covariates if model was trained with them
        if self.use_covariates and self.active_covariates_:
            if future_covariates_df is None:
                raise ValueError("Model was trained with covariates; future_covariates_df is required.")
            verify_no_leakage(future_covariates_df.columns)
            future_cov_arrays = []
            for c in self.active_covariates_:
                vals = future_covariates_df[c].astype(float).fillna(0.0).values
                m_c = self.cov_means_.get(c, 0.0)
                s_c = self.cov_stds_.get(c, 1.0)
                future_cov_arrays.append((vals - m_c) / s_c)
            future_cov_matrix = np.column_stack(future_cov_arrays)
        else:
            future_cov_matrix = None

        curr_window = self.last_lookback_history_.copy()  # shape: (lookback, input_dim)
        preds_scaled: List[float] = []

        self.net_.eval()
        with torch.no_grad():
            for h in range(horizon):
                inp = torch.tensor(curr_window[-self.lookback:], dtype=torch.float32).unsqueeze(0)
                next_pred_scaled = float(self.net_(inp).item())
                preds_scaled.append(next_pred_scaled)

                # Append predicted target and known next-step covariates
                if future_cov_matrix is not None and h < len(future_cov_matrix):
                    next_row = np.concatenate([[next_pred_scaled], future_cov_matrix[h]])
                else:
                    next_row = np.array([next_pred_scaled])

                curr_window = np.vstack([curr_window, next_row])

        preds = np.array(preds_scaled) * self.target_std_ + self.target_mean_
        return np.maximum(0.0, preds)

    def predict_interval(
        self,
        horizon: int,
        future_covariates_df: Optional[pd.DataFrame] = None,
        coverage: float = 0.90,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return point forecasts and 90% uncertainty intervals."""
        yhat = self.predict(horizon=horizon, future_covariates_df=future_covariates_df)
        q_low, q_high = self.residual_quantiles_.get(coverage, (-10.0, 10.0))
        yhat_lower = np.maximum(0.0, yhat + q_low)
        yhat_upper = np.maximum(yhat, yhat + q_high)
        return yhat, yhat_lower, yhat_upper


# --- 2. Multi-Seed Evaluation Runner ---

def evaluate_lstm_multi_seed(
    category_series: Dict[str, pd.DataFrame],
    seeds: Sequence[int] = FIXED_SEEDS,
    horizon: int = 7,
    n_splits: int = 4,
    step: int = 28,
) -> pd.DataFrame:
    """Evaluate PyTorch LSTM across 5 fixed random seeds on pre-cutoff rolling folds."""
    records: List[Dict[str, Any]] = []

    for seed in seeds:
        for cat_name, s_df in category_series.items():
            splitter = RollingOriginSplitter(n_splits=n_splits, horizon=horizon, step=step)

            for train_df, val_df, fold in splitter.split_series(s_df):
                model = PyTorchLSTMForecaster(
                    lookback=28,
                    hidden_size=16,
                    epochs=30,
                    random_seed=seed,
                    use_covariates=False,
                )
                model.fit(train_df)
                y_pred, y_low, y_high = model.predict_interval(horizon=horizon)

                y_true = val_df["Daily_Demand"].values
                metrics = evaluate_forecast(y_true, y_pred, y_low, y_high)

                records.append({
                    "model": "PyTorch_LSTM",
                    "seed": seed,
                    "category": cat_name,
                    "fold_idx": fold.fold_idx,
                    "horizon": horizon,
                    **metrics,
                })

    return pd.DataFrame(records)


# --- 3. Ablation Study Runner ---

def run_lstm_ablation_study(
    category_series: Dict[str, pd.DataFrame],
    horizon: int = 7,
    n_splits: int = 2,
    step: int = 28,
) -> pd.DataFrame:
    """Execute ablation study comparing lookbacks, hidden sizes, and exogenous covariates."""
    ablation_configs = [
        # Baseline
        {"config": "Baseline (Lookback=28, Hidden=16, Univariate)", "lookback": 28, "hidden_size": 16, "use_covariates": False},
        # Lookback variations
        {"config": "Lookback=14 (Short Memory)", "lookback": 14, "hidden_size": 16, "use_covariates": False},
        {"config": "Lookback=56 (Long Memory)", "lookback": 56, "hidden_size": 16, "use_covariates": False},
        # Hidden dimension variations
        {"config": "Hidden=8 (Low Capacity)", "lookback": 28, "hidden_size": 8, "use_covariates": False},
        {"config": "Hidden=32 (High Capacity)", "lookback": 28, "hidden_size": 32, "use_covariates": False},
        # Covariate variation
        {"config": "Multivariate (With Covariates)", "lookback": 28, "hidden_size": 16, "use_covariates": True},
    ]

    records: List[Dict[str, Any]] = []

    for cfg in ablation_configs:
        config_name = cfg["config"]
        lookback = cfg["lookback"]
        hidden_size = cfg["hidden_size"]
        use_covariates = cfg["use_covariates"]

        for cat_name, s_df in category_series.items():
            splitter = RollingOriginSplitter(n_splits=n_splits, horizon=horizon, step=step)

            for train_df, val_df, fold in splitter.split_series(s_df):
                model = PyTorchLSTMForecaster(
                    lookback=lookback,
                    hidden_size=hidden_size,
                    epochs=25,
                    random_seed=42,
                    use_covariates=use_covariates,
                )
                model.fit(train_df)
                y_pred, y_low, y_high = model.predict_interval(
                    horizon=horizon,
                    future_covariates_df=val_df if use_covariates else None,
                )

                y_true = val_df["Daily_Demand"].values
                metrics = evaluate_forecast(y_true, y_pred, y_low, y_high)

                records.append({
                    "ablation_config": config_name,
                    "category": cat_name,
                    "fold_idx": fold.fold_idx,
                    "horizon": horizon,
                    **metrics,
                })

    df_raw = pd.DataFrame(records)
    summary = df_raw.groupby(["ablation_config", "horizon"])[
        ["wape", "mae", "rmse", "bias", "coverage"]
    ].mean().reset_index()
    summary = summary.sort_values("wape").reset_index(drop=True)
    return summary
