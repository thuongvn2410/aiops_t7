from __future__ import annotations

import numpy as np

from src.models.autoencoder import AutoencoderAnomaly


class DeepSVDDAnomaly(AutoencoderAnomaly):
    def fit(self, x_train: np.ndarray, x_val: np.ndarray | None = None, epochs: int = 3, batch_size: int = 64) -> "DeepSVDDAnomaly":
        super().fit(x_train, x_val, epochs=max(epochs, 3), batch_size=batch_size)
        scores = self.score_samples(x_train[: min(256, len(x_train))])
        self.radius_ = float(np.quantile(scores, 0.95))
        print(f"deep_svdd radius={self.radius_:.6f}")
        return self
