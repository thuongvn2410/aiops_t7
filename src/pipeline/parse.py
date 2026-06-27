from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import load
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score, roc_curve

from src.models.autoencoder import AutoencoderAnomaly
from src.models.deep_svdd import DeepSVDDAnomaly
from src.models.ensemble import ScoreEnsemble
from src.models.isolation_forest import IsolationForestAnomaly
from src.models.tft_model import TFTAnomaly
from src.models.xgboost_model import XGBoostAnomaly
from src.pipeline.common import append_jsonl, utc_now, write_json
from src.pipeline.state import resolve_run_id, run_dir, stage_complete


def _load_features(root: Path, split: str = "test") -> tuple[np.ndarray, np.ndarray]:
    frame = pd.read_parquet(root / "splits" / f"{split}.parquet")
    payload = load(root / "process" / "feature_scaler.joblib")
    x = payload["scaler"].transform(frame[payload["features"]])
    return x, frame["label"].to_numpy()


def load_model_scores(model_name: str, checkpoint: Path, x: np.ndarray) -> np.ndarray:
    if model_name == "isolation_forest":
        return IsolationForestAnomaly.load(checkpoint).score_samples(x)
    if model_name == "autoencoder":
        return AutoencoderAnomaly.load(checkpoint).score_samples(x)
    if model_name == "svdd":
        return DeepSVDDAnomaly.load(checkpoint).score_samples(x)
    if model_name == "xgboost":
        return XGBoostAnomaly.load(checkpoint).score_samples(x)
    if model_name == "tft":
        return TFTAnomaly.load(checkpoint).score_samples(x)
    raise ValueError(f"Use load_ensemble_scores for model={model_name}")


def _threshold_youden(labels: np.ndarray, scores: np.ndarray) -> float:
    if len(set(labels.tolist())) < 2:
        return float(np.quantile(scores, 0.95))
    fpr, tpr, thresholds = roc_curve(labels, scores)
    return float(thresholds[np.argmax(tpr - fpr)])


def _model_metrics(name: str, labels: np.ndarray, scores: np.ndarray, elapsed_ms: float) -> dict:
    threshold = _threshold_youden(labels, scores)
    pred = (scores >= threshold).astype(int)
    return {
        "name": name,
        "precision": float(precision_score(labels, pred, zero_division=0)),
        "recall": float(recall_score(labels, pred, zero_division=0)),
        "f1": float(f1_score(labels, pred, zero_division=0)),
        "auc_roc": float(roc_auc_score(labels, scores)) if len(set(labels.tolist())) > 1 else 0.0,
        "auc_pr": float(average_precision_score(labels, scores)) if len(set(labels.tolist())) > 1 else 0.0,
        "inference_ms": float(elapsed_ms),
        "optimal_threshold": threshold,
        "confusion_matrix": confusion_matrix(labels, pred).tolist(),
        "scores": [float(v) for v in scores],
        "labels": [int(v) for v in labels],
    }


def run(run_id: str | None = None) -> str:
    selected = resolve_run_id(run_id)
    if stage_complete(selected, "parse"):
        print(f"parse skip run_id={selected}: metrics.json already exists")
        return selected
    root = run_dir(selected)
    x_test, y_test = _load_features(root, "test")
    payload = {"run_id": selected, "evaluated_at": utc_now(), "models": []}
    scores_for_ensemble: list[np.ndarray] = []
    for model_name in ["isolation_forest", "autoencoder", "svdd", "xgboost", "tft"]:
        checkpoint = root / "checkpoints" / model_name / "best.pt"
        if not checkpoint.exists():
            warning = {"model": model_name, "error": "missing checkpoint", "at": utc_now()}
            append_jsonl(root / "parse_errors.jsonl", warning)
            print(f"WARNING missing checkpoint model={model_name}; skipping")
            continue
        started = time.perf_counter()
        try:
            scores = load_model_scores(model_name, checkpoint, x_test)
            elapsed_ms = (time.perf_counter() - started) * 1000 / max(1, len(x_test))
            payload["models"].append(_model_metrics(model_name, y_test, scores, elapsed_ms))
            if model_name in {"autoencoder", "svdd", "xgboost"}:
                scores_for_ensemble.append(scores)
        except Exception as exc:
            append_jsonl(root / "parse_errors.jsonl", {"model": model_name, "error": str(exc), "at": utc_now()})
            print(f"WARNING parse failed model={model_name}: {exc}")
    ensemble_ckpt = root / "checkpoints" / "ensemble" / "best.pt"
    if ensemble_ckpt.exists() and len(scores_for_ensemble) == 3:
        started = time.perf_counter()
        scores = ScoreEnsemble.load(ensemble_ckpt).score_samples(np.vstack(scores_for_ensemble).T)
        elapsed_ms = (time.perf_counter() - started) * 1000 / max(1, len(x_test))
        payload["models"].append(_model_metrics("ensemble", y_test, scores, elapsed_ms))
    elif not ensemble_ckpt.exists():
        append_jsonl(root / "parse_errors.jsonl", {"model": "ensemble", "error": "missing checkpoint", "at": utc_now()})
        print("WARNING missing checkpoint model=ensemble; skipping")
    public_payload = {
        "run_id": payload["run_id"],
        "evaluated_at": payload["evaluated_at"],
        "models": [
            {k: v for k, v in model.items() if k not in {"scores", "labels", "confusion_matrix"}}
            for model in payload["models"]
        ],
    }
    write_json(root / "parsed" / "metrics_full.json", payload)
    write_json(root / "parsed" / "metrics.json", public_payload)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    run(args.run_id)


if __name__ == "__main__":
    main()
