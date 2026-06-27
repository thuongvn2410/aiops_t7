from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from backend.db.queries import q_open_incident_for_service, q_update_incident_events
from backend.services.anomaly_writer import severity_for_score


SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}


def _summary(event: dict, severity: str, count: int) -> str:
    return f"{severity.upper()} {event['service_name']} {event['metric_name']} score={event['anomaly_score']:.2f} events={count}"


def process(client, event: dict) -> dict:
    severity = severity_for_score(float(event["anomaly_score"]))
    existing = client.query(q_open_incident_for_service(), parameters={"service_name": event["service_name"]}).result_rows
    if existing:
        incident_id, event_ids, created_at, current_severity, _summary_text = existing[0]
        ids = [item for item in str(event_ids).split(",") if item]
        if event["event_id"] not in ids:
            ids.append(event["event_id"])
        merged_severity = severity if SEVERITY_RANK[severity] > SEVERITY_RANK.get(str(current_severity), 0) else str(current_severity)
        summary = _summary(event, merged_severity, len(ids))
        client.command(
            q_update_incident_events(),
            parameters={
                "event_ids": ",".join(ids),
                "severity": merged_severity,
                "summary": summary,
                "incident_id": str(incident_id),
            },
        )
        return {
            "incident_id": str(incident_id),
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
            "service_name": event["service_name"],
            "severity": merged_severity,
            "status": 0,
            "event_ids": ids,
            "summary": summary,
        }
    incident_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    summary = _summary(event, severity, 1)
    client.insert(
        "alert_incidents",
        [[incident_id, created_at, None, event["service_name"], severity, 0, event["event_id"], summary]],
        database="aiops",
        column_names=["incident_id", "created_at", "resolved_at", "service_name", "severity", "status", "event_ids", "summary"],
    )
    return {
        "incident_id": incident_id,
        "created_at": created_at,
        "service_name": event["service_name"],
        "severity": severity,
        "status": 0,
        "event_ids": [event["event_id"]],
        "summary": summary,
    }
