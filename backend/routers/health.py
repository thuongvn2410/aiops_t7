from __future__ import annotations

from fastapi import APIRouter, Request

from backend.db.client import clickhouse_status
from backend.ws.manager import ws_manager

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(request: Request) -> dict:
    detector = getattr(request.app.state, "detector", None)
    return {
        "status": "ok",
        "clickhouse": clickhouse_status(),
        "model_loaded": bool(getattr(detector, "loaded", False)),
        "model_name": getattr(detector, "model_name", "unloaded"),
        "threshold": getattr(detector, "threshold", None),
        "ws_clients": len(ws_manager.active),
    }
