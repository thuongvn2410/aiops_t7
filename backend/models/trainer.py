from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from backend.config import MODEL_STORE
from backend.db.queries import q_training_metrics
from backend.models.features import build_features, feature_matrix, rows_to_frame


def train_from_clickhouse(client, lookback_minutes: int = 15):
    result = client.query(q_training_metrics(lookback_minutes))
    frame = build_features(rows_to_frame(result))
    rows_used = len(frame)
    if rows_used < 100:
        return None, 0.6, rows_used
    model = IsolationForest(contamination=0.05, n_estimators=100, random_state=42)
    matrix = feature_matrix(frame)
    model.fit(matrix)
    raw_scores = -model.decision_function(matrix)
    scores = 1.0 / (1.0 + np.exp(-raw_scores))
    threshold = float(np.percentile(scores, 95))
    return model, threshold, rows_used


def save_model(model, threshold: float, rows_used: int, model_path: Path | None = None) -> dict:
    model_path = model_path or MODEL_STORE / "isolation_forest.pkl"
    manifest_path = MODEL_STORE / "manifest.json"
    if model is not None:
        joblib.dump(model, model_path)
    manifest = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "rows_used": int(rows_used),
        "threshold": float(threshold),
        "model_path": str(model_path),
        "model_loaded": model is not None,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
