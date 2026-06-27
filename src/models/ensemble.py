from __future__ import annotations

import numpy as np
from joblib import dump, load
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


class ScoreEnsemble:
    def __init__(self) -> None:
        self.scaler = StandardScaler()
        self.model = LogisticRegression(max_iter=500, class_weight="balanced", random_state=42)

    def fit(self, scores: np.ndarray, labels: np.ndarray) -> "ScoreEnsemble":
        scaled = self.scaler.fit_transform(scores)
        self.model.fit(scaled, labels)
        return self

    def score_samples(self, scores: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(self.scaler.transform(scores))[:, 1]

    def predict_event(self, scores: np.ndarray) -> dict[str, float | int]:
        score = float(self.score_samples(scores.reshape(1, -1))[0])
        return {"score": score, "label": int(score >= 0.5), "confidence": max(score, 1 - score)}

    def save(self, path) -> None:
        dump({"scaler": self.scaler, "model": self.model}, path)

    @classmethod
    def load(cls, path) -> "ScoreEnsemble":
        payload = load(path)
        instance = cls()
        instance.scaler = payload["scaler"]
        instance.model = payload["model"]
        return instance
