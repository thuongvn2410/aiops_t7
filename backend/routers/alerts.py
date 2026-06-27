from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from backend.db.client import clickhouse_status, get_client
from backend.db.queries import q_incidents, q_recent_alerts

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _to_utc_iso(dt) -> str:
    """Return ISO-8601 string with +00:00 so frontend can convert to local timezone."""
    if dt is None:
        return None
    if hasattr(dt, "tzinfo") and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)


def _parse_rca(value: str) -> list:
    try:
        return json.loads(value or "[]")
    except json.JSONDecodeError:
        return []


@router.get("/recent")
def recent(limit: int = Query(50, ge=1, le=200), status: str = Query("all", pattern="^(open|resolved|all)$")) -> list[dict]:
    try:
        if clickhouse_status() != "ok":
            return []
        rows = get_client().query(q_recent_alerts(status), parameters={"limit": limit}).result_rows
    except Exception:
        return []
    return [
        {
            "event_id": str(event_id),
            "detected_at": _to_utc_iso(detected_at),
            "source_table": source_table,
            "service_name": service_name,
            "metric_name": metric_name,
            "anomaly_score": float(anomaly_score),
            "label": int(label),
            "model_name": model_name,
            "rca_causes": _parse_rca(rca_causes),
            "incident_id": str(incident_id) if incident_id else None,
            "severity": severity or "info",
            "status": int(incident_status) if incident_status is not None else None,
            "summary": summary or "",
        }
        for event_id, detected_at, source_table, service_name, metric_name, anomaly_score, label, model_name, rca_causes, incident_id, severity, incident_status, summary in rows
    ]


@router.get("/incidents")
def incidents(limit: int = Query(20, ge=1, le=100), severity: str = Query("all", pattern="^(critical|warning|info|all)$")) -> list[dict]:
    try:
        if clickhouse_status() != "ok":
            return []
        rows = get_client().query(q_incidents(severity), parameters={"limit": limit, "severity": severity}).result_rows
    except Exception:
        return []
    return [
        {
            "incident_id": str(incident_id),
            "created_at": _to_utc_iso(created_at),
            "resolved_at": _to_utc_iso(resolved_at),
            "service_name": service_name,
            "severity": sev,
            "status": int(status),
            "event_ids": [item for item in str(event_ids).split(",") if item],
            "summary": summary,
        }
        for incident_id, created_at, resolved_at, service_name, sev, status, event_ids, summary in rows
    ]
