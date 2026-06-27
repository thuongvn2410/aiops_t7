from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from joblib import dump, load
from sklearn.ensemble import GradientBoostingClassifier


class XGBoostAnomaly:
    def __init__(self) -> None:
        self.model = None
        self.best_params_: dict[str, float | int | str] = {}

    def fit(self, x_train: np.ndarray, y_train: np.ndarray, x_val: np.ndarray | None = None, y_val: np.ndarray | None = None) -> "XGBoostAnomaly":
        neg = max(1, int((y_train == 0).sum()))
        pos = max(1, int((y_train == 1).sum()))
        scale_pos_weight = neg / pos
        try:
            from xgboost import XGBClassifier

            self.model = XGBClassifier(
                n_estimators=80,
                max_depth=3,
                learning_rate=0.1,
                objective="binary:logistic",
                eval_metric="logloss",
                tree_method="hist",
                device="cuda",
                scale_pos_weight=scale_pos_weight,
                random_state=42,
            )
            self.model.fit(x_train, y_train)
            self.best_params_ = {"backend": "xgboost", "scale_pos_weight": scale_pos_weight}
        except Exception:
            self.model = GradientBoostingClassifier(random_state=42)
            self.model.fit(x_train, y_train)
            self.best_params_ = {"backend": "sklearn_gradient_boosting", "scale_pos_weight": scale_pos_weight}
        return self

    def score_samples(self, x: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(x)[:, 1]

    def save(self, path) -> None:
        dump(self.model, path)

    def save_params(self, path: Path) -> None:
        path.write_text(json.dumps(self.best_params_, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path) -> "XGBoostAnomaly":
        instance = cls()
        instance.model = load(path)
        return instance
