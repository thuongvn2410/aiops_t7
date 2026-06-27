from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

import numpy as np
from joblib import load

from src.models.autoencoder import AutoencoderAnomaly
from src.models.deep_svdd import DeepSVDDAnomaly
from src.models.ensemble import ScoreEnsemble
from src.models.isolation_forest import IsolationForestAnomaly
from src.models.tft_model import TFTAnomaly
from src.models.xgboost_model import XGBoostAnomaly
from src.pipeline.common import append_jsonl, utc_now
from src.pipeline.state import get_latest_run_id, run_dir


class RuntimeScorer:
    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id or get_latest_run_id()
        if not self.run_id:
            raise RuntimeError("No trained run found. Run the pipeline before starting realtime scoring.")
        self.root = run_dir(self.run_id)
        self.scaler_payload = load(self.root / "process" / "feature_scaler.joblib")
        self.features: list[str] = self.scaler_payload["features"]
        self.scaler = self.scaler_payload["scaler"]
        self.models = self._load_models()
        self.thresholds = self._load_thresholds()
        self.history: deque[dict[str, float]] = deque(maxlen=120)
        self.lock = Lock()

    def _load_models(self) -> dict[str, Any]:
        checkpoints = self.root / "checkpoints"
        loaded: dict[str, Any] = {}
        paths = {
            "isolation_forest": checkpoints / "isolation_forest" / "best.pt",
            "autoencoder": checkpoints / "autoencoder" / "best.pt",
            "svdd": checkpoints / "svdd" / "best.pt",
            "xgboost": checkpoints / "xgboost" / "best.pt",
            "tft": checkpoints / "tft" / "best.pt",
            "ensemble": checkpoints / "ensemble" / "best.pt",
        }
        if paths["isolation_forest"].exists():
            loaded["isolation_forest"] = IsolationForestAnomaly.load(paths["isolation_forest"])
        if paths["autoencoder"].exists():
            loaded["autoencoder"] = AutoencoderAnomaly.load(paths["autoencoder"])
        if paths["svdd"].exists():
            loaded["svdd"] = DeepSVDDAnomaly.load(paths["svdd"])
        if paths["xgboost"].exists() and os.getenv("AIOPS_ENABLE_XGBOOST_RUNTIME") == "1":
            loaded["xgboost"] = XGBoostAnomaly.load(paths["xgboost"])
        if paths["tft"].exists():
            loaded["tft"] = TFTAnomaly.load(paths["tft"])
        if paths["ensemble"].exists() and "xgboost" in loaded:
            loaded["ensemble"] = ScoreEnsemble.load(paths["ensemble"])
        return loaded

    def _load_thresholds(self) -> dict[str, float]:
        metrics_path = self.root / "parsed" / "metrics.json"
        if not metrics_path.exists():
            return {"ensemble": 0.5, "xgboost": 0.5}
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        return {model["name"]: float(model["optimal_threshold"]) for model in payload.get("models", [])}

    def _base_features(self, telemetry: dict[str, Any]) -> dict[str, float]:
        nested = telemetry.get("features", {})
        merged = {**telemetry, **nested}
        numeric = {k: float(v) for k, v in merged.items() if isinstance(v, (int, float))}
        return {
            "cpu_usage": numeric.get("cpu_usage", numeric.get("cpu", 0.0)),
            "memory_usage": numeric.get("memory_usage", numeric.get("memory", 0.0)),
            "latency_ms": numeric.get("latency_ms", numeric.get("latency", 0.0)),
            "error_rate": numeric.get("error_rate", 1.0 if numeric.get("error", 0.0) else 0.0),
            "duration_ms": numeric.get("duration_ms", numeric.get("latency_ms", 0.0)),
            "error": numeric.get("error", 1.0 if numeric.get("error_rate", 0.0) > 0.1 else 0.0),
        }

    def _feature_vector(self, telemetry: dict[str, Any]) -> np.ndarray:
        current = self._base_features(telemetry)
        with self.lock:
            self.history.append(current)
            history = list(self.history)
        values: dict[str, float] = {}
        for key in ["cpu_usage", "memory_usage", "latency_ms", "error_rate"]:
            series = np.array([row.get(key, 0.0) for row in history], dtype=float)
            values[key] = current.get(key, 0.0)
            for window in [5, 15, 60]:
                tail = series[-window:]
                values[f"{key}_roll_mean_{window}"] = float(tail.mean()) if len(tail) else values[key]
                values[f"{key}_roll_std_{window}"] = float(tail.std()) if len(tail) else 0.0
                values[f"{key}_roll_min_{window}"] = float(tail.min()) if len(tail) else values[key]
                values[f"{key}_roll_max_{window}"] = float(tail.max()) if len(tail) else values[key]
            for lag in [1, 5, 10]:
                values[f"{key}_lag_{lag}"] = float(series[-lag - 1]) if len(series) > lag else values[key]
            values[f"{key}_rate"] = float(series[-1] - series[-2]) if len(series) > 1 else 0.0
        durations = np.array([row.get("duration_ms", row.get("latency_ms", 0.0)) for row in history], dtype=float)
        errors = np.array([row.get("error", 0.0) for row in history], dtype=float)
        values["trace_duration_p50"] = float(np.quantile(durations[-5:], 0.50)) if len(durations) else 0.0
        values["trace_duration_p95"] = float(np.quantile(durations[-15:], 0.95)) if len(durations) else 0.0
        values["trace_duration_p99"] = float(np.quantile(durations[-60:], 0.99)) if len(durations) else 0.0
        values["trace_error_rate"] = float(errors[-15:].mean()) if len(errors) else 0.0
        values["trace_call_depth"] = float(telemetry.get("call_depth", telemetry.get("features", {}).get("call_depth", 1.0)))
        row = np.array([[values.get(name, 0.0) for name in self.features]], dtype=float)
        return self.scaler.transform(row)

    def score(self, telemetry: dict[str, Any]) -> dict[str, Any]:
        vector = self._feature_vector(telemetry)
        member_scores: dict[str, float] = {}
        for name in ["autoencoder", "svdd", "xgboost"]:
            if name in self.models:
                try:
                    member_scores[name] = float(self.models[name].score_samples(vector)[0])
                except Exception:
                    continue
        scores = dict(member_scores)
        for name in ["isolation_forest", "tft"]:
            if name in self.models:
                try:
                    scores[name] = float(self.models[name].score_samples(vector)[0])
                except Exception:
                    continue
        if "ensemble" in self.models and all(name in member_scores for name in ["autoencoder", "svdd", "xgboost"]):
            score = float(self.models["ensemble"].score_samples(np.array([[member_scores["autoencoder"], member_scores["svdd"], member_scores["xgboost"]]]))[0])
            model = "ensemble"
        elif "xgboost" in scores:
            score = scores["xgboost"]
            model = "xgboost"
        elif "isolation_forest" in scores:
            score = scores["isolation_forest"]
            model = "isolation_forest"
        elif "autoencoder" in scores:
            score = scores["autoencoder"]
            model = "autoencoder"
        else:
            score = max(scores.values(), default=0.0)
            model = "heuristic"
        threshold = self.thresholds.get(model, 0.5)
        label = int(score >= threshold)
        features = self._base_features(telemetry)
        event = {
            "event_id": str(uuid4()),
            "timestamp": telemetry.get("timestamp") or utc_now(),
            "source": telemetry.get("source", "metric"),
            "anomaly_score": score,
            "label": label,
            "model": model,
            "features": features,
            "rca": None,
            "threshold": threshold,
            "model_scores": scores,
            "raw": telemetry,
        }
        append_jsonl(self.root / "runtime_events.jsonl", event)
        if label:
            append_jsonl(self.root / "runtime_alerts.jsonl", event)
        return event


_SCORER: RuntimeScorer | None = None


def get_scorer(run_id: str | None = None) -> RuntimeScorer:
    global _SCORER
    if _SCORER is None or (run_id and _SCORER.run_id != run_id):
        _SCORER = RuntimeScorer(run_id)
    return _SCORER


def read_jsonl(path: Path, limit: int = 100) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    rows: list[dict[str, Any]] = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows
