from __future__ import annotations

import pandas as pd

from src.pipeline.state import run_dir


def test_acquire_outputs_exist_and_have_schema(run_id: str) -> None:
    raw = run_dir(run_id) / "raw"
    for name in ["metrics", "logs", "traces"]:
        path = raw / f"{name}.parquet"
        assert path.exists()
        frame = pd.read_parquet(path)
        assert len(frame) > 0
        assert "timestamp" in frame.columns
        assert "label" in frame.columns
