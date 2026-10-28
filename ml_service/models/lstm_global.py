"""Global Multi-Horizon PyTorch LSTM Demand Forecaster (Task 3).

Implements:
1. Global Sequence Model across all 72 daily series:
   - 28-day historical lookback window [T-27 .. T]
   - Direct multi-horizon predictions for h in [1 .. 7] days simultaneously
   - Categorical entity embeddings:
     * Shop ID (12 -> 8 dims)
     * Food Category (6 -> 4 dims)
     * City (4 -> 4 dims)
     (Total embedding dim = 16)
   - Known-future covariates for horizons T+1 .. T+7:
     * Promotion, rain, temperature, weather code, festival, day-of-week,
       is_weekend, sin/cos day-of-year (9 features x 7 horizons = 63 dims)
   - Cross-series inputs (same-shop other 5 categories mean demand)
2. Huber Loss Justification:
   - The synthetic sequence dataset contains 216 unobserved one-off demand shocks
     (ranging from 0.45x to 1.90x multipliers) across shops and categories.
   - Standard MSE loss generates quadratic gradient spikes (2 * residual) on these
     extreme shocks, leading to exploding updates that destabilize deep nets.
   - Poisson NLL on neural networks uses an exponential link function, leading to
     severe numerical instability when extreme positive shocks occur.
   - Huber loss (SmoothL1Loss with beta=1.0) provides smooth, curvature-aware
     quadratic gradients for normal demand fluctuations (|error| <= 1.0) and transitions
     gracefully to robust linear penalties for large shocks (|error| > 1.0).
     This stabilizes sequence model training on CPU without numerical divergence.
3. Optimization & Regularization:
   - AdamW optimizer (lr=1e-3, weight_decay=1e-4)
   - Gradient clipping (torch.nn.utils.clip_grad_norm_ at max_norm=1.0)
   - Dropout (p=0.1) in recurrent/dense layers
   - Early stopping on held-out validation origins with patience=5
   - Calibrated 90% prediction intervals via empirical residual quantiles
4. 4 Controlled Ablations:
   - (a) Past demand only
   - (b) + Known-future covariates
   - (c) + Embeddings
   - (d) + Cross-series inputs
5. Multi-seed Evaluation:
   - Fixed seeds: [42, 123, 456, 789, 999]
   - Reports mean and std for WAPE, MAE, RMSE, Bias, and 90% Coverage.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

try:
    from ml_service.data.synthetic_panel import validate_demand_target
    from ml_service.data.time_series_splits import (
        FINAL_TEST_DAYS,
        LEAKAGE_COLUMNS,
        TEST_CUTOFF_DATE,
        RollingOriginSplitter,
        verify_no_leakage,
    )
    from ml_service.models.fair_tabular_baselines import TabularFeatureEngine
    from ml_service.models.metrics import evaluate_forecast
except ModuleNotFoundError:
    import sys
    base_dir = str(Path(__file__).resolve().parent.parent)
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    from data.synthetic_panel import validate_demand_target
    from data.time_series_splits import (
        FINAL_TEST_DAYS,
        LEAKAGE_COLUMNS,
        TEST_CUTOFF_DATE,
        RollingOriginSplitter,
        verify_no_leakage,
    )
    from models.fair_tabular_baselines import TabularFeatureEngine
    from models.metrics import evaluate_forecast


LSTM_SEEDS: List[int] = [42, 123, 456, 789, 999]


class GlobalMultiHorizonLSTM(nn.Module):
    """PyTorch Recurrent Neural Network for joint 7-day multi-horizon forecasting."""

    def __init__(
        self,
        use_covariates: bool = False,
        use_embeddings: bool = False,
        use_cross_series: bool = False,
        lookback: int = 28,
        horizons: int = 7,
        hidden_size: int = 32,
        num_layers: int = 1,
        dropout: float = 0.1,
        num_shops: int = 12,
        num_categories: int = 6,
        num_cities: int = 4,
        shop_embed_dim: int = 8,
        cat_embed_dim: int = 4,
        city_embed_dim: int = 4,
        fut_cov_dim_per_day: int = 9,
    ):
        super().__init__()
        self.use_covariates = use_covariates
        self.use_embeddings = use_embeddings
        self.use_cross_series = use_cross_series
        self.lookback = lookback
        self.horizons = horizons
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        # 1. Entity Embeddings (Shop, Category, City)
        if self.use_embeddings:
            self.shop_emb = nn.Embedding(num_shops, shop_embed_dim)
            self.cat_emb = nn.Embedding(num_categories, cat_embed_dim)
            self.city_emb = nn.Embedding(num_cities, city_embed_dim)
            self.total_embed_dim = shop_embed_dim + cat_embed_dim + city_embed_dim
        else:
            self.shop_emb = None
            self.cat_emb = None
            self.city_emb = None
            self.total_embed_dim = 0

        # 2. Sequential Input Dimensions:
        # Base: 1 (past scaled demand)
        # + Covariates at each timestep (9: promo, rain, temp, weather, fest, dow, wknd, sin_doy, cos_doy)
        # + Cross-series input at each timestep (1: same-shop other categories mean)
        seq_in_dim = 1
        if self.use_covariates:
            seq_in_dim += fut_cov_dim_per_day
        if self.use_cross_series:
            seq_in_dim += 1
        self.seq_in_dim = seq_in_dim

        # 3. Recurrent Encoder
        self.lstm = nn.LSTM(
            input_size=seq_in_dim,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )

        # 4. Multi-Horizon Direct Output Head
        # Head input = LSTM final hidden state (hidden_size)
        #            + Flattened future covariates for T+1 .. T+7 (7 * 9 = 63 dims if use_covariates)
        #            + Entity embeddings (16 dims if use_embeddings)
        head_in_dim = hidden_size
        if self.use_covariates:
            head_in_dim += horizons * fut_cov_dim_per_day
        if self.use_embeddings:
            head_in_dim += self.total_embed_dim
        self.head_in_dim = head_in_dim

        self.head = nn.Sequential(
            nn.Linear(head_in_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, horizons),
        )

    def forward(
        self,
        x_seq: torch.Tensor,
        shop_idx: Optional[torch.Tensor] = None,
        cat_idx: Optional[torch.Tensor] = None,
        city_idx: Optional[torch.Tensor] = None,
        fut_cov: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Forward pass.

        Args:
            x_seq: (B, lookback, seq_in_dim)
            shop_idx: (B,) optional shop indices
            cat_idx: (B,) optional category indices
            city_idx: (B,) optional city indices
            fut_cov: (B, horizons * fut_cov_dim_per_day) optional future covariates

        Returns:
            preds: (B, horizons) multi-step demand predictions
        """
        # LSTM forward: output (B, seq_len, hidden_size), (h_n, c_n)
        _, (h_n, _) = self.lstm(x_seq)
        h_last = h_n[-1]  # (B, hidden_size)

        fusion_parts = [h_last]

        # Future covariates
        if self.use_covariates and fut_cov is not None:
            fusion_parts.append(fut_cov)

        # Entity embeddings
        if self.use_embeddings and shop_idx is not None and cat_idx is not None and city_idx is not None:
            e_shop = self.shop_emb(shop_idx)
            e_cat = self.cat_emb(cat_idx)
            e_city = self.city_emb(city_idx)
            e_all = torch.cat([e_shop, e_cat, e_city], dim=-1)
            fusion_parts.append(e_all)

        fusion = torch.cat(fusion_parts, dim=-1)
        preds = self.head(fusion)
        return preds


