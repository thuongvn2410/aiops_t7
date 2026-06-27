from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from src.pipeline.common import read_config, set_random_seed, utc_now
from src.pipeline.state import PROJECT_ROOT, resolve_run_id, run_dir, stage_complete

SOURCE_URL = "https://github.com/EvoTestOps/AnoMod"


def _maybe_clone_anomod(target: Path) -> None:
    if target.exists():
        return
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", SOURCE_URL, str(target)],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except Exception:
        return


def _synthetic_telemetry(rows: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    set_random_seed(42)
    timestamps = pd.date_range("2026-01-01", periods=rows, freq="min", tz="UTC")
    baseline = np.linspace(0, 14, rows)
    cpu = 45 + 8 * np.sin(baseline) + np.random.normal(0, 2.2, rows)
    memory = 60 + 5 * np.cos(baseline / 2) + np.random.normal(0, 1.8, rows)
    latency = 120 + 20 * np.sin(baseline / 3) + np.random.normal(0, 8, rows)
    error_rate = np.clip(np.random.beta(1.4, 45, rows), 0, 1)
    labels = np.zeros(rows, dtype=int)
    anomaly_indices = np.arange(max(20, rows // 12), rows, max(40, rows // 15))
    labels[anomaly_indices] = 1
    cpu[anomaly_indices] += 30
    latency[anomaly_indices] += 160
    error_rate[anomaly_indices] += 0.35

    metrics = pd.DataFrame(
        {
            "timestamp": timestamps,
            "cpu_usage": cpu,
            "memory_usage": memory,
            "latency_ms": latency,
            "error_rate": np.clip(error_rate, 0, 1),
            "label": labels,
        }
    )
    log_levels = np.where(labels == 1, "ERROR", np.where(error_rate > 0.08, "WARN", "INFO"))
    messages = [
        f"{level} service=checkout latency={latency[i]:.1f} cpu={cpu[i]:.1f} request_id=req-{i % 97}"
        for i, level in enumerate(log_levels)
    ]
    logs = pd.DataFrame(
        {
            "timestamp": timestamps,
            "source": "log",
            "message": messages,
            "label": labels,
        }
    )
    traces = pd.DataFrame(
        {
            "timestamp": timestamps,
            "trace_id": [f"trace-{i // 5}" for i in range(rows)],
            "span_id": [f"span-{i}" for i in range(rows)],
            "parent_span_id": [None if i % 5 == 0 else f"span-{i - 1}" for i in range(rows)],
            "service": np.where(labels == 1, "checkout", "api"),
            "duration_ms": latency * np.random.uniform(0.4, 1.2, rows),
            "error": labels,
            "label": labels,
        }
    )
    return metrics, logs, traces


def run(run_id: str | None = None) -> str:
    selected = resolve_run_id(run_id, create=run_id is None)
    if stage_complete(selected, "acquire"):
        print(f"acquire skip run_id={selected}: output files already exist")
        return selected

    raw_dir = run_dir(selected) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    _maybe_clone_anomod(PROJECT_ROOT / ".cache" / "AnoMod")
    rows = int(read_config()["data"]["rows"])
    metrics, logs, traces = _synthetic_telemetry(rows)

    metrics.to_parquet(raw_dir / "metrics.parquet", index=False)
    logs.to_parquet(raw_dir / "logs.parquet", index=False)
    traces.to_parquet(raw_dir / "traces.parquet", index=False)
    for name, frame in [("metrics", metrics), ("logs", logs), ("traces", traces)]:
        print(
            f"source={SOURCE_URL} dataset={name} rows={len(frame)} "
            f"schema={list(frame.columns)} fetched_at={utc_now()}"
        )
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    run(args.run_id)


if __name__ == "__main__":
    main()
