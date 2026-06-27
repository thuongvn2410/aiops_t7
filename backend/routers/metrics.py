from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.db.client import clickhouse_status, get_client
from backend.db.queries import q_metric_names, q_services, q_timeline

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/timeline")
def timeline(service_name: str, metric_name: str, minutes: int = Query(60, ge=1, le=1440)) -> list[dict]:
    try:
        if clickhouse_status() != "ok":
            raise RuntimeError("clickhouse unavailable")
        rows = get_client().query(
            q_timeline(service_name, metric_name, minutes),
            parameters={"service_name": service_name, "metric_name": metric_name},
        ).result_rows
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"clickhouse unavailable: {exc}") from exc
    return [
        {
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "value": float(value),
            "service": service,
            "metric_name": metric,
            "unit": unit,
        }
        for ts, value, service, metric, unit in rows
    ]


@router.get("/services")
def services() -> list[str]:
    try:
        if clickhouse_status() != "ok":
            return []
        return [row[0] for row in get_client().query(q_services()).result_rows]
    except Exception:
        return []


@router.get("/metric-names")
def metric_names(service_name: str | None = None) -> list[str]:
    try:
        if clickhouse_status() != "ok":
            return []
        params = {"service_name": service_name} if service_name else None
        return [row[0] for row in get_client().query(q_metric_names(service_name), parameters=params).result_rows]
    except Exception:
        return []
