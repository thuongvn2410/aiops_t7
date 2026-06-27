from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import acquire, parse, prepare, process, render
from src.pipeline.state import get_latest_run_id, run_dir, stage_complete


@pytest.fixture(scope="session")
def run_id() -> str:
    os.environ.setdefault("AIOPS_ROWS", "240")
    selected = get_latest_run_id()
    if not selected or not stage_complete(selected, "acquire"):
        selected = acquire.run()
    if not stage_complete(selected, "prepare"):
        prepare.run(selected)
    return selected


@pytest.fixture(scope="session")
def processed_run(run_id: str) -> str:
    process.run(run_id, model="all")
    return run_id


@pytest.fixture(scope="session")
def parsed_run(processed_run: str) -> str:
    parse.run(processed_run)
    return processed_run


@pytest.fixture(scope="session")
def rendered_run(parsed_run: str) -> str:
    render.run(parsed_run)
    return parsed_run
