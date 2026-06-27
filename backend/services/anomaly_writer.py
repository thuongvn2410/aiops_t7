from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from backend.db.queries import q_insert_anomaly


def severity_for_score(score: float) -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.70:
        return "warning"
    return "info"


def anomaly_payload(row) -> dict:
    detected_at = row.get("timestamp") or datetime.now(timezone.utc)
    if hasattr(detected_at, "isoformat"):
        # Ensure UTC-aware so isoformat() emits +00:00 (not naive string)
        if hasattr(detected_at, "tzinfo") and detected_at.tzinfo is None:
            detected_at = detected_at.replace(tzinfo=timezone.utc)
        detected_iso = detected_at.isoformat()
    else:
        detected_iso = str(detected_at)
    score = float(row.get("anomaly_score", 0.0))
    return {
        "event_id": str(uuid4()),
        "detected_at": detected_iso,
        "source_table": "metrics",
        "service_name": str(row.get("service_name", "")),
        "metric_name": str(row.get("metric_name", "")),
        "anomaly_score": score,
        "label": 1,
        "model_name": str(row.get("model_name", "IsolationForest")),
        "rca_causes": [],
        "severity": severity_for_score(score),
        "narrative": "",
    }


def write_anomaly(client, event: dict) -> dict:
    client.insert(
        "anomaly_events",
        [
            [
                event["event_id"],
                event["detected_at"],
                event["source_table"],
                event["service_name"],
                event["metric_name"],
                event["anomaly_score"],
                event["label"],
                event["model_name"],
                json.dumps(event.get("rca_causes", [])),
                event.get("narrative", ""),
            ]
        ],
        database="aiops",
        column_names=[
            "event_id",
            "detected_at",
            "source_table",
            "service_name",
            "metric_name",
            "anomaly_score",
            "label",
            "model_name",
            "rca_causes",
            "narrative",
        ],
    )
    return event
