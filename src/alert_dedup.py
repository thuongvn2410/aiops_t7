from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN


def deduplicate_alerts(alerts: pd.DataFrame, eps: float = 0.8, min_samples: int = 2) -> tuple[pd.DataFrame, float]:
    if alerts.empty:
        return alerts.copy(), 0.0
    numeric = alerts.select_dtypes(include=[np.number]).drop(columns=["label"], errors="ignore")
    if numeric.empty:
        return alerts.drop_duplicates(subset=["timestamp"]).copy(), 0.0
    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(numeric)
    grouped = alerts.copy()
    grouped["incident_cluster"] = labels
    deduped = grouped.sort_values("timestamp").groupby("incident_cluster", as_index=False).first()
    reduction = 1.0 - (len(deduped) / max(1, len(alerts)))
    return deduped, float(reduction)
