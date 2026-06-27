from __future__ import annotations

import numpy as np
from joblib import dump, load
from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score


class IsolationForestAnomaly:
    def __init__(self, random_state: int = 42) -> None:
        self.random_state = random_state
        self.model = IsolationForest(n_estimators=100, contamination=0.1, random_state=random_state)

    def fit(self, x_train: np.ndarray, x_val: np.ndarray | None = None, y_val: np.ndarray | None = None) -> "IsolationForestAnomaly":
        best_model = self.model
        best_score = -1.0
        grid = [0.03, 0.05, 0.08, 0.10, 0.15]
        for contamination in grid:
            model = IsolationForest(n_estimators=100, contamination=contamination, random_state=self.random_state)
            model.fit(x_train)
            if x_val is None or y_val is None or len(set(y_val.tolist())) < 2:
                best_model = model
                break
            labels = (model.decision_function(x_val) * -1 > 0).astype(int)
            score = f1_score(y_val, labels, zero_division=0)
            if score > best_score:
                best_model = model
                best_score = score
        self.model = best_model
        return self

    def score_samples(self, x: np.ndarray) -> np.ndarray:
        return -self.model.decision_function(x)

    def save(self, path) -> None:
        dump(self.model, path)

    @classmethod
    def load(cls, path) -> "IsolationForestAnomaly":
        instance = cls()
        instance.model = load(path)
        return instance
