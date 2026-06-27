from __future__ import annotations

import numpy as np
import pandas as pd

from src.alert_dedup import deduplicate_alerts


def test_alert_dedup_reduces_synthetic_burst_over_60_percent() -> None:
    rng = np.random.default_rng(42)
    burst = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=100, freq="s"),
            "cpu_usage": 90 + rng.normal(0, 0.05, 100),
            "latency_ms": 300 + rng.normal(0, 0.05, 100),
            "error_rate": 0.4 + rng.normal(0, 0.01, 100),
            "label": 1,
        }
    )
    deduped, reduction = deduplicate_alerts(burst, eps=0.5, min_samples=2)
    assert len(deduped) < len(burst)
    assert reduction > 0.60
