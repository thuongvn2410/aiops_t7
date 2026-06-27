from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.preprocessing import StandardScaler

from src.models.autoencoder import AutoencoderAnomaly
from src.models.deep_svdd import DeepSVDDAnomaly
from src.models.ensemble import ScoreEnsemble
from src.models.isolation_forest import IsolationForestAnomaly
from src.models.tft_model import TFTAnomaly
from src.models.xgboost_model import XGBoostAnomaly
from src.pipeline.common import numeric_feature_columns, read_config, set_random_seed, utc_now, write_json
from src.pipeline.state import resolve_run_id, run_dir

MODEL_ALIASES = {
    "isolation_forest": "isolation_forest",
    "autoencoder": "autoencoder",
    "svdd": "svdd",
    "xgboost": "xgboost",
    "tft": "tft",
    "ensemble": "ensemble",
}


def _gpu_stats() -> dict[str, float | bool | str]:
    try:
        import torch

        available = torch.cuda.is_available()
        if not available:
            return {"cuda_available": False, "gpu_memory_peak_mb": 0.0}
        return {
            "cuda_available": True,
            "device": torch.cuda.get_device_name(0),
            "gpu_memory_peak_mb": float(torch.cuda.max_memory_allocated() / 1024 / 1024),
        }
    except Exception as exc:
        return {"cuda_available": False, "gpu_memory_peak_mb": 0.0, "gpu_error": str(exc)}


def _load_xy(root: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    train = pd.read_parquet(root / "splits" / "train.parquet")
    val = pd.read_parquet(root / "splits" / "val.parquet")
    test = pd.read_parquet(root / "splits" / "test.parquet")
    features = numeric_feature_columns(train)
    scaler = StandardScaler()
    x_train = scaler.fit_transform(train[features])
    x_val = scaler.transform(val[features])
    x_test = scaler.transform(test[features])
    dump({"scaler": scaler, "features": features}, root / "process" / "feature_scaler.joblib")
    return x_train, train["label"].to_numpy(), x_val, val["label"].to_numpy(), x_test, test["label"].to_numpy(), features


def _checkpoint(root: Path, model_name: str) -> Path:
    return root / "checkpoints" / model_name / "best.pt"


def _train_one(model_name: str, root: Path, force: bool, arrays: tuple) -> dict:
    ckpt = _checkpoint(root, model_name)
    if ckpt.exists() and not force:
        return {"name": model_name, "skipped": True, "checkpoint": str(ckpt)}
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    x_train, y_train, x_val, y_val, _x_test, _y_test, _features = arrays
    started = time.perf_counter()
    if model_name == "isolation_forest":
        model = IsolationForestAnomaly().fit(x_train, x_val, y_val)
        model.save(ckpt)
    elif model_name == "autoencoder":
        model = AutoencoderAnomaly(x_train.shape[1]).fit(x_train, x_val)
        model.save(ckpt)
    elif model_name == "svdd":
        model = DeepSVDDAnomaly(x_train.shape[1]).fit(x_train, x_val)
        model.save(ckpt)
    elif model_name == "xgboost":
        model = XGBoostAnomaly().fit(x_train, y_train, x_val, y_val)
        model.save(ckpt)
        model.save_params(root / "process" / "xgb_best_params.json")
    elif model_name == "tft":
        model = TFTAnomaly(x_train.shape[1]).fit(x_train, x_val)
        model.save(ckpt)
    elif model_name == "ensemble":
        members = []
        for member_name in ["autoencoder", "svdd", "xgboost"]:
            member_path = _checkpoint(root, member_name)
            if not member_path.exists():
                raise FileNotFoundError(f"Missing member checkpoint for ensemble: {member_name}")
            from src.pipeline.parse import load_model_scores

            members.append(load_model_scores(member_name, member_path, x_val))
        score_matrix = np.vstack(members).T
        model = ScoreEnsemble().fit(score_matrix, y_val)
        model.save(ckpt)
    else:
        raise ValueError(f"Unsupported model: {model_name}")
    elapsed = time.perf_counter() - started
    stats = _gpu_stats()
    return {"name": model_name, "skipped": False, "checkpoint": str(ckpt), "wall_clock_sec": elapsed, **stats}


def run(run_id: str | None = None, model: str = "all", force: bool = False) -> str:
    selected = resolve_run_id(run_id)
    root = run_dir(selected)
    (root / "process").mkdir(parents=True, exist_ok=True)
    set_random_seed(42)
    cfg = read_config()
    models = ["isolation_forest", "autoencoder", "svdd", "xgboost", "tft", "ensemble"] if model == "all" else [MODEL_ALIASES.get(model, model)]
    if "ensemble" in models:
        for dependency in ["autoencoder", "svdd", "xgboost"]:
            if dependency not in models and not _checkpoint(root, dependency).exists():
                models.insert(0, dependency)
    arrays = _load_xy(root)
    try:
        import mlflow

        mlflow.set_tracking_uri(str((Path.cwd() / "mlruns").resolve()))
        mlflow.pytorch.autolog(disable=False)
    except Exception:
        pass
    print("cuda_available warning=false" if _gpu_stats()["cuda_available"] else "WARNING cuda_available=false; continuing on CPU")
    manifest = {
        "run_id": selected,
        "started_at": utc_now(),
        "seeds": cfg.get("seeds", {"python": 42, "numpy": 42, "torch": 42}),
        "hyperparameters": cfg.get("models", {}),
        "models": [],
    }
    for model_name in models:
        try:
            result = _train_one(model_name, root, force, arrays)
        except Exception as exc:
            result = {"name": model_name, "error": str(exc), "skipped": False}
        manifest["models"].append(result)
        write_json(root / "process" / "run_manifest.json", manifest)
        print(f"model={model_name} result={result}")
    manifest["finished_at"] = utc_now()
    write_json(root / "process" / "run_manifest.json", manifest)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--model", default="all", choices=["all", "isolation_forest", "autoencoder", "svdd", "xgboost", "tft", "ensemble"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run(args.run_id, args.model, args.force)


if __name__ == "__main__":
    main()