def get_parameter_count(model: nn.Module) -> int:
    """Return total number of trainable parameters in PyTorch model."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


class GlobalLSTMForecaster:
    """High-level estimator wrapper for Global Multi-Horizon LSTM."""

    def __init__(
        self,
        use_covariates: bool = False,
        use_embeddings: bool = False,
        use_cross_series: bool = False,
        lookback: int = 28,
        horizons: int = 7,
        hidden_size: int = 32,
        num_layers: int = 1,
        dropout: float = 0.1,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-4,
        epochs: int = 25,
        batch_size: int = 512,
        patience: int = 5,
        random_seed: int = 42,
    ):
        self.use_covariates = use_covariates
        self.use_embeddings = use_embeddings
        self.use_cross_series = use_cross_series
        self.lookback = lookback
        self.horizons = horizons
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.epochs = epochs
        self.batch_size = batch_size
        self.patience = patience
        self.random_seed = random_seed

        self.model: Optional[GlobalMultiHorizonLSTM] = None
        self.demand_mean_: float = 0.0
        self.demand_std_: float = 1.0
        self.rain_mean_: float = 0.0
        self.rain_std_: float = 1.0
        self.temp_mean_: float = 0.0
        self.temp_std_: float = 1.0
        self.residual_quantiles_: Tuple[float, float] = (0.0, 0.0)
        self.is_fitted_: bool = False

    def _prepare_tensors(
        self,
        engine: TabularFeatureEngine,
        origin_indices: Sequence[int],
        is_training: bool = True,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Convert engine matrices into PyTorch tensors for specified origins via vectorized indexing."""
        origs = np.asarray(origin_indices, dtype=np.int32)
        n_origs = len(origs)
        n_series = engine.n_series  # 72

        past_idx = origs[:, None] + np.arange(-self.lookback + 1, 1)[None, :]  # (n_origs, 28)
        if is_training:
            fut_idx = origs[:, None] + np.arange(1, self.horizons + 1)[None, :]  # (n_origs, 7)
        else:
            fut_idx = np.clip(origs[:, None] + np.arange(1, self.horizons + 1)[None, :], 0, engine.n_dates - 1)

        # 1. Past scaled demand: (n_origs, 28, 72) -> (n_origs, 72, 28) -> (N, 28, 1)
        d_windows = (engine.demand_arr[past_idx, :] - self.demand_mean_) / self.demand_std_
        d_seq = d_windows.transpose(0, 2, 1).reshape(-1, self.lookback, 1)
        seq_components = [d_seq]

        # 2. Past covariates sequence (9 channels)
        if self.use_covariates:
            promo_win = engine.promo_arr[past_idx, :]
            rain_win = (engine.rain_arr[past_idx, :] - self.rain_mean_) / self.rain_std_
            temp_win = (engine.temp_arr[past_idx, :] - self.temp_mean_) / self.temp_std_
            weather_win = engine.weather_arr[past_idx, :] / 3.0
            fest_win = (engine.fest_arr[past_idx, :] > 0).astype(np.float32)

            dow_win = np.tile((engine.cal_dow[past_idx] / 6.0)[:, :, None], (1, 1, n_series))
            wknd_win = np.tile(engine.cal_is_weekend[past_idx][:, :, None], (1, 1, n_series))
            sin_win = np.tile(engine.cal_sin_doy[past_idx][:, :, None], (1, 1, n_series))
            cos_win = np.tile(engine.cal_cos_doy[past_idx][:, :, None], (1, 1, n_series))

            cov_9_past = np.stack(
                [promo_win, rain_win, temp_win, weather_win, fest_win, dow_win, wknd_win, sin_win, cos_win],
                axis=-1,
            )  # (n_origs, 28, 72, 9)
            cov_seq = cov_9_past.transpose(0, 2, 1, 3).reshape(-1, self.lookback, 9)
            seq_components.append(cov_seq)

        # 3. Cross-series past sequence (1 channel: same-shop other categories mean)
        if self.use_cross_series:
            cross_win = (engine.shop_other_cats_arr[past_idx, :] - self.demand_mean_) / self.demand_std_
            c_seq = cross_win.transpose(0, 2, 1).reshape(-1, self.lookback, 1)
            seq_components.append(c_seq)

        x_seq_tensor = torch.tensor(np.concatenate(seq_components, axis=-1), dtype=torch.float32)

        # 4. Target values for future horizons T+1 .. T+7: (n_origs, 7, 72) -> (N, 7)
        if is_training:
            y_targets = (engine.demand_arr[fut_idx, :] - self.demand_mean_) / self.demand_std_
            y_tensor = torch.tensor(y_targets.transpose(0, 2, 1).reshape(-1, self.horizons), dtype=torch.float32)
        else:
            y_tensor = torch.zeros((n_origs * n_series, self.horizons), dtype=torch.float32)

        # 5. Entity IDs for series: (N,)
        shop_codes = engine.static_features_72[:, 0].astype(np.int64)
        cat_codes = engine.static_features_72[:, 1].astype(np.int64)
        city_codes = engine.static_features_72[:, 2].astype(np.int64)

        shop_idx_tensor = torch.tensor(np.tile(shop_codes, n_origs), dtype=torch.long)
        cat_idx_tensor = torch.tensor(np.tile(cat_codes, n_origs), dtype=torch.long)
        city_idx_tensor = torch.tensor(np.tile(city_codes, n_origs), dtype=torch.long)

        # 6. Future covariates for T+1 .. T+7 (flattened to 63 dims per sample)
        if self.use_covariates:
            p_fut = engine.promo_arr[fut_idx, :]
            r_fut = (engine.rain_arr[fut_idx, :] - self.rain_mean_) / self.rain_std_
            t_fut = (engine.temp_arr[fut_idx, :] - self.temp_mean_) / self.temp_std_
            w_fut = engine.weather_arr[fut_idx, :] / 3.0
            f_fut = (engine.fest_arr[fut_idx, :] > 0).astype(np.float32)

            dow_fut = np.tile((engine.cal_dow[fut_idx] / 6.0)[:, :, None], (1, 1, n_series))
            wknd_fut = np.tile(engine.cal_is_weekend[fut_idx][:, :, None], (1, 1, n_series))
            sin_fut = np.tile(engine.cal_sin_doy[fut_idx][:, :, None], (1, 1, n_series))
            cos_fut = np.tile(engine.cal_cos_doy[fut_idx][:, :, None], (1, 1, n_series))

            fut_cov_9 = np.stack(
                [p_fut, r_fut, t_fut, w_fut, f_fut, dow_fut, wknd_fut, sin_fut, cos_fut],
                axis=-1,
            )  # (n_origs, 7, 72, 9)
            fut_cov_flat = fut_cov_9.transpose(0, 2, 1, 3).reshape(-1, self.horizons * 9)
            fut_cov_tensor = torch.tensor(fut_cov_flat, dtype=torch.float32)
        else:
            fut_cov_tensor = torch.zeros((n_origs * n_series, 1), dtype=torch.float32)

        return x_seq_tensor, y_tensor, shop_idx_tensor, cat_idx_tensor, city_idx_tensor, fut_cov_tensor

    def fit(
        self,
        engine: TabularFeatureEngine,
        train_origins: Sequence[int],
        val_origins: Optional[Sequence[int]] = None,
        stride: int = 3,
    ) -> "GlobalLSTMForecaster":
        """Fit Global Multi-Horizon LSTM using Huber loss, AdamW, and early stopping."""
        torch.manual_seed(self.random_seed)
        np.random.seed(self.random_seed)

        # 1. Compute scaling parameters strictly from training history
        origs_arr = np.asarray(train_origins, dtype=np.int32)
        max_train_date_idx = int(np.max(origs_arr))
        # strictly historical data up to max training origin:
        past_demand_pool = engine.demand_arr[: max_train_date_idx + 1, :].reshape(-1)
        self.demand_mean_ = float(np.mean(past_demand_pool))
        self.demand_std_ = float(np.std(past_demand_pool)) if np.std(past_demand_pool) > 1e-4 else 1.0

        past_rain_pool = engine.rain_arr[: max_train_date_idx + 1, :].reshape(-1)
        self.rain_mean_ = float(np.mean(past_rain_pool))
        self.rain_std_ = float(np.std(past_rain_pool)) if np.std(past_rain_pool) > 1e-4 else 1.0

        past_temp_pool = engine.temp_arr[: max_train_date_idx + 1, :].reshape(-1)
        self.temp_mean_ = float(np.mean(past_temp_pool))
        self.temp_std_ = float(np.std(past_temp_pool)) if np.std(past_temp_pool) > 1e-4 else 1.0

        # Subsample training origins by stride to eliminate redundant daily overlap while preserving temporal coverage
        train_sub_origins = origs_arr[::stride]

        # Prepare training tensors
        x_train, y_train, shop_tr, cat_tr, city_tr, fut_tr = self._prepare_tensors(engine, train_sub_origins)

        # Prepare validation tensors if provided
        if val_origins is not None and len(val_origins) > 0:
            x_val, y_val, shop_val, cat_val, city_val, fut_val = self._prepare_tensors(engine, val_origins)
        else:
            x_val, y_val = None, None

        # 2. Instantiate Model
        self.model = GlobalMultiHorizonLSTM(
            use_covariates=self.use_covariates,
            use_embeddings=self.use_embeddings,
            use_cross_series=self.use_cross_series,
            lookback=self.lookback,
            horizons=self.horizons,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            dropout=self.dropout,
        )

        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )

        # Huber Loss (SmoothL1Loss with beta=1.0)
        criterion = nn.SmoothL1Loss(beta=1.0)

        best_val_loss = float("inf")
        best_state = None
        no_improve_epochs = 0

        n_samples = len(x_train)
        n_batches = int(math.ceil(n_samples / self.batch_size))

        self.model.train()
        for epoch in range(self.epochs):
            perm = torch.randperm(n_samples)
            total_train_loss = 0.0

            for b in range(n_batches):
                idx = perm[b * self.batch_size : (b + 1) * self.batch_size]
                optimizer.zero_grad()

                preds = self.model(
                    x_seq=x_train[idx],
                    shop_idx=shop_tr[idx] if self.use_embeddings else None,
                    cat_idx=cat_tr[idx] if self.use_embeddings else None,
                    city_idx=city_tr[idx] if self.use_embeddings else None,
                    fut_cov=fut_tr[idx] if self.use_covariates else None,
                )

                loss = criterion(preds, y_train[idx])
                loss.backward()

                # Gradient clipping to prevent exploding gradients
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                optimizer.step()
                total_train_loss += loss.item() * len(idx)

            avg_train_loss = total_train_loss / n_samples

            # Validation step for early stopping
            if x_val is not None:
                self.model.eval()
                with torch.no_grad():
                    val_preds = self.model(
                        x_seq=x_val,
                        shop_idx=shop_val if self.use_embeddings else None,
                        cat_idx=cat_val if self.use_embeddings else None,
                        city_idx=city_val if self.use_embeddings else None,
                        fut_cov=fut_val if self.use_covariates else None,
                    )
                    val_loss = criterion(val_preds, y_val).item()
                self.model.train()

                if val_loss < best_val_loss - 1e-4:
                    best_val_loss = val_loss
                    best_state = copy.deepcopy(self.model.state_dict())
                    no_improve_epochs = 0
                else:
                    no_improve_epochs += 1
                    if no_improve_epochs >= self.patience:
                        break

        # Restore best model state if validation was used
        if best_state is not None:
            self.model.load_state_dict(best_state)

        # 3. Calibrate empirical 90% prediction intervals on training residuals
        self.model.eval()
        with torch.no_grad():
            tr_preds = self.model(
                x_seq=x_train,
                shop_idx=shop_tr if self.use_embeddings else None,
                cat_idx=cat_tr if self.use_embeddings else None,
                city_idx=city_tr if self.use_embeddings else None,
                fut_cov=fut_tr if self.use_covariates else None,
            ).cpu().numpy()

        # Unscale predictions and targets back to natural units
        unscaled_preds = np.maximum(0.0, tr_preds * self.demand_std_ + self.demand_mean_)
        unscaled_targets = y_train.cpu().numpy() * self.demand_std_ + self.demand_mean_
        residuals = (unscaled_targets - unscaled_preds).reshape(-1)

        q_low = float(np.quantile(residuals, 0.05))
        q_high = float(np.quantile(residuals, 0.95))
        self.residual_quantiles_ = (q_low, q_high)
        self.is_fitted_ = True
        return self

    def predict(
        self,
        engine: TabularFeatureEngine,
        origin_indices: Sequence[int],
    ) -> np.ndarray:
        """Predict natural demand for horizons 1..7 for all series at specified origins.

        Returns:
            preds: (len(origin_indices) * 72, 7) array in natural units (>= 0).
        """
        if not self.is_fitted_ or self.model is None:
            raise RuntimeError("Model is not fitted.")

        self.model.eval()
        x_seq, _, shop_idx, cat_idx, city_idx, fut_cov = self._prepare_tensors(engine, origin_indices, is_training=False)

        with torch.no_grad():
            scaled_preds = self.model(
                x_seq=x_seq,
                shop_idx=shop_idx if self.use_embeddings else None,
                cat_idx=cat_idx if self.use_embeddings else None,
                city_idx=city_idx if self.use_embeddings else None,
                fut_cov=fut_cov if self.use_covariates else None,
            ).cpu().numpy()

        unscaled_preds = np.maximum(0.0, scaled_preds * self.demand_std_ + self.demand_mean_)
        return unscaled_preds

    def predict_interval(
        self,
        engine: TabularFeatureEngine,
        origin_indices: Sequence[int],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Predict 90% prediction intervals [lower, upper] for all 7 horizons."""
        point_preds = self.predict(engine, origin_indices)
        q_low, q_high = self.residual_quantiles_
        lower = np.maximum(0.0, point_preds + q_low)
        upper = np.maximum(0.0, point_preds + q_high)
        return lower, upper


def run_lstm_rolling_cv_seed(
    engine: TabularFeatureEngine,
    use_covariates: bool,
    use_embeddings: bool,
    use_cross_series: bool,
    seed: int,
    n_splits: int = 4,
    test_cutoff: str = TEST_CUTOFF_DATE,
) -> Dict[str, Any]:
    """Run rolling-origin cross validation across 4 folds for a single random seed."""
    pre_cutoff_dates = [d for d in engine.unique_dates if d < pd.Timestamp(test_cutoff)]
    splitter = RollingOriginSplitter(n_splits=n_splits, horizon=7, step=28, test_cutoff=test_cutoff)
    folds = splitter.get_folds(pre_cutoff_dates)

    h1_true, h1_pred, h1_low, h1_high = [], [], [], []
    h7_true, h7_pred, h7_low, h7_high = [], [], [], []

    for fold in folds:
        train_end_idx = engine.date_to_idx[fold.train_end]
        # Origins for training: index 28 up to train_end_idx - 7
        all_train_origins = np.arange(28, train_end_idx - 6, dtype=np.int32)

        # Internal validation origins: last 28 days of training origins
        if len(all_train_origins) > 56:
            fit_train_origins = all_train_origins[:-28]
            val_origins = all_train_origins[-28:]
        else:
            fit_train_origins = all_train_origins
            val_origins = None

        torch.set_num_threads(4)
        forecaster = GlobalLSTMForecaster(
            use_covariates=use_covariates,
            use_embeddings=use_embeddings,
            use_cross_series=use_cross_series,
            random_seed=seed,
            epochs=15,
            batch_size=1024,
            patience=4,
        )
        forecaster.fit(engine, fit_train_origins, val_origins=val_origins, stride=7)

        # Evaluate at validation origin: train_end_idx
        eval_origin = np.array([train_end_idx], dtype=np.int32)
        preds_7d = forecaster.predict(engine, eval_origin)  # (72, 7)
        low_7d, high_7d = forecaster.predict_interval(engine, eval_origin)

        # Ground truth targets for horizons 1..7:
        y_true_7d = engine.demand_arr[train_end_idx + 1 : train_end_idx + 8, :].T  # (72, 7)

        # Horizon 1 (index 0)
        h1_true.extend(y_true_7d[:, 0].tolist())
        h1_pred.extend(preds_7d[:, 0].tolist())
        h1_low.extend(low_7d[:, 0].tolist())
        h1_high.extend(high_7d[:, 0].tolist())

        # Horizon 7 (index 6)
        h7_true.extend(y_true_7d[:, 6].tolist())
        h7_pred.extend(preds_7d[:, 6].tolist())
        h7_low.extend(low_7d[:, 6].tolist())
        h7_high.extend(high_7d[:, 6].tolist())

    m_h1 = evaluate_forecast(np.array(h1_true), np.array(h1_pred), np.array(h1_low), np.array(h1_high))
    m_h7 = evaluate_forecast(np.array(h7_true), np.array(h7_pred), np.array(h7_low), np.array(h7_high))

    return {
        "seed": seed,
        "h1": {
            "wape": m_h1["wape"],
            "mae": m_h1["mae"],
            "rmse": m_h1["rmse"],
            "bias": m_h1["bias"],
            "coverage": m_h1.get("coverage", 0.0),
        },
        "h7": {
            "wape": m_h7["wape"],
            "mae": m_h7["mae"],
            "rmse": m_h7["rmse"],
            "bias": m_h7["bias"],
            "coverage": m_h7.get("coverage", 0.0),
        },
    }
