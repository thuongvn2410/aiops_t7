from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
LATEST_RUN_FILE = DATA_DIR / "latest_run.txt"

STAGE_OUTPUTS = {
    "acquire": [
        "raw/metrics.parquet",
        "raw/logs.parquet",
        "raw/traces.parquet",
    ],
    "prepare": [
        "splits/train.parquet",
        "splits/val.parquet",
        "splits/test.parquet",
    ],
    "process": [
        "process/run_manifest.json",
    ],
    "parse": [
        "parsed/metrics.json",
    ],
    "render": [
        "../../reports/{run_id}/roc_curves.png",
        "../../reports/{run_id}/pr_curves.png",
        "../../reports/{run_id}/confusion_matrices.png",
        "../../reports/{run_id}/score_distributions.png",
        "../../reports/{run_id}/summary_report.html",
    ],
}

STAGE_ORDER = ["acquire", "prepare", "process", "parse", "render"]


def get_run_id() -> str:
    """Return a run id in YYYYMMDD_HHMMSS format."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def run_dir(run_id: str) -> Path:
    return DATA_DIR / run_id


def report_dir(run_id: str) -> Path:
    return REPORTS_DIR / run_id


def set_latest_run_id(run_id: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_RUN_FILE.write_text(run_id, encoding="utf-8")


def get_latest_run_id() -> str | None:
    env_run_id = os.getenv("RUN_ID")
    if env_run_id:
        return env_run_id
    if LATEST_RUN_FILE.exists():
        value = LATEST_RUN_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    runs = sorted(p.name for p in DATA_DIR.glob("*") if p.is_dir())
    return runs[-1] if runs else None


def resolve_run_id(run_id: str | None = None, create: bool = False) -> str:
    selected = run_id or get_latest_run_id()
    if not selected or create:
        selected = get_run_id()
    set_latest_run_id(selected)
    return selected


def _stage_paths(run_id: str, stage_name: str) -> list[Path]:
    if stage_name not in STAGE_OUTPUTS:
        raise ValueError(f"Unknown stage: {stage_name}")
    paths: list[Path] = []
    for raw in STAGE_OUTPUTS[stage_name]:
        rendered = raw.format(run_id=run_id)
        if rendered.startswith("../../reports"):
            paths.append((run_dir(run_id) / rendered).resolve())
        else:
            paths.append(run_dir(run_id) / rendered)
    return paths


def stage_complete(run_id: str, stage_name: str) -> bool:
    """Check whether all output files of a stage exist."""
    return all(path.exists() for path in _stage_paths(run_id, stage_name))


def stage_status(run_id: str) -> dict[str, bool]:
    return {stage: stage_complete(run_id, stage) for stage in STAGE_ORDER}


def invalidate_from(run_id: str, stage_name: str) -> None:
    """Delete outputs for a stage and every downstream stage."""
    if stage_name not in STAGE_ORDER:
        raise ValueError(f"Unknown stage: {stage_name}")
    start = STAGE_ORDER.index(stage_name)
    targets = [
        run_dir(run_id) / "raw",
        run_dir(run_id) / "splits",
        run_dir(run_id) / "process",
        run_dir(run_id) / "checkpoints",
        run_dir(run_id) / "parsed",
        report_dir(run_id),
    ]
    stage_to_targets = {
        "acquire": targets,
        "prepare": targets[1:],
        "process": targets[2:],
        "parse": targets[4:],
        "render": [targets[5]],
    }
    for stage in STAGE_ORDER[start:]:
        for target in stage_to_targets[stage]:
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
