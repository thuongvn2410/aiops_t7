from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from src.pipeline.common import read_config
from src.pipeline.state import resolve_run_id, run_dir, stage_complete


def _metric_features(metrics: pd.DataFrame) -> pd.DataFrame:
    frame = metrics.sort_values("timestamp").reset_index(drop=True).copy()
    base = ["cpu_usage", "memory_usage", "latency_ms", "error_rate"]
    for column in base:
        for window in [5, 15, 60]:
            rolled = frame[column].rolling(window=window, min_periods=1)
            frame[f"{column}_roll_mean_{window}"] = rolled.mean()
            frame[f"{column}_roll_std_{window}"] = rolled.std().fillna(0)
            frame[f"{column}_roll_min_{window}"] = rolled.min()
            frame[f"{column}_roll_max_{window}"] = rolled.max()
        for lag in [1, 5, 10]:
            frame[f"{column}_lag_{lag}"] = frame[column].shift(lag).bfill()
        frame[f"{column}_rate"] = frame[column].diff().fillna(0)
    return frame


def _log_features(logs: pd.DataFrame, max_features: int) -> pd.DataFrame:
    vectorizer = TfidfVectorizer(max_features=max_features, token_pattern=r"(?u)\b\w[\w=-]+\b")
    matrix = vectorizer.fit_transform(logs["message"].fillna(""))
    names = [f"log_tfidf_{name}" for name in vectorizer.get_feature_names_out()]
    return pd.DataFrame(matrix.toarray(), columns=names)


def _trace_features(traces: pd.DataFrame) -> pd.DataFrame:
    ordered = traces.sort_values("timestamp").reset_index(drop=True)
    duration = ordered["duration_ms"]
    return pd.DataFrame(
        {
            "trace_duration_p50": duration.rolling(5, min_periods=1).quantile(0.50),
            "trace_duration_p95": duration.rolling(15, min_periods=1).quantile(0.95),
            "trace_duration_p99": duration.rolling(60, min_periods=1).quantile(0.99),
            "trace_error_rate": ordered["error"].rolling(15, min_periods=1).mean(),
            "trace_call_depth": ordered["parent_span_id"].notna().astype(int).rolling(5, min_periods=1).sum(),
        }
    )


def _split(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    total = len(frame)
    train_end = int(total * 0.70)
    val_end = int(total * 0.85)
    return {
        "train": frame.iloc[:train_end].copy(),
        "val": frame.iloc[train_end:val_end].copy(),
        "test": frame.iloc[val_end:].copy(),
    }


def run(run_id: str | None = None) -> str:
    selected = resolve_run_id(run_id)
    if stage_complete(selected, "prepare"):
        print(f"prepare skip run_id={selected}: split files already exist")
        return selected

    root = run_dir(selected)
    metrics = pd.read_parquet(root / "raw" / "metrics.parquet")
    logs = pd.read_parquet(root / "raw" / "logs.parquet")
    traces = pd.read_parquet(root / "raw" / "traces.parquet")
    cfg = read_config()
    features = _metric_features(metrics)
    log_features = _log_features(logs, int(cfg["data"].get("log_tfidf_features", 500)))
    trace_features = _trace_features(traces)
    feature_frame = pd.concat(
        [features[["timestamp", "label"]], features.drop(columns=["timestamp", "label"]), log_features, trace_features],
        axis=1,
    )
    feature_frame = feature_frame.replace([np.inf, -np.inf], 0).fillna(0)

    split_dir = root / "splits"
    split_dir.mkdir(parents=True, exist_ok=True)
    for name, part in _split(feature_frame).items():
        part.to_parquet(split_dir / f"{name}.parquet", index=False)
        print(f"split={name} rows={len(part)} class_distribution={part['label'].value_counts().to_dict()}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    run(args.run_id)


if __name__ == "__main__":
    main()
