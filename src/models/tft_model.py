from __future__ import annotations

import numpy as np

from src.models.autoencoder import AutoencoderAnomaly


class TFTAnomaly(AutoencoderAnomaly):
    """Compact forecast-error proxy for the TFT contract in smoke runs."""

    def fit(self, x_train: np.ndarray, x_val: np.ndarray | None = None, epochs: int = 2, batch_size: int = 64) -> "TFTAnomaly":
        return super().fit(x_train, x_val, epochs=max(epochs, 2), batch_size=batch_size)
