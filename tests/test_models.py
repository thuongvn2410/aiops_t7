from __future__ import annotations

import numpy as np

from src.models.autoencoder import AutoencoderAnomaly
from src.models.deep_svdd import DeepSVDDAnomaly
from src.models.ensemble import ScoreEnsemble
from src.models.isolation_forest import IsolationForestAnomaly
from src.models.tft_model import TFTAnomaly
from src.models.xgboost_model import XGBoostAnomaly
from src.pipeline.state import run_dir


def test_model_checkpoints_exist(processed_run: str) -> None:
    for name in ["isolation_forest", "autoencoder", "svdd", "xgboost", "tft", "ensemble"]:
        assert (run_dir(processed_run) / "checkpoints" / name / "best.pt").exists()


def test_models_smoke_cpu_fake_data() -> None:
    rng = np.random.default_rng(42)
    x = rng.normal(size=(100, 8))
    y = np.r_[np.zeros(90), np.ones(10)]
    assert IsolationForestAnomaly().fit(x, x, y).score_samples(x).shape == (100,)
    assert AutoencoderAnomaly(8, device="cpu").fit(x, x, epochs=1).score_samples(x).shape == (100,)
    assert DeepSVDDAnomaly(8, device="cpu").fit(x, x, epochs=1).score_samples(x).shape == (100,)
    assert XGBoostAnomaly().fit(x, y).score_samples(x).shape == (100,)
    assert TFTAnomaly(8, device="cpu").fit(x, x, epochs=1).score_samples(x).shape == (100,)
    scores = np.column_stack([rng.random(100), rng.random(100), rng.random(100)])
    assert ScoreEnsemble().fit(scores, y).score_samples(scores).shape == (100,)
