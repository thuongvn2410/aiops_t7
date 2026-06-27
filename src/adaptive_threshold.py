from __future__ import annotations

import numpy as np
from scipy.stats import genpareto


class POTThreshold:
    def __init__(self, quantile: float = 0.98, update_every: int = 1000) -> None:
        self.quantile = quantile
        self.update_every = update_every
        self.threshold_: float = 0.0
        self.buffer: list[float] = []

    def fit(self, scores) -> "POTThreshold":
        values = np.asarray(scores, dtype=float)
        base = float(np.quantile(values, self.quantile))
        excess = values[values > base] - base
        if len(excess) >= 5:
            shape, loc, scale = genpareto.fit(excess, floc=0)
            self.threshold_ = float(base + genpareto.ppf(0.95, shape, loc=loc, scale=scale))
        else:
            self.threshold_ = base
        return self

    def update(self, score: float) -> float:
        self.buffer.append(float(score))
        if len(self.buffer) >= self.update_every:
            self.fit(self.buffer)
            self.buffer.clear()
        return self.threshold_
