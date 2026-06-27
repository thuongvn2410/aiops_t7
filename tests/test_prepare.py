from __future__ import annotations

import pandas as pd

from src.pipeline.state import run_dir


def test_prepare_chronological_splits_no_leakage(run_id: str) -> None:
    root = run_dir(run_id) / "splits"
    train = pd.read_parquet(root / "train.parquet")
    val = pd.read_parquet(root / "val.parquet")
    test = pd.read_parquet(root / "test.parquet")
    assert len(train) > len(val) > 0
    assert len(test) > 0
    assert train["timestamp"].max() < val["timestamp"].min()
    assert val["timestamp"].max() < test["timestamp"].min()
    assert "cpu_usage_roll_mean_5" in train.columns
    assert any(column.startswith("log_tfidf_") for column in train.columns)
