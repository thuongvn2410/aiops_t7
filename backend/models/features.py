from __future__ import annotations

import pandas as pd


FEATURE_COLUMNS = ["value", "rolling_mean_12", "rolling_std_12", "rate_of_change"]


def rows_to_frame(rows) -> pd.DataFrame:
    if hasattr(rows, "result_rows"):
        rows = rows.result_rows
    frame = pd.DataFrame(rows, columns=["service_name", "metric_name", "value", "timestamp", "unit"])
    if frame.empty:
        return pd.DataFrame(columns=["service_name", "metric_name", "value", "timestamp", "unit", *FEATURE_COLUMNS])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce").fillna(0.0)
    return frame.sort_values(["service_name", "metric_name", "timestamp"]).reset_index(drop=True)


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    enriched = frame.copy()
    grouped = enriched.groupby(["service_name", "metric_name"], sort=False)["value"]
    enriched["rolling_mean_12"] = grouped.transform(lambda s: s.rolling(12, min_periods=1).mean())
    enriched["rolling_std_12"] = grouped.transform(lambda s: s.rolling(12, min_periods=1).std().fillna(0.0))
    enriched["rate_of_change"] = grouped.transform(lambda s: s.diff().fillna(0.0))
    return enriched.fillna(0.0)


def feature_matrix(frame: pd.DataFrame):
    return frame[FEATURE_COLUMNS].astype(float).to_numpy()
