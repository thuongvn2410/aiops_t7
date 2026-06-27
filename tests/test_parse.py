from __future__ import annotations

import json
import shutil

from src.pipeline import parse
from src.pipeline.state import run_dir


def test_parse_metrics_schema(parsed_run: str) -> None:
    path = run_dir(parsed_run) / "parsed" / "metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["run_id"] == parsed_run
    assert isinstance(payload["models"], list)
    assert payload["models"]
    required = {"name", "precision", "recall", "f1", "auc_roc", "auc_pr", "inference_ms", "optimal_threshold"}
    assert required <= set(payload["models"][0])


def test_parse_missing_checkpoint_graceful(parsed_run: str) -> None:
    root = run_dir(parsed_run)
    ckpt = root / "checkpoints" / "tft" / "best.pt"
    backup = root / "checkpoints" / "tft" / "best.bak"
    if ckpt.exists():
        shutil.move(str(ckpt), str(backup))
    try:
        (root / "parsed" / "metrics.json").unlink(missing_ok=True)
        (root / "parsed" / "metrics_full.json").unlink(missing_ok=True)
        parse.run(parsed_run)
        assert (root / "parse_errors.jsonl").exists()
    finally:
        if backup.exists():
            shutil.move(str(backup), str(ckpt))
        (root / "parsed" / "metrics.json").unlink(missing_ok=True)
        (root / "parsed" / "metrics_full.json").unlink(missing_ok=True)
        parse.run(parsed_run)
