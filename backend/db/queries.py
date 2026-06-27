from __future__ import annotations

from backend.config import CLICKHOUSE_DB


def q_recent_metrics(lookback_sec: int) -> str:
    return f"""
    SELECT service_name, metric_name, value, timestamp, unit
    FROM {CLICKHOUSE_DB}.metrics
    WHERE timestamp >= now() - INTERVAL {int(lookback_sec)} SECOND
    ORDER BY service_name, metric_name, timestamp
    """


def q_training_metrics(lookback_minutes: int) -> str:
    return f"""
    SELECT service_name, metric_name, value, timestamp, unit
    FROM {CLICKHOUSE_DB}.metrics
    WHERE timestamp >= now() - INTERVAL {int(lookback_minutes)} MINUTE
    ORDER BY service_name, metric_name, timestamp
    """


def q_timeline(service_name: str, metric_name: str, minutes: int) -> str:
    return f"""
    SELECT timestamp, value, service_name, metric_name, unit
    FROM {CLICKHOUSE_DB}.metrics
    WHERE service_name = %(service_name)s
      AND metric_name = %(metric_name)s
      AND timestamp >= now() - INTERVAL {int(minutes)} MINUTE
    ORDER BY timestamp
    """


def q_services() -> str:
    return f"""
    SELECT DISTINCT service_name
    FROM {CLICKHOUSE_DB}.metrics
    WHERE timestamp >= now() - INTERVAL 24 HOUR
    ORDER BY service_name
    """


def q_metric_names(service_name: str | None = None) -> str:
    clause = "WHERE service_name = %(service_name)s" if service_name else ""
    return f"""
    SELECT DISTINCT metric_name
    FROM {CLICKHOUSE_DB}.metrics
    {clause}
    ORDER BY metric_name
    """


def q_recent_alerts(status: str) -> str:
    status_clause = ""
    if status == "open":
        status_clause = "WHERE i.status = 0"
    elif status == "resolved":
        status_clause = "WHERE i.status = 1"
    return f"""
    SELECT
      e.event_id, e.detected_at, e.source_table, e.service_name, e.metric_name,
      e.anomaly_score, e.label, e.model_name, e.rca_causes,
      i.incident_id, i.severity, i.status AS incident_status, i.summary
    FROM {CLICKHOUSE_DB}.anomaly_events e
    LEFT JOIN (
      SELECT incident_id, severity, status, summary, arrayJoin(splitByChar(',', event_ids)) AS event_id_str
      FROM {CLICKHOUSE_DB}.alert_incidents
    ) i
      ON toString(e.event_id) = i.event_id_str
    {status_clause}
    ORDER BY e.detected_at DESC
    LIMIT %(limit)s
    """


def q_incidents(severity: str) -> str:
    where = "" if severity == "all" else "WHERE severity = %(severity)s"
    return f"""
    SELECT incident_id, created_at, resolved_at, service_name, severity, status, event_ids, summary
    FROM {CLICKHOUSE_DB}.alert_incidents
    {where}
    ORDER BY created_at DESC
    LIMIT %(limit)s
    """


def q_open_incident_for_service() -> str:
    return f"""
    SELECT incident_id, event_ids, created_at, severity, summary
    FROM {CLICKHOUSE_DB}.alert_incidents
    WHERE service_name = %(service_name)s
      AND status = 0
      AND created_at >= now() - INTERVAL 5 MINUTE
    ORDER BY created_at DESC
    LIMIT 1
    """


def q_insert_anomaly() -> str:
    return f"""
    INSERT INTO {CLICKHOUSE_DB}.anomaly_events
    (event_id, detected_at, source_table, service_name, metric_name, anomaly_score, label, model_name, rca_causes, narrative)
    VALUES
    """


def q_insert_incident() -> str:
    return f"""
    INSERT INTO {CLICKHOUSE_DB}.alert_incidents
    (incident_id, created_at, resolved_at, service_name, severity, status, event_ids, summary)
    VALUES
    """


def q_update_incident_events() -> str:
    return f"""
    ALTER TABLE {CLICKHOUSE_DB}.alert_incidents
    UPDATE event_ids = %(event_ids)s, severity = %(severity)s, summary = %(summary)s
    WHERE incident_id = %(incident_id)s
    """


def q_select_one() -> str:
    return "SELECT 1"
