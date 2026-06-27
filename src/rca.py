from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd
from statsmodels.tsa.stattools import grangercausalitytests


def rank_root_causes(frame: pd.DataFrame, target: str = "latency_ms", max_lag: int = 2) -> dict:
    pvalues: dict[str, float] = {}
    numeric = [c for c in frame.columns if c != target and pd.api.types.is_numeric_dtype(frame[c])]
    for column in numeric:
        try:
            result = grangercausalitytests(frame[[target, column]].dropna(), maxlag=max_lag, verbose=False)
            pvalues[column] = float(min(result[lag][0]["ssr_ftest"][1] for lag in result))
        except Exception:
            pvalues[column] = 1.0
    likely = [name for name, _ in sorted(pvalues.items(), key=lambda item: item[1])[:2]]
    confidence = 1.0 - min(pvalues.values(), default=1.0)
    return {
        "anomaly_id": str(uuid4()),
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "likely_causes": likely,
        "granger_pvalues": pvalues,
        "confidence": float(max(0.0, min(1.0, confidence))),
    }
