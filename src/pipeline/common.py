from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_random_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except Exception:
        pass


def read_config() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "configs" / "train_config.yaml"
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    rows = int(os.getenv("AIOPS_ROWS", data.get("data", {}).get("rows", 1200)))
    data.setdefault("data", {})["rows"] = rows
    return data


def numeric_feature_columns(frame: pd.DataFrame) -> list[str]:
    blocked = {"timestamp", "label", "source", "message", "trace_id", "span_id", "parent_span_id", "service"}
    return [
        column
        for column in frame.columns
        if column not in blocked and pd.api.types.is_numeric_dtype(frame[column])
    ]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
