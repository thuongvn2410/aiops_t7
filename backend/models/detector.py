from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from backend.config import ANOMALY_THRESHOLD, MODEL_STORE
from backend.db.client import clickhouse_status, get_client
from backend.models.features import build_features, feature_matrix
from backend.models.trainer import save_model, train_from_clickhouse


class Detector:
    def __init__(self, model=None, threshold: float = ANOMALY_THRESHOLD) -> None:
        self.model = model
        self.threshold = float(threshold)
        self.model_name = "IsolationForest" if model is not None else "fixed-threshold"

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def _metric_boost(self, features: pd.DataFrame, score: np.ndarray) -> np.ndarray:
        """Domain-specific score boosts — applied on top of any model score."""
        values = features["value"].astype(float).to_numpy()
        roc = np.abs(features["rate_of_change"].astype(float).to_numpy())
        metric_names = features.get("metric_name", pd.Series([""] * len(features))).astype(str).to_numpy()
        score = score.copy()
        for i, metric_name in enumerate(metric_names):
            v, r = values[i], roc[i]
            if metric_name == "error_rate":
                score[i] = max(score[i], min(1.0, v / 0.35))
            elif metric_name == "cpu_usage":
                score[i] = max(score[i], min(1.0, max(0.0, v - 65.0) / 25.0))
            elif metric_name in ("latency_ms", "request_latency", "query_latency"):
                score[i] = max(score[i], min(1.0, max(0.0, v - 220.0) / 220.0))
                score[i] = max(score[i], min(1.0, r / 80.0))
            elif metric_name in ("active_connections", "connections"):
                score[i] = max(score[i], min(1.0, max(0.0, v - 500.0) / 1500.0))
            elif metric_name == "throughput":
                score[i] = max(score[i], min(1.0, max(0.0, v - 1500.0) / 600.0))
        return np.clip(score, 0.0, 1.0)

    def predict_scores(self, features: pd.DataFrame) -> np.ndarray:
        if features.empty:
            return np.array([], dtype=float)
        matrix = feature_matrix(features)
        if self.model is not None:
            raw = -self.model.decision_function(matrix)
            score = 1.0 / (1.0 + np.exp(-raw))
        else:
            values = features["value"].astype(float).to_numpy()
            rolling = features["rolling_mean_12"].astype(float).to_numpy()
            std = np.maximum(features["rolling_std_12"].astype(float).to_numpy(), 1e-6)
            z = np.abs(values - rolling) / std
            score = np.clip(z / 4.0, 0.0, 1.0)
        return self._metric_boost(features, score)

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        scored = features.copy()
        scored["anomaly_score"] = self.predict_scores(scored)
        scored["is_anomaly"] = scored["anomaly_score"] > self.threshold
        scored["model_name"] = self.model_name
        return scored


def load_or_train_detector(retrain: bool = False) -> Detector:
    model_path = MODEL_STORE / "isolation_forest.pkl"
    manifest_path = MODEL_STORE / "manifest.json"
    if model_path.exists() and manifest_path.exists() and not retrain:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return Detector(joblib.load(model_path), float(manifest.get("threshold", ANOMALY_THRESHOLD)))
    try:
        if clickhouse_status() != "ok":
            save_model(None, ANOMALY_THRESHOLD, 0, model_path)
            return Detector(None, ANOMALY_THRESHOLD)
        model, threshold, rows_used = train_from_clickhouse(get_client(), lookback_minutes=15)
        save_model(model, threshold, rows_used, model_path)
        return Detector(model, threshold)
    except Exception:
        save_model(None, ANOMALY_THRESHOLD, 0, model_path)
        return Detector(None, ANOMALY_THRESHOLD)


def selftest() -> dict:
    rng = np.random.default_rng(42)
    timestamps = [datetime.now(timezone.utc) - timedelta(seconds=5 * i) for i in range(150, 0, -1)]
    rows = pd.DataFrame(
        {
            "service_name": "svc-order",
            "metric_name": "latency_ms",
            "value": np.r_[rng.normal(120, 8, 145), rng.normal(360, 20, 5)],
            "timestamp": timestamps,
            "unit": "ms",
        }
    )
    features = build_features(rows)
    model = IsolationForest(contamination=0.05, n_estimators=50, random_state=42).fit(feature_matrix(features))
    detector = Detector(model, 0.5)
    scored = detector.predict(features.tail(10))
    return {"rows": len(scored), "max_score": float(scored["anomaly_score"].max()), "model_loaded": detector.loaded}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrain", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        print(json.dumps(selftest(), indent=2))
    else:
        detector = load_or_train_detector(retrain=args.retrain)
        print(json.dumps({"model_loaded": detector.loaded, "threshold": detector.threshold, "model_name": detector.model_name}, indent=2))


if __name__ == "__main__":
    main()
